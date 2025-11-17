/**
 Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

 Licensed under the Apache License, Version 2.0 (the "License").
 You may not use this file except in compliance with the License.
 You may obtain a copy of the License at

 http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
 */
import { Duration, Stack, StackProps } from 'aws-cdk-lib';
import { ITable, Table } from 'aws-cdk-lib/aws-dynamodb';
import { Credentials, DatabaseInstance, DatabaseInstanceEngine } from 'aws-cdk-lib/aws-rds';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';
import { Code, Function, IFunction, ILayerVersion, LayerVersion } from 'aws-cdk-lib/aws-lambda';
import { FastApiContainer } from '../api-base/fastApiContainer';
import { ECSCluster } from '../api-base/ecsCluster';
import { createCdkId } from '../core/utils';
import { Vpc } from '../networking/vpc';
import { BaseProps, Config } from '../schema';
import {
    Effect,
    Policy,
    PolicyDocument,
    PolicyStatement,
    Role,
    ServicePrincipal,
} from 'aws-cdk-lib/aws-iam';
import { HostedRotation, ISecret } from 'aws-cdk-lib/aws-secretsmanager';
import { SecurityGroupEnum } from '../core/iam/SecurityGroups';
import { SecurityGroupFactory } from '../networking/vpc/security-group-factory';
import { LAMBDA_PATH, REST_API_PATH } from '../util';
import { AwsCustomResource, PhysicalResourceId } from 'aws-cdk-lib/custom-resources';
import { getDefaultRuntime } from '../api-base/utils';
import { ISecurityGroup, Port } from 'aws-cdk-lib/aws-ec2';
import { ECSTasks } from '../api-base/ecsCluster';
import { GuardrailsTable } from '../models/guardrails-table';

export type LisaServeApplicationProps = {
    vpc: Vpc;
    securityGroups: ISecurityGroup[];
} & BaseProps & StackProps;

/**
 * LisaServe Application stack.
 */
export class LisaServeApplicationConstruct extends Construct {
    /** FastAPI construct */
    public readonly restApi: FastApiContainer;
    public readonly modelsPs: StringParameter;
    public readonly endpointUrl: StringParameter;
    public readonly tokenTable?: ITable;
    public readonly ecsCluster: ECSCluster;
    public readonly guardrailsTableNamePs: StringParameter;
    public readonly guardrailsTable: ITable;

    /**
     * @param {Stack} scope - The parent or owner of the construct.
     * @param {string} id - The unique identifier for the construct within its scope.
     * @param {LisaServeApplicationProps} props - Properties for the Stack.
     */
    constructor (scope: Stack, id: string, props: LisaServeApplicationProps) {
        super(scope, id);
        const { config, vpc, securityGroups } = props;

        // TokenTable is now created in API Base, reference it from SSM parameter
        // API Base stack must be deployed before Serve stack (dependency is set in stages.ts)
        const tokenTableNameParameter = StringParameter.fromStringParameterName(
            scope,
            'TokenTableNameParameter',
            `${config.deploymentPrefix}/tokenTableName`
        );
        // Reference the table by name (table is created in API Base stack)
        let tokenTable = Table.fromTableName(
            scope,
            'TokenTable',
            tokenTableNameParameter.stringValue
        );
        this.tokenTable = tokenTable;

        const managementKeySecretNameStringParameter = StringParameter.fromStringParameterName(this, createCdkId([id, 'managementKeyStringParameter']), `${config.deploymentPrefix}/appManagementKeySecretName`);

        // Create guardrails table in serve stack to avoid circular dependency
        const guardrailsTableConstruct = new GuardrailsTable(scope, 'GuardrailsTable', {
            deploymentPrefix: config.deploymentPrefix || '',
            removalPolicy: config.removalPolicy,
        });
        this.guardrailsTable = guardrailsTableConstruct.table;

        // Create SSM parameter for guardrails table name
        this.guardrailsTableNamePs = new StringParameter(scope, 'GuardrailsTableNameParameter', {
            parameterName: `${config.deploymentPrefix}/guardrailsTableName`,
            stringValue: this.guardrailsTable.tableName,
        });

        // Create REST API
        const restApi = new FastApiContainer(scope, 'RestApi', {
            apiName: 'REST',
            config: config,
            resourcePath: REST_API_PATH,
            securityGroup: vpc.securityGroups.restApiAlbSg,
            tokenTable: tokenTable,
            vpc: vpc,
            managementKeyName: managementKeySecretNameStringParameter.stringValue
        });

        // LiteLLM requires a PostgreSQL database to support multiple-instance scaling with dynamic model management.
        const connectionParamName = 'LiteLLMDbConnectionInfo';

        const litellmDbSg = SecurityGroupFactory.createSecurityGroup(
            scope,
            config.securityGroupConfig?.liteLlmDbSecurityGroupId,
            SecurityGroupEnum.LITE_LLM_SG,
            undefined,
            vpc.vpc,
            'LiteLLM dynamic model management database',
        );

        if (!config.securityGroupConfig?.liteLlmDbSecurityGroupId) {
            SecurityGroupFactory.addIngress(litellmDbSg, SecurityGroupEnum.LITE_LLM_SG, vpc.vpc, config.restApiConfig.rdsConfig.dbPort, vpc.subnetSelection?.subnets);
        }

        const username = config.restApiConfig.rdsConfig.username;
        const dbCreds = Credentials.fromGeneratedSecret(username);

        // DB is a Single AZ instance for cost + inability to make non-Aurora multi-AZ cluster in CDK
        // DB is not expected to be under any form of heavy load.
        // https://github.com/aws/aws-cdk/issues/25547
        const litellmDb = new DatabaseInstance(scope, 'LiteLLMScalingDB', {
            engine: DatabaseInstanceEngine.POSTGRES,
            vpc: vpc.vpc,
            subnetGroup: vpc.subnetGroup,
            credentials: dbCreds,
            iamAuthentication: true,
            securityGroups: [litellmDbSg],
            removalPolicy: config.removalPolicy,
        });

        const litellmDbPasswordSecret = litellmDb.secret!;

        // Add rotation policy for the database password secret (only if not using IAM auth)
        if (!config.iamRdsAuth) {
            // Allow the rotation Lambda to connect to the database
            securityGroups.forEach((sg) => {
                litellmDbSg.addIngressRule(
                    sg,
                    Port.tcp(config.restApiConfig.rdsConfig.dbPort),
                    'Allow rotation Lambda to connect to database'
                );
            });

            litellmDbPasswordSecret.addRotationSchedule('DatabasePasswordRotationSchedule', {
                automaticallyAfter: Duration.days(30),
                hostedRotation: HostedRotation.postgreSqlSingleUser({
                    functionName: `${config.deploymentName}-Litellm-Rotation-Function`,
                    vpc: vpc.vpc,
                    vpcSubnets: vpc.subnetSelection,
                    securityGroups: securityGroups
                })
            });
        }

        const litellmDbConnectionInfoPs = new StringParameter(scope, createCdkId([connectionParamName, 'StringParameter']), {
            parameterName: `${config.deploymentPrefix}/${connectionParamName}`,
            stringValue: JSON.stringify({
                username: username,
                dbHost: litellmDb.dbInstanceEndpointAddress,
                dbName: config.restApiConfig.rdsConfig.dbName,
                dbPort: config.restApiConfig.rdsConfig.dbPort,
                // only include passwordSecretId if authenticating with username/password
                ...(config.iamRdsAuth ? {} : { passwordSecretId: litellmDbPasswordSecret.secretName })
            }),
        });
        console.log('storing llmdbconninfop', JSON.stringify({
            username: username,
            dbHost: litellmDb.dbInstanceEndpointAddress,
            dbName: config.restApiConfig.rdsConfig.dbName,
            dbPort: config.restApiConfig.rdsConfig.dbPort,
            // only include passwordSecretId if authenticating with username/password
            ...(config.iamRdsAuth ? {} : { passwordSecretId: litellmDbPasswordSecret.secretName })
        }));

        // update the rdsConfig with the endpoint address
        config.restApiConfig.rdsConfig.dbHost = litellmDb.dbInstanceEndpointAddress;

        // Create Parameter Store entry with RestAPI URI
        this.endpointUrl = new StringParameter(scope, createCdkId(['LisaServeRestApiUri', 'StringParameter']), {
            parameterName: `${config.deploymentPrefix}/lisaServeRestApiUri`,
            stringValue: restApi.endpoint,
            description: 'URI for LISA Serve API',
        });

        // Create Parameter Store entry with registeredModels
        this.modelsPs = new StringParameter(scope, createCdkId(['RegisteredModels', 'StringParameter']), {
            parameterName: `${config.deploymentPrefix}/registeredModels`,
            stringValue: JSON.stringify([]),
            description: 'Serialized JSON of registered models data',
        });

        const serveRole = restApi.apiCluster.taskRoles[ECSTasks.REST];
        if (serveRole) {
            // Grant access to REST API task role only
            litellmDbConnectionInfoPs.grantRead(serveRole);
            if (config.iamRdsAuth) {
                litellmDb.grantConnect(serveRole, serveRole.roleName);

                // Create the lambda for generating DB users for IAM auth
                const createDbUserLambda = this.getIAMAuthLambda(scope, config, litellmDbPasswordSecret, serveRole.roleName, vpc, [litellmDbSg]);

                const customResourceRole = new Role(scope, 'LISAServeCustomResourceRole', {
                    assumedBy: new ServicePrincipal('lambda.amazonaws.com'),
                });
                createDbUserLambda.grantInvoke(customResourceRole);

                // run updateInstanceKmsConditionsLambda every deploy
                new AwsCustomResource(scope, 'LISAServeCreateDbUserCustomResource', {
                    onCreate: {
                        service: 'Lambda',
                        action: 'invoke',
                        physicalResourceId: PhysicalResourceId.of('LISAServeCreateDbUserCustomResource'),
                        parameters: {
                            FunctionName: createDbUserLambda.functionName,
                            Payload: '{}'
                        },
                    },
                    role: customResourceRole
                });
            } else {
                litellmDb.grantConnect(serveRole);
                litellmDbPasswordSecret.grantRead(serveRole);
            }
            this.modelsPs.grantRead(serveRole);
        }

        // Use the guardrails table name from the construct we just created
        const guardrailsTableName = this.guardrailsTable.tableName;

        // Add parameter as container environment variable for both RestAPI and RagAPI
        const container = restApi.apiCluster.containers[ECSTasks.REST];
        if (container) {
            container.addEnvironment('LITELLM_DB_INFO_PS_NAME', litellmDbConnectionInfoPs.parameterName);
            container.addEnvironment('REGISTERED_MODELS_PS_NAME', this.modelsPs.parameterName);
            container.addEnvironment('LITELLM_DB_INFO_PS_NAME', litellmDbConnectionInfoPs.parameterName);
            container.addEnvironment('GUARDRAILS_TABLE_NAME', guardrailsTableName);
        }
        restApi.node.addDependency(this.modelsPs);
        restApi.node.addDependency(litellmDbConnectionInfoPs);
        restApi.node.addDependency(this.endpointUrl);

        // Update
        this.restApi = restApi;
        this.ecsCluster = restApi.apiCluster;

        // Grant permissions after restApi is fully constructed
        // Additional permissions for REST API Role
        const invocation_permissions = new Policy(scope, 'ModelInvokePerms', {
            statements: [
                new PolicyStatement({
                    effect: Effect.ALLOW,
                    actions: [
                        'bedrock:InvokeModel',
                        'bedrock:InvokeModelWithResponseStream',
                        'bedrock:ApplyGuardrail',
                    ],
                    resources: [
                        '*'
                    ]
                }),
                new PolicyStatement({
                    effect: Effect.ALLOW,
                    actions: [
                        'sagemaker:InvokeEndpoint',
                        'sagemaker:InvokeEndpointWithResponseStream',
                    ],
                    resources: [
                        'arn:*:sagemaker:*:*:endpoint/*'
                    ],
                }),
            ]
        });

        // Grant DynamoDB permissions for guardrails table
        const guardrails_permissions = new Policy(scope, 'GuardrailsTablePerms', {
            statements: [
                new PolicyStatement({
                    effect: Effect.ALLOW,
                    actions: [
                        'dynamodb:Query',
                        'dynamodb:GetItem',
                    ],
                    resources: [
                        `arn:${config.partition}:dynamodb:${config.region}:${config.accountNumber}:table/${guardrailsTableName}/*`,
                    ],
                }),
            ]
        });

        // Grant SSM parameter read access and attach invocation permissions
        const restRole = restApi.apiCluster.taskRoles[ECSTasks.REST];
        if (restRole) {
            this.modelsPs.grantRead(restRole);
            litellmDbConnectionInfoPs.grantRead(restRole);
            restRole.attachInlinePolicy(invocation_permissions);
            restRole.attachInlinePolicy(guardrails_permissions);
            if (serveRole) {
                this.modelsPs.grantRead(serveRole);
                litellmDbConnectionInfoPs.grantRead(serveRole);
                serveRole.attachInlinePolicy(invocation_permissions);
            }
        }
    };

    getIAMAuthLambda (scope: Stack, config: Config, secret: ISecret, user: string, vpc: Vpc, securityGroups: ISecurityGroup[]): IFunction {
        // Create the IAM role for updating the database to allow IAM authentication
        const iamAuthLambdaRole = new Role(scope, createCdkId(['LISAServe', 'IAMAuthLambdaRole']), {
            assumedBy: new ServicePrincipal('lambda.amazonaws.com'),
            inlinePolicies: {
                'EC2NetworkInterfaces': new PolicyDocument({
                    statements: [
                        new PolicyStatement({
                            effect: Effect.ALLOW,
                            actions: ['ec2:CreateNetworkInterface', 'ec2:DescribeNetworkInterfaces', 'ec2:DeleteNetworkInterface'],
                            resources: ['*'],
                        }),
                    ],
                }),
            }
        });

        secret.grantRead(iamAuthLambdaRole);

        const commonLayer = this.getLambdaLayer(scope, config);
        const lambdaPath = config.lambdaPath || LAMBDA_PATH;

        // Create the Lambda function that will create the database user
        return new Function(scope, 'LISAServeCreateDbUserLambda', {
            runtime: getDefaultRuntime(),
            handler: 'utilities.db_setup_iam_auth.handler',
            code: Code.fromAsset(lambdaPath),
            timeout: Duration.minutes(2),
            environment: {
                SECRET_ARN: secret.secretArn, // ARN of the RDS secret
                DB_HOST: config.restApiConfig.rdsConfig.dbHost!,
                DB_PORT: String(config.restApiConfig.rdsConfig.dbPort), // Default PostgreSQL port
                DB_NAME: config.restApiConfig.rdsConfig.dbName, // Database name
                DB_USER: config.restApiConfig.rdsConfig.username, // Admin user for RDS
                IAM_NAME: user, // IAM role for Lambda execution
            },
            role: iamAuthLambdaRole, // Lambda execution role
            layers: [commonLayer],
            vpc: vpc.vpc,
            vpcSubnets: vpc.subnetSelection,
            securityGroups: securityGroups,
        });
    }

    getLambdaLayer (scope: Stack, config: Config): ILayerVersion {
        return LayerVersion.fromLayerVersionArn(
            scope,
            'LISAServeCommonLayerVersion',
            StringParameter.valueForStringParameter(scope, `${config.deploymentPrefix}/layerVersion/common`),
        );
    }

}

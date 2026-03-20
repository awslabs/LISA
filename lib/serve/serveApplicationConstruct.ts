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
import { CustomResource, Duration, RemovalPolicy, Stack, StackProps } from 'aws-cdk-lib';
import { ITable, Table } from 'aws-cdk-lib/aws-dynamodb';
import { Credentials, DatabaseInstance, DatabaseInstanceEngine, IDatabaseInstance } from 'aws-cdk-lib/aws-rds';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';
import { FastApiContainer } from '../api-base/fastApiContainer';
import { ECSCluster } from '../api-base/ecsCluster';
import { createCdkId } from '../core/utils';
import { Vpc } from '../networking/vpc';
import { APP_MANAGEMENT_KEY, BaseProps } from '../schema';
import {
    Effect,
    ManagedPolicy,
    Policy,
    PolicyStatement,
    Role,
    ServicePrincipal,
} from 'aws-cdk-lib/aws-iam';
import { HostedRotation } from 'aws-cdk-lib/aws-secretsmanager';
import { SecurityGroupEnum } from '../core/iam/SecurityGroups';
import { SecurityGroupFactory } from '../networking/vpc/security-group-factory';
import { LAMBDA_PATH, REST_API_PATH } from '../util';
import { AwsCustomResource, AwsCustomResourcePolicy, PhysicalResourceId, Provider } from 'aws-cdk-lib/custom-resources';
import { ISecurityGroup, Port } from 'aws-cdk-lib/aws-ec2';
import { ECSTasks } from '../api-base/ecsCluster';
import { GuardrailsTable } from '../models/guardrails-table';
import { Code, Function, LayerVersion } from 'aws-cdk-lib/aws-lambda';
import { getPythonRuntime } from '../api-base/utils';

export type LisaServeApplicationProps = {
    vpc: Vpc;
    securityGroups: ISecurityGroup[];
    metricsQueueUrl?: string;
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

        // Determine authentication method - default to IAM auth (iamRdsAuth = false)
        const useIamAuth = config.iamRdsAuth ?? false;

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

        const managementKeySecretNameStringParameter = StringParameter.fromStringParameterName(this, createCdkId([id, 'managementKeyStringParameter']), `${config.deploymentPrefix}/${APP_MANAGEMENT_KEY}`);

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

        // Create credentials for database setup
        const dbCreds = Credentials.fromGeneratedSecret(username);

        // DB is a Single AZ instance for cost + inability to make non-Aurora multi-AZ cluster in CDK
        // DB is not expected to be under any form of heavy load.
        // https://github.com/aws/aws-cdk/issues/25547
        // NOTE: databaseName is intentionally NOT set here for backwards compatibility.
        // Previous deployments created this RDS instance without a named database, so the
        // default 'postgres' database is used. This means restApiConfig.rdsConfig.dbName
        // is NOT respected for the LiteLLM database - it will always use 'postgres'.
        const litellmDb = new DatabaseInstance(scope, 'LiteLLMScalingDB', {
            engine: DatabaseInstanceEngine.POSTGRES,
            vpc: vpc.vpc,
            subnetGroup: vpc.subnetGroup,
            credentials: dbCreds,
            iamAuthentication: useIamAuth, // Enable IAM auth when iamRdsAuth is true
            securityGroups: [litellmDbSg],
            removalPolicy: config.removalPolicy,
            deletionProtection: config.removalPolicy !== RemovalPolicy.DESTROY,
        });

        // Secret is used for password auth or for IAM user bootstrap
        const litellmDbSecret = litellmDb.secret!;

        // Add rotation policy for the database password secret (only if using password auth)
        if (!useIamAuth) {
            // WARNING: If switching from IAM auth (iamRdsAuth=true) back to password auth (iamRdsAuth=false),
            // the deployment will fail because the master password secret was deleted during IAM auth setup.
            // This is a one-way migration - once IAM auth is enabled, you cannot switch back to password auth
            // without recreating the database.

            // Allow the rotation Lambda to connect to the database
            securityGroups.forEach((sg) => {
                litellmDbSg.addIngressRule(
                    sg,
                    Port.tcp(config.restApiConfig.rdsConfig.dbPort),
                    'Allow rotation Lambda to connect to database'
                );
            });

            litellmDbSecret.addRotationSchedule('DatabasePasswordRotationSchedule', {
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
                // Include passwordSecretId only when using password auth
                ...(!useIamAuth ? { passwordSecretId: litellmDbSecret.secretName } : {})
            }),
        });

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

            if (!useIamAuth) {
                // Password auth: grant secret read access only (grantConnect requires IAM auth)
                litellmDbSecret.grantRead(serveRole);
            } else {
                // IAM auth: manually grant rds-db:connect permission
                // Note: We do NOT use litellmDb.grantConnect() due to CDK bug #11851
                // The grantConnect method generates incorrect ARN format (uses rds: instead of rds-db:)
                // Per AWS docs: https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.IAMDBAuth.html
                // The correct format is: arn:aws:rds-db:region:account-id:dbuser:DbiResourceId/db-user-name
                serveRole.addToPrincipalPolicy(new PolicyStatement({
                    effect: Effect.ALLOW,
                    actions: ['rds-db:connect'],
                    resources: [
                        // Use wildcard for DbiResourceId since it's not available in CloudFormation
                        // Format: arn:aws:rds-db:region:account:dbuser:*/username
                        `arn:${config.partition}:rds-db:${config.region}:${config.accountNumber}:dbuser:*/${serveRole.roleName}`
                    ]
                }));

                // Use the shared IAM auth setup Lambda from API Base stack
                const iamAuthSetupFnArn = StringParameter.valueForStringParameter(
                    scope,
                    `${config.deploymentPrefix}/iamAuthSetupFnArn`
                );

                // Get the IAM auth setup Lambda role ARN from SSM to grant it permissions
                const iamAuthSetupRoleArn = StringParameter.valueForStringParameter(
                    scope,
                    `${config.deploymentPrefix}/iamAuthSetupRoleArn`
                );

                // Import the IAM auth setup role to grant it secret permissions
                const iamAuthSetupRole = Role.fromRoleArn(
                    scope,
                    'IamAuthSetupRoleRef',
                    iamAuthSetupRoleArn
                );

                // Grant the IAM auth setup Lambda role permission to read the bootstrap secret
                litellmDbSecret.grantRead(iamAuthSetupRole);

                // Run the shared IAM auth setup Lambda on create and update
                // This runs when switching to IAM auth or updating the configuration
                // Pass parameters via payload since the Lambda is shared
                // Use Stack.of(scope).toJsonString() to properly resolve CDK tokens in the payload
                // Include timestamp to force re-run on every deployment
                const lambdaInvokeParams = {
                    service: 'Lambda',
                    action: 'invoke',
                    physicalResourceId: PhysicalResourceId.of('LISAServeCreateDbUserCustomResource'),
                    parameters: {
                        FunctionName: iamAuthSetupFnArn,
                        Payload: Stack.of(scope).toJsonString({
                            secretArn: litellmDbSecret.secretArn,
                            dbHost: config.restApiConfig.rdsConfig.dbHost,
                            dbPort: config.restApiConfig.rdsConfig.dbPort,
                            dbName: config.restApiConfig.rdsConfig.dbName,
                            dbUser: config.restApiConfig.rdsConfig.username,
                            iamName: serveRole.roleName,
                            timestamp: new Date().toISOString(), // Force re-run on every deployment
                        })
                    },
                };

                const createDbUserResource = new AwsCustomResource(scope, 'LISAServeCreateDbUserCustomResource', {
                    onCreate: lambdaInvokeParams,
                    onUpdate: lambdaInvokeParams,  // Also run on updates to ensure IAM user is created
                    policy: AwsCustomResourcePolicy.fromStatements([
                        new PolicyStatement({
                            effect: Effect.ALLOW,
                            actions: ['lambda:InvokeFunction'],
                            resources: [iamAuthSetupFnArn],
                        })
                    ]),
                });

                // Ensure the RDS instance is fully available before running IAM auth setup
                createDbUserResource.node.addDependency(litellmDb);

                // Ensure the ECS service waits for IAM user setup to complete
                restApi.node.addDependency(createDbUserResource);
            }

            this.modelsPs.grantRead(serveRole);
        }

        // Use the guardrails table name from the construct we just created
        const guardrailsTableName = this.guardrailsTable.tableName;

        // Get generated images bucket name for video/image content storage
        const imagesBucketName = StringParameter.valueForStringParameter(
            scope,
            `${config.deploymentPrefix}/generatedImagesBucketName`
        );

        // Add parameter as container environment variable for both RestAPI and RagAPI
        const container = restApi.apiCluster.containers[ECSTasks.REST];
        if (container) {
            container.addEnvironment('LITELLM_DB_INFO_PS_NAME', litellmDbConnectionInfoPs.parameterName);
            container.addEnvironment('REGISTERED_MODELS_PS_NAME', this.modelsPs.parameterName);
            container.addEnvironment('LITELLM_DB_INFO_PS_NAME', litellmDbConnectionInfoPs.parameterName);
            container.addEnvironment('GUARDRAILS_TABLE_NAME', guardrailsTableName);
            container.addEnvironment('GENERATED_IMAGES_S3_BUCKET_NAME', imagesBucketName);
            container.addEnvironment('MODEL_INFO_CACHE_TTL', '300');
            // Add metrics queue URL if provided
            if (props.metricsQueueUrl) {
                // Get the queue URL from SSM parameter
                const queueUrl = StringParameter.valueForStringParameter(scope, props.metricsQueueUrl);
                container.addEnvironment('USAGE_METRICS_QUEUE_URL', queueUrl);
            }

            // Add IAM auth environment variables for LiteLLM's native token refresh
            // When these are set, LiteLLM automatically generates and refreshes IAM auth tokens
            if (useIamAuth && serveRole) {
                container.addEnvironment('IAM_TOKEN_DB_AUTH', 'true');
                container.addEnvironment('DATABASE_HOST', litellmDb.dbInstanceEndpointAddress);
                container.addEnvironment('DATABASE_NAME', config.restApiConfig.rdsConfig.dbName);
                container.addEnvironment('DATABASE_PORT', config.restApiConfig.rdsConfig.dbPort.toString());
                container.addEnvironment('DATABASE_USER', serveRole.roleName);
            }
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

            // Grant S3 bucket permissions for video/image content storage
            restRole.addToPrincipalPolicy(
                new PolicyStatement({
                    effect: Effect.ALLOW,
                    actions: ['s3:PutObject', 's3:GetObject', 's3:DeleteObject'],
                    resources: [`arn:${config.partition}:s3:::${imagesBucketName}/*`]
                })
            );

            // Grant SQS send permissions if metrics queue URL is provided
            if (props.metricsQueueUrl) {
                // Get the queue name from SSM parameter
                const queueName = StringParameter.valueForStringParameter(
                    scope,
                    `${config.deploymentPrefix}/queue-name/usage-metrics`
                );
                const sqs_permissions = new Policy(scope, 'SQSMetricsPerms', {
                    statements: [
                        new PolicyStatement({
                            effect: Effect.ALLOW,
                            actions: ['sqs:SendMessage'],
                            resources: [`arn:${config.partition}:sqs:${config.region}:${config.accountNumber}:${queueName}`],
                        }),
                    ]
                });
                restRole.attachInlinePolicy(sqs_permissions);
            }

            if (serveRole) {
                this.modelsPs.grantRead(serveRole);
                litellmDbConnectionInfoPs.grantRead(serveRole);
                serveRole.attachInlinePolicy(invocation_permissions);
            }
        }

        // Create Lambda for syncing models from DynamoDB to LiteLLM
        // This runs when the LiteLLM database is created or updated
        this.createLiteLLMModelSyncLambda(scope, config, vpc, securityGroups, litellmDb);
    }

    /**
     * Creates a Lambda function to sync models from DynamoDB to LiteLLM.
     * This is triggered when the LiteLLM PostgreSQL database is created or updated,
     * ensuring all models in the Models DynamoDB table are registered in LiteLLM.
     */
    private createLiteLLMModelSyncLambda (
        scope: Stack,
        config: any,
        vpc: Vpc,
        securityGroups: ISecurityGroup[],
        litellmDb: IDatabaseInstance
    ): void {
        const lambdaPath = config.lambdaPath || LAMBDA_PATH;

        // Get common layer based on arn from SSM
        const commonLambdaLayer = LayerVersion.fromLayerVersionArn(
            scope,
            'litellm-sync-common-lambda-layer',
            StringParameter.valueForStringParameter(scope, `${config.deploymentPrefix}/layerVersion/common`),
        );

        const fastapiLambdaLayer = LayerVersion.fromLayerVersionArn(
            scope,
            'litellm-sync-fastapi-lambda-layer',
            StringParameter.valueForStringParameter(scope, `${config.deploymentPrefix}/layerVersion/fastapi`),
        );

        const lambdaLayers = [commonLambdaLayer, fastapiLambdaLayer];

        // Get management key name from SSM
        const managementKeyName = StringParameter.valueForStringParameter(
            scope,
            `${config.deploymentPrefix}/${APP_MANAGEMENT_KEY}`
        );

        // Get model table name from SSM
        const modelTableName = StringParameter.valueForStringParameter(
            scope,
            `${config.deploymentPrefix}/modelTableName`
        );

        // Create role for the Lambda
        const litellmSyncRole = new Role(scope, 'LiteLLMModelSyncRole', {
            assumedBy: new ServicePrincipal('lambda.amazonaws.com'),
            managedPolicies: [
                ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaVPCAccessExecutionRole'),
            ],
        });

        // Grant permissions to read from the model table
        litellmSyncRole.addToPrincipalPolicy(new PolicyStatement({
            effect: Effect.ALLOW,
            actions: ['dynamodb:Scan', 'dynamodb:GetItem'],
            resources: [`arn:${config.partition}:dynamodb:${config.region}:${config.accountNumber}:table/*`],
        }));

        // Grant access to SSM parameters
        litellmSyncRole.addToPrincipalPolicy(new PolicyStatement({
            effect: Effect.ALLOW,
            actions: ['ssm:GetParameter'],
            resources: [`arn:${config.partition}:ssm:${config.region}:${config.accountNumber}:parameter${config.deploymentPrefix}/*`],
        }));

        // Grant access to management key secret
        litellmSyncRole.addToPrincipalPolicy(new PolicyStatement({
            effect: Effect.ALLOW,
            actions: ['secretsmanager:GetSecretValue'],
            resources: [`arn:${config.partition}:secretsmanager:${config.region}:${config.accountNumber}:secret:*`],
        }));

        // Grant IAM access for SSL cert validation
        litellmSyncRole.addToPrincipalPolicy(new PolicyStatement({
            effect: Effect.ALLOW,
            actions: ['iam:GetServerCertificate'],
            resources: ['*'],
        }));

        // Create the sync Lambda
        const litellmModelSyncLambda = new Function(scope, 'LiteLLMModelSync', {
            runtime: getPythonRuntime(),
            handler: 'models.litellm_model_sync.handler',
            code: Code.fromAsset(lambdaPath),
            layers: lambdaLayers,
            environment: {
                MODEL_TABLE_NAME: modelTableName,
                MANAGEMENT_KEY_NAME: managementKeyName,
                LISA_API_URL_PS_NAME: `${config.deploymentPrefix}/lisaServeRestApiUri`,
                REST_API_VERSION: 'v2',
                RESTAPI_SSL_CERT_ARN: config.restApiConfig?.sslCertIamArn ?? '',
            },
            role: litellmSyncRole,
            vpc: vpc.vpc,
            vpcSubnets: vpc.subnetSelection,
            securityGroups: securityGroups,
            timeout: Duration.minutes(10),
            description: 'Sync all models from DynamoDB to LiteLLM when the LiteLLM database is created or updated',
        });

        // Create custom resource provider
        const syncProvider = new Provider(scope, 'LiteLLMModelSyncProvider', {
            onEventHandler: litellmModelSyncLambda,
        });

        // Create custom resource that triggers on LiteLLM DB create/update
        const syncResource = new CustomResource(scope, 'LiteLLMModelSyncResource', {
            serviceToken: syncProvider.serviceToken,
            properties: { timestamp: new Date().toISOString() },  // Force re-run on every deployment
        });

        // Ensure the sync runs after the REST API and database are available
        syncResource.node.addDependency(this.restApi);
        syncResource.node.addDependency(litellmDb);
    }

}

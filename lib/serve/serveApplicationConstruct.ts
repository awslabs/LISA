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
import { Stack, StackProps } from 'aws-cdk-lib';
import { AttributeType, BillingMode, ITable, Table, TableEncryption } from 'aws-cdk-lib/aws-dynamodb';
import { Credentials, DatabaseInstance, DatabaseInstanceEngine } from 'aws-cdk-lib/aws-rds';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';

import { FastApiContainer } from '../api-base/fastApiContainer';
import { createCdkId } from '../core/utils';
import { Vpc } from '../networking/vpc';
import { BaseProps } from '../schema';
import { Effect, Policy, PolicyStatement } from 'aws-cdk-lib/aws-iam';
import { Secret } from 'aws-cdk-lib/aws-secretsmanager';
import { SecurityGroupEnum } from '../core/iam/SecurityGroups';
import { SecurityGroupFactory } from '../networking/vpc/security-group-factory';
import { REST_API_PATH } from '../util';

export type LisaServeApplicationProps = {
    vpc: Vpc;
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

    /**
   * @param {Stack} scope - The parent or owner of the construct.
   * @param {string} id - The unique identifier for the construct within its scope.
   * @param {LisaServeApplicationProps} props - Properties for the Stack.
   */
    constructor (scope: Stack, id: string, props: LisaServeApplicationProps) {
        super(scope, id);
        const { config, vpc } = props;

        let tokenTable;
        if (config.restApiConfig.internetFacing) {
            // Create DynamoDB Table for enabling API token usage
            tokenTable = new Table(scope, 'TokenTable', {
                tableName: `${config.deploymentName}-LISAApiTokenTable`,
                partitionKey: {
                    name: 'token',
                    type: AttributeType.STRING,
                },
                billingMode: BillingMode.PAY_PER_REQUEST,
                encryption: TableEncryption.AWS_MANAGED,
                removalPolicy: config.removalPolicy,
            });
        }
        this.tokenTable = tokenTable;

        // Create REST API
        const restApi = new FastApiContainer(scope, 'RestApi', {
            apiName: 'REST',
            config: config,
            resourcePath: REST_API_PATH,
            securityGroup: vpc.securityGroups.restApiAlbSg,
            tokenTable: tokenTable,
            vpc: vpc,
        });

        // Use a stable name for the management key secret
        const managementKeySecret = new Secret(scope, createCdkId([scope.node.id, 'managementKeySecret']), {
            secretName: `${config.deploymentName}-lisa-management-key`, // Use stable name based on deployment
            description: 'LISA management key secret',
            generateSecretString: {
                excludePunctuation: true,
                passwordLength: 16
            },
            removalPolicy: config.removalPolicy
        });

        // const commonLambdaLayer = LayerVersion.fromLayerVersionArn(
        //     scope,
        //     'base-common-lambda-layer',
        //     StringParameter.valueForStringParameter(scope, `${config.deploymentPrefix}/layerVersion/common`),
        // );

        // const rotateManagementKeyLambdaId = createCdkId([id, 'RotateManagementKeyLambda'])
        // const rotateManagementKeyLambda = new Function(scope, rotateManagementKeyLambdaId, {
        //     deadLetterQueueEnabled: true,
        //     deadLetterQueue: new Queue(scope, 'RotateManagementKeyLambdaDLQ', {
        //         queueName: 'RotateManagementKeyLambdaDLQ',
        //         enforceSSL: true,
        //     }),
        //     functionName: rotateManagementKeyLambdaId,
        //     runtime: config.lambdaConfig.pythonRuntime,
        //     handler: 'management_key.rotate_management_key',
        //     code: Code.fromAsset('./lambda/'),
        //     timeout: Duration.minutes(1),
        //     memorySize: 1024,
        //     environment: {
        //         MANAGEMENT_KEY_NAME: managementKeySecret.secretName
        //     },
        //     layers: [commonLambdaLayer],
        //     vpc: props.vpc.vpc,
        // });

        // managementKeySecret.grantRead(rotateManagementKeyLambda);

        // new RotationSchedule(scope, createCdkId([id, 'RotateManagementRotationSchedule']), {
        //     secret: managementKeySecret,
        //     rotationLambda: rotateManagementKeyLambda,
        //     automaticallyAfter: Duration.days(1), // Rotate every 30 days
        //   });

        // You can now use the `secret` variable to access the created secret
        // For example, you might output the secret's ARN for reference
        // new CfnOutput(scope, createCdkId([id, 'RotateManagementKey']), {
        //     value: managementKeySecret.secretArn,
        //     description: 'The ARN of the secret',
        // });

        const managementKeySecretNameStringParameter = new StringParameter(scope, createCdkId(['ManagementKeySecretName']), {
            parameterName: `${config.deploymentPrefix}/managementKeySecretName`,
            stringValue: managementKeySecret.secretName,
        });
        restApi.container.addEnvironment('MANAGEMENT_KEY_NAME', managementKeySecretNameStringParameter.stringValue);

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
            securityGroups: [litellmDbSg],
            removalPolicy: config.removalPolicy,
        });

        const litellmDbPasswordSecret = litellmDb.secret!;
        const litellmDbConnectionInfoPs = new StringParameter(scope, createCdkId([connectionParamName, 'StringParameter']), {
            parameterName: `${config.deploymentPrefix}/${connectionParamName}`,
            stringValue: JSON.stringify({
                username: username,
                passwordSecretId: litellmDbPasswordSecret.secretName,
                dbHost: litellmDb.dbInstanceEndpointAddress,
                dbName: config.restApiConfig.rdsConfig.dbName,
                dbPort: config.restApiConfig.rdsConfig.dbPort,
            }),
        });
        litellmDbPasswordSecret.grantRead(restApi.taskRole);
        litellmDbConnectionInfoPs.grantRead(restApi.taskRole);
        restApi.container.addEnvironment('LITELLM_DB_INFO_PS_NAME', litellmDbConnectionInfoPs.parameterName);
        if (config.region.includes('iso')){
            const ca_bundle = config.certificateAuthorityBundle ?? '';
            restApi.container.addEnvironment('SSL_CERT_DIR', '/etc/pki/tls/certs');
            restApi.container.addEnvironment('SSL_CERT_FILE', ca_bundle);
            restApi.container.addEnvironment('REQUESTS_CA_BUNDLE', ca_bundle);
            restApi.container.addEnvironment('CURL_CA_BUNDLE', ca_bundle);
            restApi.container.addEnvironment('AWS_CA_BUNDLE', ca_bundle);
        }

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

        this.modelsPs.grantRead(restApi.taskRole);
        // Add parameter as container environment variable for both RestAPI and RagAPI
        restApi.container.addEnvironment('REGISTERED_MODELS_PS_NAME', this.modelsPs.parameterName);
        restApi.node.addDependency(this.modelsPs);

        // Additional permissions for REST API Role
        const invocation_permissions = new Policy(scope, 'ModelInvokePerms', {
            statements: [
                new PolicyStatement({
                    effect: Effect.ALLOW,
                    actions: [
                        'bedrock:InvokeModel',
                        'bedrock:InvokeModelWithResponseStream',
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
        restApi.taskRole.attachInlinePolicy(invocation_permissions);

        // Update
        this.restApi = restApi;
    }
}

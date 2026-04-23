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

import { IAuthorizer, IRestApi, RestApi } from 'aws-cdk-lib/aws-apigateway';
import { ISecurityGroup } from 'aws-cdk-lib/aws-ec2';
import { Construct } from 'constructs';
import { Vpc } from '../networking/vpc';
import { AmiHardwareType } from '../schema/cdk';
import { APP_MANAGEMENT_KEY, BaseProps, Config, ECSConfig, Ec2Metadata, EcsSourceType } from '../schema';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { Duration, RemovalPolicy, StackProps } from 'aws-cdk-lib';
import { createCdkId } from '../core/utils';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import { getPythonRuntime, PythonLambdaFunction, registerAPIEndpoint } from '../api-base/utils';
import * as iam from 'aws-cdk-lib/aws-iam';
import { definePythonLambda, getPythonLambdaLayers, MCP_WORKBENCH_PATH } from '../util';
import { WORKBENCH_CONTAINER_MEMORY_RESERVATION, WORKBENCH_CONTAINER_MEMORY_LIMIT } from '../api-base/fastApiContainer';
import { defaultMcpWorkbenchHostnameFromServeApiDomain } from './mcpWorkbenchDomain';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import { ECSCluster, ECSTasks } from '../api-base/ecsCluster';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import { BlockPublicAccess, BucketEncryption } from 'aws-cdk-lib/aws-s3';
import { Secret } from 'aws-cdk-lib/aws-secretsmanager';

export type McpWorkbenchConstructProps = {
    bucketAccessLogsBucket: s3.IBucket;
    restApiId: string;
    rootResourceId: string;
    securityGroups: ISecurityGroup[];
    vpc: Vpc;
    authorizer?: IAuthorizer;
} & BaseProps & StackProps;

export class McpWorkbenchConstruct extends Construct {
    public readonly workbenchBucket: s3.Bucket;

    constructor (scope: Construct, id: string, props: McpWorkbenchConstructProps) {
        super(scope, id);

        const { authorizer, bucketAccessLogsBucket, config, restApiId, rootResourceId, securityGroups, vpc } = props;

        const lambdaLayers = getPythonLambdaLayers(this, config, ['common', 'fastapi'], 'McpWorkbench');

        const restApi = RestApi.fromRestApiAttributes(this, 'RestApi', {
            restApiId: restApiId,
            rootResourceId: rootResourceId,
        });

        const workbenchBucket = this.createWorkbenchBucket(scope, config, bucketAccessLogsBucket);
        this.createWorkbenchApi(restApi, config, vpc, securityGroups, workbenchBucket, lambdaLayers, authorizer);

        if (config.deployMcpWorkbench) {
            // The workbench ECS service only needs the third-party `common` layer (not lisa-shared).
            const commonLambdaLayer = lambda.LayerVersion.fromLayerVersionArn(
                this,
                'mcp-common-lambda-layer-ecs',
                ssm.StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/layerVersion/common`),
            );
            this.createWorkbenchService(config, vpc, commonLambdaLayer);
        }
    }

    private buildMcpWorkbenchBuildArgs (config: Config): Record<string, string> {
        const buildArgs: Record<string, string> = {
            BASE_IMAGE: config.baseImage,
            PYPI_INDEX_URL: config.pypiConfig.indexUrl,
            PYPI_TRUSTED_HOST: config.pypiConfig.trustedHost,
        };
        if (config.mcpWorkbenchBuildConfig) {
            Object.entries(config.mcpWorkbenchBuildConfig).forEach(([key, value]) => {
                if (value) {
                    buildArgs[key] = value;
                }
            });
        }
        return buildArgs;
    }

    private buildWorkbenchEcsConfig (config: Config): ECSConfig {
        const o = config.mcpWorkbenchEcsConfig ?? {};
        const instanceType = o.instanceType ?? 'm5.xlarge';
        // Workbench uses its own ALB; never reuse restApiConfig.domainName (that name resolves to the Serve ALB).
        // mcpWorkbenchRestApiConfig mirrors restApiConfig for YAML parity; mcpWorkbenchEcsConfig.domainName remains supported.
        const workbenchDomainName =
            config.mcpWorkbenchRestApiConfig?.domainName ??
            o.domainName ??
            defaultMcpWorkbenchHostnameFromServeApiDomain(config.restApiConfig.domainName ?? undefined) ??
            null;
        const workbenchSslCertArn =
            config.mcpWorkbenchRestApiConfig?.sslCertIamArn ??
            o.sslCertIamArn ??
            config.restApiConfig.sslCertIamArn ??
            null;
        return {
            amiHardwareType: AmiHardwareType.STANDARD,
            autoScalingConfig: {
                blockDeviceVolumeSize: o.blockDeviceVolumeSize ?? 50,
                minCapacity: o.minCapacity ?? 1,
                maxCapacity: o.maxCapacity ?? 5,
                cooldown: o.cooldown ?? 60,
                defaultInstanceWarmup: 60,
                metricConfig: {
                    albMetricName: 'RequestCountPerTarget',
                    targetValue: 1000,
                    duration: 60,
                    estimatedInstanceWarmup: 30,
                },
            },
            buildArgs: this.buildMcpWorkbenchBuildArgs(config),
            tasks: {},
            containerMemoryBuffer: 0,
            instanceType,
            internetFacing: config.restApiConfig.internetFacing,
            loadBalancerConfig: {
                healthCheckConfig: {
                    path: '/health',
                    interval: 60,
                    timeout: 30,
                    healthyThresholdCount: 2,
                    unhealthyThresholdCount: 3,
                },
                domainName: workbenchDomainName,
                sslCertIamArn: workbenchSslCertArn,
            },
        };
    }

    private buildWorkbenchClusterEnvironment (config: Config, instanceType: string, managementKeyName: string | undefined): Record<string, string> {
        const environment: Record<string, string> = {
            LOG_LEVEL: config.logLevel,
            AWS_REGION: config.region,
            AWS_REGION_NAME: config.region,
            THREADS: Ec2Metadata.get(instanceType).vCpus.toString(),
        };
        if (config.authConfig) {
            environment.USE_AUTH = 'true';
            environment.AUTHORITY = config.authConfig.authority;
            environment.CLIENT_ID = config.authConfig.clientId;
            environment.ADMIN_GROUP = config.authConfig.adminGroup;
            environment.USER_GROUP = config.authConfig.userGroup;
            environment.JWT_GROUPS_PROP = config.authConfig.jwtGroupsProperty;
            environment.MANAGEMENT_KEY_NAME = managementKeyName!;
        } else {
            environment.USE_AUTH = 'false';
        }
        if (config.region.includes('iso')) {
            environment.SSL_CERT_DIR = '/etc/pki/tls/certs';
            environment.SSL_CERT_FILE = config.certificateAuthorityBundle;
            environment.REQUESTS_CA_BUNDLE = config.certificateAuthorityBundle;
            environment.AWS_CA_BUNDLE = config.certificateAuthorityBundle;
            environment.CURL_CA_BUNDLE = config.certificateAuthorityBundle;
        }
        return environment;
    }

    private getMcpWorkbenchTaskDefinition (config: Config) {
        const mcpWorkbenchImage = config.mcpWorkbenchConfig || {
            baseImage: config.baseImage,
            path: MCP_WORKBENCH_PATH,
            type: EcsSourceType.ASSET,
        };

        return {
            environment: {
                RCLONE_CONFIG_S3_REGION: config.region,
                MCPWORKBENCH_BUCKET: [config.deploymentName, config.deploymentStage, 'MCPWorkbench', config.accountNumber].join('-').toLowerCase(),
                CORS_ORIGINS: config.mcpWorkbenchCorsOrigins,
            },
            containerConfig: {
                image: mcpWorkbenchImage,
                healthCheckConfig: {
                    command: ['CMD-SHELL', 'exit 0'],
                    interval: 10,
                    startPeriod: 30,
                    timeout: 5,
                    retries: 3,
                },
                environment: {},
                sharedMemorySize: 0,
                privileged: true,
            },
            containerMemoryReservationMiB: WORKBENCH_CONTAINER_MEMORY_RESERVATION,
            memoryLimitMiB: WORKBENCH_CONTAINER_MEMORY_LIMIT,
            applicationTarget: { port: 8000 },
        };
    }

    private createWorkbenchApi (restApi: IRestApi, config: Config, vpc: Vpc, securityGroups: ISecurityGroup[], workbenchBucket: s3.Bucket, lambdaLayers: lambda.ILayerVersion[], authorizer?: IAuthorizer) {

        const env = {
            ADMIN_GROUP: config.authConfig?.adminGroup || '',
            WORKBENCH_BUCKET: workbenchBucket.bucketName
        };

        // Create API Lambda functions
        const apis: PythonLambdaFunction[] = [{
            name: 'list',
            resource: 'mcp_workbench',
            description: 'Lists available MCP Workbench tools',
            method: 'GET',
            environment: env,
            path: 'mcp-workbench'
        }, {
            name: 'create',
            resource: 'mcp_workbench',
            description: 'Create MCP Workbench tools',
            method: 'POST',
            environment: env,
            path: 'mcp-workbench'
        }, {
            name: 'read',
            resource: 'mcp_workbench',
            description: 'Get MCP Workbench tool',
            method: 'GET',
            environment: env,
            path: 'mcp-workbench/{toolId}'
        }, {
            name: 'update',
            resource: 'mcp_workbench',
            description: 'Update MCP Workbench tool',
            method: 'PUT',
            environment: env,
            path: 'mcp-workbench/{toolId}'
        }, {
            name: 'delete',
            resource: 'mcp_workbench',
            description: 'Delete MCP Workbench tool',
            method: 'DELETE',
            environment: env,
            path: 'mcp-workbench/{toolId}'
        }, {
            name: 'validate_syntax',
            resource: 'mcp_workbench',
            description: 'Validate Python code syntax',
            method: 'POST',
            environment: env,
            path: 'mcp-workbench/validate-syntax'
        }];

        // Create IAM role for Lambda
        const lambdaRole = new iam.Role(this, 'LambdaExecutionRole', {
            assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
            description: 'IAM role for Lambda function execution',
            inlinePolicies: {
                'EC2NetworkInterfaces': new iam.PolicyDocument({
                    statements: [
                        new iam.PolicyStatement({
                            effect: iam.Effect.ALLOW,
                            actions: ['ec2:CreateNetworkInterface', 'ec2:DescribeNetworkInterfaces', 'ec2:DeleteNetworkInterface'],
                            resources: ['*'],
                        }),
                    ],
                }),
            },
        });

        // Attach AWSLambdaBasicExecutionRole policy to the role
        lambdaRole.addManagedPolicy(
            iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole')
        );

        apis.forEach((f) => {
            const lambdaFunction = registerAPIEndpoint(
                this,
                restApi,
                config,
                lambdaLayers,
                f,
                getPythonRuntime(),
                vpc,
                securityGroups,
                authorizer,
                lambdaRole,
            );

            // Grant S3 permissions based on function type
            if (['validate_syntax'].includes(f.name)) {
                // No S3 permissions needed for syntax validation
            } else if (f.method === 'POST' || f.method === 'PUT') {
                workbenchBucket.grantWrite(lambdaFunction);
            } else if (f.method === 'GET') {
                workbenchBucket.grantRead(lambdaFunction);
            } else if (f.method === 'DELETE') {
                workbenchBucket.grantDelete(lambdaFunction);
            }
        });
    }

    private createWorkbenchBucket (scope: Construct, config: Config, bucketAccessLogsBucket: s3.IBucket): s3.Bucket {
        return new s3.Bucket(scope, createCdkId(['LISA', 'MCPWorkbench', config.deploymentName, config.deploymentStage]), {
            bucketName: [config.deploymentName, config.deploymentStage, 'MCPWorkbench', config.accountNumber].join('-').toLowerCase(),
            removalPolicy: config.removalPolicy,
            autoDeleteObjects: config.removalPolicy === RemovalPolicy.DESTROY,
            enforceSSL: true,
            serverAccessLogsBucket: bucketAccessLogsBucket,
            serverAccessLogsPrefix: 'logs/mcpworkbench-bucket/',
            eventBridgeEnabled: true,
            blockPublicAccess: BlockPublicAccess.BLOCK_ALL,
            encryption: BucketEncryption.S3_MANAGED
        });
    }

    private createWorkbenchService (config: Config, vpc: Vpc, commonLambdaLayer: lambda.ILayerVersion) {
        const ecsConfig = this.buildWorkbenchEcsConfig(config);
        const managementKeyName = config.authConfig
            ? ssm.StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/${APP_MANAGEMENT_KEY}`)
            : undefined;
        const environment = this.buildWorkbenchClusterEnvironment(config, ecsConfig.instanceType, managementKeyName);
        // Same token table as Serve REST API (SSM from Api Base); required for ApiTokenAuthorizer in auth middleware
        environment.TOKEN_TABLE_NAME = ssm.StringParameter.valueForStringParameter(
            this,
            `${config.deploymentPrefix}/tokenTableName`,
        );

        const workbenchCluster = new ECSCluster(this, 'McpWorkbenchDedicatedEcs', {
            identifier: 'McpWorkbenchDedicated',
            ecsConfig,
            config,
            securityGroup: vpc.securityGroups.restApiAlbSg,
            vpc,
            environment,
        });

        const mcpWorkbenchTaskDefinition = this.getMcpWorkbenchTaskDefinition(config);
        workbenchCluster.addTask(ECSTasks.MCPWORKBENCH, mcpWorkbenchTaskDefinition);

        const tokenTableNameParameter = ssm.StringParameter.fromStringParameterName(
            this,
            createCdkId(['McpWorkbench', 'TokenTableNameParameter']),
            `${config.deploymentPrefix}/tokenTableName`,
        );
        const tokenTable = dynamodb.Table.fromTableName(
            this,
            createCdkId(['McpWorkbench', 'TokenTable']),
            tokenTableNameParameter.stringValue,
        );
        const mcpWorkbenchTaskRole = workbenchCluster.taskRoles[ECSTasks.MCPWORKBENCH];
        if (mcpWorkbenchTaskRole) {
            tokenTable.grantReadData(mcpWorkbenchTaskRole);
        }

        this.createS3EventHandler(config, vpc, workbenchCluster.endpointUrl, commonLambdaLayer, managementKeyName);

        new ssm.StringParameter(this, 'McpWorkbenchHostedEndpoint', {
            parameterName: `${config.deploymentPrefix}/mcpWorkbench/endpoint`,
            stringValue: workbenchCluster.endpointUrl,
            description: 'Base URL for hosted MCP Workbench HTTP server (MCP path /v2/mcp/)',
        });
    }

    private createS3EventHandler (
        config: any,
        vpc: Vpc,
        workbenchEndpointUrl: string,
        commonLambdaLayer: lambda.ILayerVersion,
        managementKeyName?: string,
    ) {
        const policyStatements: iam.PolicyStatement[] = [
            new iam.PolicyStatement({
                effect: iam.Effect.ALLOW,
                actions: [
                    'logs:CreateLogGroup',
                    'logs:CreateLogStream',
                    'logs:PutLogEvents'
                ],
                resources: [`arn:${config.partition}:logs:*:*:*`]
            }),
        ];
        if (managementKeyName) {
            policyStatements.push(new iam.PolicyStatement({
                effect: iam.Effect.ALLOW,
                actions: ['secretsmanager:GetSecretValue'],
                resources: [
                    `${Secret.fromSecretNameV2(this, createCdkId(['McpWorkbench', 'S3EventHandlerMgmtKey']), managementKeyName).secretArn}-??????`,
                ],
            }));
        }

        const s3EventHandlerRole = new iam.Role(this, 'S3EventHandlerRole', {
            assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
            managedPolicies: [
                iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaVPCAccessExecutionRole'),
            ],
            inlinePolicies: {
                'S3EventHandlerPolicy': new iam.PolicyDocument({
                    statements: policyStatements,
                })
            }
        });

        const s3EventHandlerLambda = definePythonLambda(this, 'S3EventHandlerLambda', {
            handlerDir: 'mcp_workbench',
            entry: 's3_event_handler.handler',
            config,
            layers: [commonLambdaLayer],
            role: s3EventHandlerRole,
            vpc,
            securityGroups: [vpc.securityGroups.lambdaSg],
            timeout: Duration.minutes(2),
            environment: {
                MCP_WORKBENCH_ENDPOINT: workbenchEndpointUrl,
                WORKBENCH_RESCAN_DELAY_SECONDS: '5',
                MCP_WORKBENCH_RESCAN_PATH: 'v2/mcp/rescan',
                ...(managementKeyName ? { MANAGEMENT_KEY_NAME: managementKeyName } : {}),
            },
        });

        const rescanMcpWorkbenchRule = new events.Rule(this, 'RescanMCPWorkbenchRule', {
            eventPattern: {
                source: ['aws.s3', 'debug'],
                detailType: [
                    'Object Created',
                    'Object Deleted'
                ],
                detail: {
                    bucket: {
                        name: [[config.deploymentName, config.deploymentStage, 'MCPWorkbench', config.accountNumber].join('-').toLowerCase()]
                    }
                }
            },
        });

        rescanMcpWorkbenchRule.addTarget(new targets.LambdaFunction(s3EventHandlerLambda, {
            retryAttempts: 2,
            maxEventAge: Duration.minutes(5)
        }));
    }
}

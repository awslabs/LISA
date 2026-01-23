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
import { BaseProps, Config, EcsSourceType } from '../schema';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { Duration, RemovalPolicy, StackProps } from 'aws-cdk-lib';
import { createCdkId } from '../core/utils';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import { getPythonRuntime, PythonLambdaFunction, registerAPIEndpoint } from '../api-base/utils';
import * as iam from 'aws-cdk-lib/aws-iam';
import { LAMBDA_PATH, MCP_WORKBENCH_PATH } from '../util';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import { ECSCluster, ECSTasks } from '../api-base/ecsCluster';
import { Ec2Service } from 'aws-cdk-lib/aws-ecs';
import { BucketEncryption } from 'aws-cdk-lib/aws-s3';

export type McpWorkbenchConstructProps = {
    restApiId: string;
    rootResourceId: string;
    securityGroups: ISecurityGroup[];
    vpc: Vpc;
    apiCluster: ECSCluster;
    authorizer?: IAuthorizer;
} & BaseProps & StackProps;

export class McpWorkbenchConstruct extends Construct {
    public readonly workbenchBucket: s3.Bucket;

    constructor (scope: Construct, id: string, props: McpWorkbenchConstructProps) {
        super(scope, id);

        const { authorizer, config, restApiId, rootResourceId, securityGroups, vpc, apiCluster } = props;

        // Get common layer based on arn from SSM due to issues with cross stack references
        const commonLambdaLayer = lambda.LayerVersion.fromLayerVersionArn(
            this,
            'mcp-common-lambda-layer',
            ssm.StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/layerVersion/common`),
        );

        const fastapiLambdaLayer = lambda.LayerVersion.fromLayerVersionArn(
            this,
            'mcp-fastapi-lambda-layer',
            ssm.StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/layerVersion/fastapi`),
        );

        const restApi = RestApi.fromRestApiAttributes(this, 'RestApi', {
            restApiId: restApiId,
            rootResourceId: rootResourceId,
        });

        const lambdaLayers = [commonLambdaLayer, fastapiLambdaLayer];

        const workbenchBucket = this.createWorkbenchBucket(scope, config);
        this.createWorkbenchApi(restApi, config, vpc, securityGroups, workbenchBucket, lambdaLayers, authorizer);
        this.createWorkbenchService(apiCluster, config, vpc);
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

        const lambdaPath = config.lambdaPath || LAMBDA_PATH;
        apis.forEach((f) => {
            const lambdaFunction = registerAPIEndpoint(
                this,
                restApi,
                lambdaPath,
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

    private createWorkbenchBucket (scope: Construct, config: Config): s3.Bucket {
        const bucketAccessLogsBucket = s3.Bucket.fromBucketArn(scope, 'BucketAccessLogsBucket',
            ssm.StringParameter.valueForStringParameter(scope, `${config.deploymentPrefix}/bucket/bucket-access-logs`),
        );

        return new s3.Bucket(scope, createCdkId(['LISA', 'MCPWorkbench', config.deploymentName, config.deploymentStage]), {
            bucketName: [config.deploymentName, config.deploymentStage, 'MCPWorkbench', config.accountNumber].join('-').toLowerCase(),
            removalPolicy: config.removalPolicy,
            autoDeleteObjects: config.removalPolicy === RemovalPolicy.DESTROY,
            enforceSSL: true,
            serverAccessLogsBucket: bucketAccessLogsBucket,
            serverAccessLogsPrefix: 'logs/mcpworkbench-bucket/',
            eventBridgeEnabled: true,
            encryption: BucketEncryption.S3_MANAGED
        });
    }

    private createWorkbenchService (apiCluster: ECSCluster, config: Config, vpc: Vpc) {

        const mcpWorkbenchImage = config.mcpWorkbenchConfig || {
            baseImage: config.baseImage,
            path: MCP_WORKBENCH_PATH,
            type: EcsSourceType.ASSET
        };

        const mcpWorkbenchTaskDefinition = {
            environment: {
                RCLONE_CONFIG_S3_REGION: config.region,
                MCPWORKBENCH_BUCKET: [config.deploymentName, config.deploymentStage, 'MCPWorkbench', config.accountNumber].join('-').toLowerCase(),
            },
            containerConfig: {
                image: mcpWorkbenchImage,
                healthCheckConfig: {
                    command: ['CMD-SHELL', 'exit 0'],
                    interval: 10,
                    startPeriod: 30,
                    timeout: 5,
                    retries: 3
                },
                environment: {},
                sharedMemorySize: 0,
                // Use SYS_ADMIN capability instead of full privileged mode
                // Required for FUSE mounts (rclone S3 mount)
                // The mcpworkbench application itself runs as non-root user (lisa)
                privileged: false,
                linuxCapabilities: {
                    add: ['SYS_ADMIN']
                }
            },
            containerMemoryReservationMiB: 1024,
            applicationTarget: {
                port: 8000,
                priority: 80,
                conditions: [{
                    type: 'pathPatterns' as const,
                    values: ['/v2/mcp/*']
                }]
            }
        };

        const { service } = apiCluster.addTask(ECSTasks.MCPWORKBENCH, mcpWorkbenchTaskDefinition);

        this.createS3EventHandler(config, service, vpc);
    }

    private createS3EventHandler (config: any, workbenchService: Ec2Service, vpc: Vpc) {
        const s3EventHandlerRole = new iam.Role(this, 'S3EventHandlerRole', {
            assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
            managedPolicies: [
                iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaVPCAccessExecutionRole'),
            ],
            inlinePolicies: {
                'S3EventHandlerPolicy': new iam.PolicyDocument({
                    statements: [
                        new iam.PolicyStatement({
                            effect: iam.Effect.ALLOW,
                            actions: [
                                'logs:CreateLogGroup',
                                'logs:CreateLogStream',
                                'logs:PutLogEvents'
                            ],
                            resources: [`arn:${config.partition}:logs:*:*:*`]
                        }),
                        new iam.PolicyStatement({
                            effect: iam.Effect.ALLOW,
                            actions: [
                                'ecs:UpdateService',
                                'ecs:DescribeServices',
                                'ecs:DescribeClusters'
                            ],
                            resources: [
                                `arn:${config.partition}:ecs:${config.region}:*:cluster/${workbenchService.cluster.clusterName}*`,
                                `arn:${config.partition}:ecs:${config.region}:*:service/${workbenchService.cluster.clusterName}*/${workbenchService.serviceName}*`
                            ]
                        }),
                        new iam.PolicyStatement({
                            effect: iam.Effect.ALLOW,
                            actions: [
                                'ssm:GetParameter'
                            ],
                            resources: [
                                `arn:${config.partition}:ssm:${config.region}:*:parameter${config.deploymentPrefix}/deploymentName`
                            ]
                        })
                    ]
                })
            }
        });

        const s3EventHandlerLambda = new lambda.Function(this, 'S3EventHandlerLambda', {
            runtime: getPythonRuntime(),
            handler: 'mcp_workbench.s3_event_handler.handler',
            code: lambda.Code.fromAsset(config.lambdaPath ?? LAMBDA_PATH),
            timeout: Duration.minutes(2),
            role: s3EventHandlerRole,
            vpc: vpc.vpc,
            vpcSubnets: vpc.subnetSelection,
            environment: {
                DEPLOYMENT_PREFIX: config.deploymentPrefix!,
                API_NAME: 'MCPWorkbench',
                ECS_CLUSTER_NAME: workbenchService.cluster.clusterName,
                MCPWORKBENCH_SERVICE_NAME: workbenchService.serviceName
            }
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

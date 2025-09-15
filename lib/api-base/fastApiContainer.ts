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

import { CfnOutput, Duration } from 'aws-cdk-lib';
import { ITable } from 'aws-cdk-lib/aws-dynamodb';
import { ISecurityGroup } from 'aws-cdk-lib/aws-ec2';
import { AmiHardwareType, ContainerDefinition } from 'aws-cdk-lib/aws-ecs';
import { IRole } from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';
import { dump as yamlDump } from 'js-yaml';

import { ECSCluster, ECSTasks } from './ecsCluster';
import { BaseProps, Ec2Metadata, ECSConfig, EcsSourceType } from '../schema';
import { Vpc } from '../networking/vpc';
import { MCP_WORKBENCH_PATH, REST_API_PATH } from '../util';
import * as child_process from 'child_process';
import * as path from 'path';
import { letIfDefined } from '../util/common-functions';
import { Bucket } from 'aws-cdk-lib/aws-s3';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import { Effect, PolicyDocument, PolicyStatement, Role, ServicePrincipal } from 'aws-cdk-lib/aws-iam';
import { LAMBDA_PATH } from '../util';
import { getDefaultRuntime } from './utils';

// This is the amount of memory to buffer (or subtract off) from the total instance memory, if we don't include this,
// the container can have a hard time finding available RAM resources to start and the tasks will fail deployment
const INSTANCE_MEMORY_RESERVATION = 1024;
const SERVE_CONTAINER_MEMORY_RESERVATION = 1024 * 2;
const WORKBENCH_CONTAINER_MEMORY_RESERVATION = 1024;

/**
 * Properties for FastApiContainer Construct.
 *
 * @property {Vpc} vpc - The virtual private cloud (VPC).
 * @property {ISecurityGroup} securityGroup - The security groups of the application.
 */
type FastApiContainerProps = {
    apiName: string;
    resourcePath: string;
    securityGroup: ISecurityGroup;
    tokenTable: ITable | undefined;
    vpc: Vpc;
} & BaseProps;

/**
 * FastApiContainer Construct.
 */
export class FastApiContainer extends Construct {
    /** Map of all container definitions by identifier */
    public readonly containers: ContainerDefinition[] = [];

    /** Map of all task roles by identifier */
    public readonly taskRoles: Partial<Record<ECSTasks, IRole>> = {};

    /** FastAPI URL **/
    public readonly endpoint: string;

    /**
   * @param {Construct} scope - The parent or owner of the construct.
   * @param {string} id - The unique identifier for the construct within its scope.
   * @param {FastApiContainerProps} props - The properties of the construct.
   */
    constructor (scope: Construct, id: string, props: FastApiContainerProps) {
        super(scope, id);

        const { config, securityGroup, tokenTable, vpc } = props;
        const buildArgs: Record<string, string> | undefined = {
            BASE_IMAGE: config.baseImage,
            PYPI_INDEX_URL: config.pypiConfig.indexUrl,
            PYPI_TRUSTED_HOST: config.pypiConfig.trustedHost,
            LITELLM_CONFIG: yamlDump(config.litellmConfig),
        };
        const baseEnvironment: Record<string, string> = {
            LOG_LEVEL: config.logLevel,
            AWS_REGION: config.region,
            AWS_REGION_NAME: config.region, // for supporting SageMaker endpoints in LiteLLM
            THREADS: Ec2Metadata.get('m5.large').vCpus.toString(),
            LITELLM_KEY: config.litellmConfig.db_key,
            TIKTOKEN_CACHE_DIR: '/app/TIKTOKEN_CACHE'
        };

        if (config.restApiConfig.internetFacing) {
            baseEnvironment.USE_AUTH = 'true';
            baseEnvironment.AUTHORITY = config.authConfig!.authority;
            baseEnvironment.CLIENT_ID = config.authConfig!.clientId;
            baseEnvironment.ADMIN_GROUP = config.authConfig!.adminGroup;
            baseEnvironment.USER_GROUP = config.authConfig!.userGroup;
            baseEnvironment.JWT_GROUPS_PROP = config.authConfig!.jwtGroupsProperty;
        } else {
            baseEnvironment.USE_AUTH = 'false';
        }

        if (tokenTable) {
            baseEnvironment.TOKEN_TABLE_NAME = tokenTable.tableName;
        }

        // Pre-generate the tiktoken cache to ensure it does not attempt to fetch data from the internet at runtime.
        if (config.restApiConfig.imageConfig === undefined) {
            const cache_dir = path.join(REST_API_PATH, 'TIKTOKEN_CACHE');
            // Skip tiktoken cache generation in test environment
            if (process.env.NODE_ENV !== 'test') {
                try {
                    child_process.execSync(`python3 scripts/cache-tiktoken-for-offline.py ${cache_dir}`, { stdio: 'inherit' });
                } catch (error) {
                    console.warn('Failed to generate tiktoken cache:', error);
                    // Continue execution even if cache generation fails
                }
            }
        }

        const restApiImage = config.restApiConfig.imageConfig || {
            baseImage: config.baseImage,
            path: REST_API_PATH,
            type: EcsSourceType.ASSET
        };
        const instanceType = 'm5.large';
        const healthCheckConfig = {
            command: ['CMD-SHELL', 'exit 0'],
            interval: 10,
            startPeriod: 30,
            timeout: 5,
            retries: 3
        };
        const ecsConfig: ECSConfig = {
            amiHardwareType: AmiHardwareType.STANDARD,
            autoScalingConfig: {
                blockDeviceVolumeSize: 30,
                minCapacity: 1,
                maxCapacity: 5,
                cooldown: 60,
                defaultInstanceWarmup: 60,
                metricConfig: {
                    albMetricName: 'RequestCountPerTarget',
                    targetValue: 1000,
                    duration: 60,
                    estimatedInstanceWarmup: 30
                }
            },
            buildArgs,
            tasks: {
                [ECSTasks.REST]: {
                    environment: baseEnvironment,
                    containerConfig: {
                        image: restApiImage,
                        healthCheckConfig,
                        environment: {},
                        sharedMemorySize: 0
                    },
                    // set a softlimit of what we expect to use
                    containerMemoryReservationMiB: SERVE_CONTAINER_MEMORY_RESERVATION
                },
                [ECSTasks.MCPWORKBENCH]: {
                    environment: {...baseEnvironment,
                        RCLONE_CONFIG_S3_REGION: config.region,
                        MCPWORKBENCH_BUCKET: [config.deploymentName, config.deploymentStage, 'MCPWorkbench', config.accountNumber].join('-').toLowerCase(),
                    },
                    containerConfig: {
                        image: {
                            baseImage: config.baseImage,
                            path: MCP_WORKBENCH_PATH,
                            type: EcsSourceType.ASSET
                        },
                        healthCheckConfig,
                        environment: {},
                        sharedMemorySize: 0,
                        privileged: true
                    },
                    applicationTarget: {
                        port: 8000,
                        priority: 80,
                        conditions: [
                            { type: 'pathPatterns', values: ['/v2/mcp/*'] }
                        ]
                    },
                    containerMemoryReservationMiB: WORKBENCH_CONTAINER_MEMORY_RESERVATION,
                }
            },
            // reserve at least enough memory for each task and a buffer for the instance to use
            containerMemoryBuffer: Ec2Metadata.get(instanceType).memory - (INSTANCE_MEMORY_RESERVATION + SERVE_CONTAINER_MEMORY_RESERVATION + WORKBENCH_CONTAINER_MEMORY_RESERVATION),
            instanceType,
            internetFacing: config.restApiConfig.internetFacing,
            loadBalancerConfig: {
                healthCheckConfig: {
                    path: '/health',
                    interval: 60,
                    timeout: 30,
                    healthyThresholdCount: 2,
                    unhealthyThresholdCount: 10
                },
                domainName: config.restApiConfig.domainName,
                sslCertIamArn: config.restApiConfig?.sslCertIamArn ?? null,
            },
        };

        const apiCluster = new ECSCluster(scope, `${id}-ECSCluster`, {
            identifier: props.apiName,
            ecsConfig,
            config,
            securityGroup,
            vpc
        });

        // Create Lambda function to handle S3 events and trigger MCP Workbench service redeployment
        const s3EventHandlerRole = new Role(this, 'S3EventHandlerRole', {
            assumedBy: new ServicePrincipal('lambda.amazonaws.com'),
            inlinePolicies: {
                'S3EventHandlerPolicy': new PolicyDocument({
                    statements: [
                        new PolicyStatement({
                            effect: Effect.ALLOW,
                            actions: [
                                'logs:CreateLogGroup',
                                'logs:CreateLogStream',
                                'logs:PutLogEvents'
                            ],
                            resources: ['arn:aws:logs:*:*:*']
                        }),
                        new PolicyStatement({
                            effect: Effect.ALLOW,
                            actions: [
                                'ecs:UpdateService',
                                'ecs:DescribeServices',
                                'ecs:DescribeClusters'
                            ],
                            resources: [
                                `arn:aws:ecs:${config.region}:*:cluster/${config.deploymentName}-${props.apiName}*`,
                                `arn:aws:ecs:${config.region}:*:service/${config.deploymentName}-${props.apiName}*/MCPWORKBENCH*`
                            ]
                        }),
                        new PolicyStatement({
                            effect: Effect.ALLOW,
                            actions: [
                                'ssm:GetParameter'
                            ],
                            resources: [
                                `arn:aws:ssm:${config.region}:*:parameter${config.deploymentPrefix}/deploymentName`
                            ]
                        })
                    ]
                })
            }
        });

        const s3EventHandlerLambda = new lambda.Function(this, 'S3EventHandlerLambda', {
            runtime: getDefaultRuntime(),
            handler: 'mcp_workbench.s3_event_handler.handler',
            code: lambda.Code.fromAsset(config.lambdaPath ?? LAMBDA_PATH),
            timeout: Duration.minutes(2),
            role: s3EventHandlerRole,
            environment: {
                DEPLOYMENT_PREFIX: config.deploymentPrefix!,
                API_NAME: props.apiName,
                ECS_CLUSTER_NAME: `${config.deploymentName}-${props.apiName}`,
                MCPWORKBENCH_SERVICE_NAME: ECSTasks.MCPWORKBENCH
            }
        });

        // Create EventBridge rule to trigger Lambda when S3 objects are created/deleted
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

        if (tokenTable) {
            Object.entries(apiCluster.taskRoles).forEach(([, role]) => {
                tokenTable.grantReadData(role);
            });
        }

        letIfDefined(apiCluster.taskRoles.MCPWORKBENCH, (taskRole) => {
            const bucketName = [config.deploymentName, config.deploymentStage, 'MCPWorkbench', config.accountNumber].join('-').toLowerCase();
            const workbenchBucket = Bucket.fromBucketName(scope, 'MCPWorkbenchBucket', bucketName);
            workbenchBucket.grantRead(taskRole);
        });

        this.endpoint = apiCluster.endpointUrl;

        new StringParameter(scope, 'FastApiEndpoint', {
            parameterName: `${config.deploymentPrefix}/serve/endpoint`,
            stringValue: this.endpoint
        });

        // Update
        this.containers = Object.values(apiCluster.containers);
        this.taskRoles = apiCluster.taskRoles;

        // CFN output
        new CfnOutput(this, `${props.apiName}Url`, {
            value: apiCluster.endpointUrl,
        });
    }
}

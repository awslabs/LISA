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

import { Duration } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { BaseProps, EcsSourceType } from '../schema';
import { Vpc } from '../networking/vpc';
import { Ec2Service } from 'aws-cdk-lib/aws-ecs';
import { ECSCluster, ECSTasks } from '../api-base/ecsCluster';
import { MCP_WORKBENCH_PATH } from '../util';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import { Effect, PolicyDocument, PolicyStatement, Role, ServicePrincipal } from 'aws-cdk-lib/aws-iam';
import { LAMBDA_PATH } from '../util';
import { getDefaultRuntime } from '../api-base/utils';

export type McpWorkbenchServiceConstructProps = {
    vpc: Vpc;
    apiCluster: ECSCluster;
} & BaseProps;

export default class McpWorkbenchServiceConstruct extends Construct {
    public readonly service: Ec2Service;

    constructor (scope: Construct, id: string, props: McpWorkbenchServiceConstructProps) {
        super(scope, id);

        const { config, vpc, apiCluster } = props;

        const baseEnvironment: Record<string, string> = {
            LOG_LEVEL: config.logLevel,
            AWS_REGION: config.region,
            AWS_REGION_NAME: config.region,
            LITELLM_KEY: config.litellmConfig.db_key,
            OPENAI_API_KEY: config.litellmConfig.db_key,
            USE_AUTH: 'true',
            AUTHORITY: config.authConfig!.authority,
            CLIENT_ID: config.authConfig!.clientId,
            ADMIN_GROUP: config.authConfig!.adminGroup,
            USER_GROUP: config.authConfig!.userGroup,
            JWT_GROUPS_PROP: config.authConfig!.jwtGroupsProperty,
            RCLONE_CONFIG_S3_REGION: config.region,
            MCPWORKBENCH_BUCKET: [config.deploymentName, config.deploymentStage, 'MCPWorkbench', config.accountNumber].join('-').toLowerCase(),
        };

        const mcpWorkbenchImage = config.mcpWorkbenchConfig || {
            baseImage: config.baseImage,
            path: MCP_WORKBENCH_PATH,
            type: EcsSourceType.ASSET
        };

        const healthCheckConfig = {
            command: ['CMD-SHELL', 'exit 0'],
            interval: 10,
            startPeriod: 30,
            timeout: 5,
            retries: 3
        };

        const mcpWorkbenchTaskDefinition = {
            environment: baseEnvironment,
            containerConfig: {
                image: mcpWorkbenchImage,
                healthCheckConfig,
                environment: {},
                sharedMemorySize: 0,
                privileged: true
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

        const { service } = apiCluster.addTask(ECSTasks.MCPWORKBENCH, mcpWorkbenchTaskDefinition, 'REST');
        this.service = service;

        this.createS3EventHandler(config, service);
    }

    private createS3EventHandler (config: any, workbenchService: Ec2Service) {
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
                            resources: [`arn:${config.partition}:logs:*:*:*`]
                        }),
                        new PolicyStatement({
                            effect: Effect.ALLOW,
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
                        new PolicyStatement({
                            effect: Effect.ALLOW,
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
            runtime: getDefaultRuntime(),
            handler: 'mcp_workbench.s3_event_handler.handler',
            code: lambda.Code.fromAsset(config.lambdaPath ?? LAMBDA_PATH),
            timeout: Duration.minutes(2),
            role: s3EventHandlerRole,
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

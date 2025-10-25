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
import { Construct } from 'constructs';
import { BaseProps, EcsSourceType } from '../schema';
import McpWorkbenchConstruct from './mcpWorkbenchConstruct';
import { Vpc } from '../networking/vpc';
import { ICluster, Ec2Service, Ec2TaskDefinition, Protocol, LogDriver, HealthCheck } from 'aws-cdk-lib/aws-ecs';
import { MCP_WORKBENCH_PATH } from '../util';
import { dump as yamlDump } from 'js-yaml';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import { Effect, PolicyDocument, PolicyStatement, Role, ServicePrincipal } from 'aws-cdk-lib/aws-iam';
import { LAMBDA_PATH } from '../util';
import { getDefaultRuntime } from '../api-base/utils';
import { createCdkId } from '../core/utils';
import { CodeFactory } from '../util';
import { LogGroup, RetentionDays } from 'aws-cdk-lib/aws-logs';

import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { Port } from 'aws-cdk-lib/aws-ec2';
import { ListenerCondition } from 'aws-cdk-lib/aws-elasticloadbalancingv2';

export type McpWorkbenchStackProps = {
    vpc: Vpc;
    restApiId: string;
    rootResourceId: string;
    authorizerId: string;
    ecsCluster: ICluster;
    loadBalancer: any;
    listener: any;
} & BaseProps & StackProps;

export class McpWorkbenchStack extends Stack {
    constructor (scope: Construct, id: string, props: McpWorkbenchStackProps) {
        super(scope, id, props);

        const { config, vpc, restApiId, rootResourceId, authorizerId, ecsCluster, loadBalancer, listener } = props;

        // Import authorizer
        const authorizer = { authorizerId };

        new McpWorkbenchConstruct(this, 'McpWorkbench', {
            ...props,
            authorizer: authorizer as any,
            restApiId,
            rootResourceId,
            securityGroups: [vpc.securityGroups.ecsModelAlbSg],
        });

        // Create MCP Workbench ECS Service on shared cluster
        this.createMcpWorkbenchEcsService(config, vpc, ecsCluster, loadBalancer, listener);
    }

    private createMcpWorkbenchEcsService (config: any, vpc: Vpc, ecsCluster: ICluster, loadBalancer: any, listener: any) {
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

        const buildArgs: Record<string, string> = {
            BASE_IMAGE: config.baseImage,
            PYPI_INDEX_URL: config.pypiConfig.indexUrl,
            PYPI_TRUSTED_HOST: config.pypiConfig.trustedHost,
            LITELLM_CONFIG: yamlDump(config.litellmConfig),
        };

        // Create CloudWatch log group
        const logGroup = new LogGroup(this, createCdkId([config.deploymentPrefix, 'MCPWorkbench', 'LogGroup']), {
            logGroupName: `/aws/ecs/${config.deploymentName}-${config.deploymentStage}-MCPWorkbench`,
            retention: RetentionDays.ONE_WEEK,
            removalPolicy: config.removalPolicy
        });

        // Get task role from parameter store
        const taskRole = Role.fromRoleArn(
            this,
            'MCPWorkbenchTaskRole',
            StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/roles/MCPWORKBENCH`),
        );
        const executionRole = Role.fromRoleArn(
            this,
            'MCPWorkbenchExecutionRole',
            StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/roles/MCPWORKBENCHEX`),
        );

        // Create task definition
        const taskDefinition = new Ec2TaskDefinition(this, createCdkId(['MCPWorkbench', 'Ec2TaskDefinition']), {
            family: createCdkId([config.deploymentName, 'MCPWorkbench'], 32, 2),
            taskRole,
            executionRole,
        });

        // Grant CloudWatch logs write permissions
        logGroup.grantWrite(taskRole);
        logGroup.grantWrite(executionRole);

        const healthCheckConfig = {
            command: ['CMD-SHELL', 'exit 0'],
            interval: 10,
            startPeriod: 30,
            timeout: 5,
            retries: 3
        };

        const containerHealthCheck: HealthCheck = {
            command: healthCheckConfig.command,
            interval: Duration.seconds(healthCheckConfig.interval),
            startPeriod: Duration.seconds(healthCheckConfig.startPeriod),
            timeout: Duration.seconds(healthCheckConfig.timeout),
            retries: healthCheckConfig.retries,
        };

        const image = CodeFactory.createImage(mcpWorkbenchImage, this, 'MCPWorkbench', buildArgs);

        taskDefinition.addContainer(createCdkId(['MCPWorkbench', 'Container']), {
            containerName: createCdkId([config.deploymentName, 'MCPWorkbench'], 32, 2),
            image,
            environment: baseEnvironment,
            logging: LogDriver.awsLogs({
                logGroup: logGroup,
                streamPrefix: 'MCPWorkbench'
            }),
            memoryReservationMiB: 1024,
            portMappings: [{ hostPort: 0, containerPort: 8000, protocol: Protocol.TCP }],
            healthCheck: containerHealthCheck,
            privileged: true,
        });

        // Create ECS service
        const service = new Ec2Service(this, createCdkId([config.deploymentName, 'MCPWorkbench', 'Ec2Svc']), {
            cluster: ecsCluster,
            serviceName: createCdkId(['MCPWorkbench'], 32, 2),
            taskDefinition: taskDefinition,
            circuitBreaker: !config.region.includes('iso') ? { rollback: true } : undefined,
        });

        const scalableTaskCount = service.autoScaleTaskCount({
            minCapacity: 1,
            maxCapacity: 10
        });

        // Connect service to shared load balancer
        service.connections.allowFrom(loadBalancer, Port.allTcp());

        // Create target group for MCP Workbench
        const targetGroup = listener.addTargets(createCdkId(['REST', 'MCPWorkbench', 'TgtGrp']), {
            targetGroupName: createCdkId([config.deploymentName, 'REST', 'MCPWorkbench'], 32, 2).toLowerCase(),
            healthCheck: {
                path: '/health',
                interval: Duration.seconds(60),
                timeout: Duration.seconds(30),
                healthyThresholdCount: 2,
                unhealthyThresholdCount: 10,
            },
            port: 80,
            targets: [service],
            priority: 80,
            conditions: [ListenerCondition.pathPatterns(['/v2/mcp/*'])]
        });

        scalableTaskCount.scaleOnRequestCount(createCdkId(['REST', 'MCPWorkbench', 'ScalingPolicy']), {
            requestsPerTarget: 500,
            targetGroup,
            scaleInCooldown: Duration.seconds(60),
            scaleOutCooldown: Duration.seconds(60)
        });

        // Create S3 event handler for MCP Workbench
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

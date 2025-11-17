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
import { Metric, Stats } from 'aws-cdk-lib/aws-cloudwatch';
import { ISecurityGroup, IVpc, SubnetSelection } from 'aws-cdk-lib/aws-ec2';
import {
    Cluster,
    ContainerImage,
    ContainerInsights,
    FargateTaskDefinition,
    LogDriver,
    Protocol,
} from 'aws-cdk-lib/aws-ecs';
import { ApplicationLoadBalancedFargateService } from 'aws-cdk-lib/aws-ecs-patterns';
import { ApplicationListener, ApplicationLoadBalancer, Protocol as ElbProtocol } from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import {
    Effect,
    IRole,
    ManagedPolicy,
    PolicyStatement,
    Role,
    ServicePrincipal,
} from 'aws-cdk-lib/aws-iam';
import { Bucket } from 'aws-cdk-lib/aws-s3';
import { Construct } from 'constructs';

import { createCdkId } from '../../../lib/core/utils';
import { PartialConfig } from '../../../lib/schema';
import { McpServerConfig } from './utils';

/**
 * Properties for the ECSFargateCluster Construct.
 *
 * @property {IVpc} vpc - The virtual private cloud (VPC).
 * @property {ISecurityGroup} securityGroup - The security group that the ECS cluster should use.
 * @property {McpServerConfig} mcpServerConfig - The MCP server configuration.
 * @property {SubnetSelection} subnetSelection? - Optional subnet selection.
 * @property {IRole} taskExecutionRole? - Optional task execution role ARN.
 * @property {IRole} taskRole? - Optional task role ARN.
 */
type ContainerDefinitionConfig = {
    image: ContainerImage;
    environment: { [key: string]: string };
    portMappings: Array<{ containerPort: number; protocol: Protocol }>;
    command?: string[];
    entryPoint?: string[];
};

type ECSFargateClusterProps = {
    identifier: string;
    mcpServerConfig: McpServerConfig;
    securityGroup: ISecurityGroup;
    vpc: IVpc;
    subnetSelection?: SubnetSelection;
    taskExecutionRole?: IRole;
    taskRole?: IRole;
    config: PartialConfig;
    containerDefinitionConfig: ContainerDefinitionConfig;
};

/**
 * Create an ECS Fargate cluster for MCP servers.
 */
export class ECSFargateCluster extends Construct {
    /** Fargate service */
    public readonly service: ApplicationLoadBalancedFargateService;

    /** IAM role associated with the ECS task */
    public readonly taskRole: IRole;

    /** Endpoint URL of application load balancer for the cluster. */
    public readonly endpointUrl: string;

    /** Application Load Balancer for NLB integration */
    public readonly alb: ApplicationLoadBalancer;

    /** Application Load Balancer listener for NLB integration */
    public readonly albListener: ApplicationListener;

    /**
     * @param {Construct} scope - The parent or owner of the construct.
     * @param {string} id - The unique identifier for the construct within its scope.
     * @param {ECSFargateClusterProps} props - The properties of the construct.
     */
    constructor (scope: Construct, id: string, props: ECSFargateClusterProps) {
        super(scope, id);
        const { identifier, config, vpc, securityGroup, mcpServerConfig, subnetSelection, taskExecutionRole, taskRole, containerDefinitionConfig } = props;

        // CPU and memory for Fargate (defaults align with current minimums if not provided)
        // Minimum: 0.25 vCPU / 0.5 GB, Maximum: 4 vCPU / 30 GB
        const cpu = mcpServerConfig.cpu ?? 256; // 0.25 vCPU
        const memoryLimitMiB = mcpServerConfig.memoryLimitMiB ?? 512; // 0.5 GB

        // Determine container port
        const containerPort = containerDefinitionConfig.portMappings.length > 0
            ? containerDefinitionConfig.portMappings[0].containerPort
            : (mcpServerConfig.port || 8000);

        const cluster = new Cluster(this, createCdkId([identifier, 'Cl']), {
            clusterName: createCdkId([config.deploymentName, identifier], 32, 2),
            vpc: vpc,
            containerInsightsV2: !config.region?.includes('iso') ? ContainerInsights.ENABLED : ContainerInsights.DISABLED,
        });

        // Create Fargate task definition
        const fargateTaskDefinition = new FargateTaskDefinition(this, createCdkId([identifier, 'FargateTask']), {
            cpu: cpu,
            memoryLimitMiB: memoryLimitMiB,
            family: createCdkId([config.deploymentName, identifier], 32, 2),
            executionRole: taskExecutionRole || this.createExecutionRole(config, identifier),
            taskRole: taskRole || this.createTaskRole(config, identifier),
        });

        // Build container definition options
        const containerOptions: any = {
            containerName: createCdkId([config.deploymentName, identifier], 32, 2),
            image: containerDefinitionConfig.image,
            environment: containerDefinitionConfig.environment,
            logging: LogDriver.awsLogs({
                streamPrefix: identifier,
            }),
            portMappings: containerDefinitionConfig.portMappings.length > 0
                ? containerDefinitionConfig.portMappings
                : [{
                    containerPort: containerPort,
                    protocol: Protocol.TCP,
                }],
        };

        // Add container health check if configured, otherwise use defaults
        if (mcpServerConfig.containerHealthCheckConfig) {
            const healthCheckConfig = mcpServerConfig.containerHealthCheckConfig;
            const command = Array.isArray(healthCheckConfig.command)
                ? healthCheckConfig.command
                : [healthCheckConfig.command];
            containerOptions.healthCheck = {
                command: command,
                interval: Duration.seconds(healthCheckConfig.interval),
                startPeriod: Duration.seconds(healthCheckConfig.startPeriod),
                retries: healthCheckConfig.retries,
                timeout: Duration.seconds(healthCheckConfig.timeout),
            };
        } else {
            // Default container health check
            containerOptions.healthCheck = {
                command: [
                    `curl --fail http://localhost:${containerPort}/status || exit 1`
                ],
                interval: Duration.seconds(30),
                retries: 3,
                timeout: Duration.seconds(10),
                startPeriod: Duration.seconds(90),
            };
        }

        // Override command/entrypoint if provided (for pre-built images that need wrapping)
        if (containerDefinitionConfig.command) {
            containerOptions.command = containerDefinitionConfig.command;
        }
        if (containerDefinitionConfig.entryPoint) {
            containerOptions.entryPoint = containerDefinitionConfig.entryPoint;
        }

        // Add container to task definition using the container definition configuration
        fargateTaskDefinition.addContainer(createCdkId([identifier, 'Container']), containerOptions);

        // Grant S3 read access if s3Path is provided
        const hostingBucketArn = process.env['LISA_HOSTING_BUCKET_ARN'];
        if (mcpServerConfig.s3Path && hostingBucketArn) {
            const hostingBucket = Bucket.fromBucketArn(this, 'HostingBucket', hostingBucketArn);
            hostingBucket.grantRead(fargateTaskDefinition.taskRole);
        }

        // Create ApplicationLoadBalancedFargateService - this handles service, ALB, listener, and target group
        const service = new ApplicationLoadBalancedFargateService(this, createCdkId([identifier, 'FargateSvc']), {
            cluster: cluster,
            taskDefinition: fargateTaskDefinition,
            desiredCount: mcpServerConfig.autoScalingConfig.minCapacity,
            serviceName: createCdkId([config.deploymentName, identifier], 32, 2),
            publicLoadBalancer: false,
            loadBalancerName: createCdkId([config.deploymentName, identifier], 32, 2).toLowerCase(),
            listenerPort: containerPort,
            taskSubnets: subnetSelection,
            securityGroups: [securityGroup],
            circuitBreaker: !config.region?.includes('iso') ? { rollback: true } : undefined,
            // The pattern automatically uses the first container from the task definition
        });

        const alb = service.loadBalancer;

        // Configure target group deregistration delay
        service.targetGroup.setAttribute('deregistration_delay.timeout_seconds', '0');

        // Configure health check - use provided config or defaults
        if (mcpServerConfig.loadBalancerConfig?.healthCheckConfig) {
            const healthCheckConfig = mcpServerConfig.loadBalancerConfig.healthCheckConfig;
            service.targetGroup.configureHealthCheck({
                path: healthCheckConfig.path,
                port: containerPort.toString(),
                protocol: ElbProtocol.HTTP,
                healthyThresholdCount: healthCheckConfig.healthyThresholdCount,
                unhealthyThresholdCount: healthCheckConfig.unhealthyThresholdCount,
                timeout: Duration.seconds(healthCheckConfig.timeout),
                interval: Duration.seconds(healthCheckConfig.interval),
            });
        } else {
            // Default load balancer health check
            service.targetGroup.configureHealthCheck({
                path: '/status',
                port: containerPort.toString(),
                protocol: ElbProtocol.HTTP,
                healthyThresholdCount: 2,
                unhealthyThresholdCount: 3,
                timeout: Duration.seconds(10),
                interval: Duration.seconds(30),
            });
        }

        this.service = service;
        this.taskRole = fargateTaskDefinition.taskRole;
        this.alb = alb;
        this.albListener = service.listener;

        // Auto-scaling configuration
        if (mcpServerConfig.autoScalingConfig.maxCapacity > mcpServerConfig.autoScalingConfig.minCapacity) {
            const scalableTarget = service.service.autoScaleTaskCount({
                minCapacity: mcpServerConfig.autoScalingConfig.minCapacity,
                maxCapacity: mcpServerConfig.autoScalingConfig.maxCapacity,
            });

            // Scale based on CPU utilization
            scalableTarget.scaleOnCpuUtilization('CpuScaling', {
                targetUtilizationPercent: 70,
                scaleInCooldown: Duration.seconds(mcpServerConfig.autoScalingConfig.cooldown || 60),
                scaleOutCooldown: Duration.seconds(mcpServerConfig.autoScalingConfig.cooldown || 60),
            });

            // Scale based on request count if metric name provided
            if (mcpServerConfig.autoScalingConfig.metricName && mcpServerConfig.autoScalingConfig.targetValue) {
                const requestCountMetric = new Metric({
                    metricName: mcpServerConfig.autoScalingConfig.metricName,
                    namespace: 'AWS/ApplicationELB',
                    dimensionsMap: {
                        TargetGroup: service.targetGroup.targetGroupFullName,
                        LoadBalancer: service.loadBalancer.loadBalancerFullName,
                    },
                    statistic: Stats.SAMPLE_COUNT,
                    period: Duration.seconds(mcpServerConfig.autoScalingConfig.duration || 60),
                });

                scalableTarget.scaleToTrackCustomMetric('RequestScaling', {
                    metric: requestCountMetric,
                    targetValue: mcpServerConfig.autoScalingConfig.targetValue,
                    scaleInCooldown: Duration.seconds(mcpServerConfig.autoScalingConfig.cooldown || 60),
                    scaleOutCooldown: Duration.seconds(mcpServerConfig.autoScalingConfig.cooldown || 60),
                });
            }
        }

        this.endpointUrl = `http://${alb.loadBalancerDnsName}`;

        new CfnOutput(this, 'mcpServerEndpointUrl', {
            key: 'mcpServerEndpointUrl',
            value: this.endpointUrl,
        });
    }

    /**
     * Create default execution role for Fargate tasks
     */
    private createExecutionRole (config: PartialConfig, identifier: string): IRole {
        const roleName = createCdkId([config.deploymentName, identifier, 'ExecutionRole']);
        return new Role(this, roleName, {
            assumedBy: new ServicePrincipal('ecs-tasks.amazonaws.com'),
            roleName,
            description: `Allow ${identifier} ECS Fargate task execution access to AWS resources`,
            managedPolicies: [
                ManagedPolicy.fromAwsManagedPolicyName('service-role/AmazonECSTaskExecutionRolePolicy'),
            ],
        });
    }

    /**
     * Create default task role for Fargate tasks
     */
    private createTaskRole (config: PartialConfig, identifier: string): IRole {
        const roleName = createCdkId([config.deploymentName, identifier, 'TaskRole']);
        const role = new Role(this, roleName, {
            assumedBy: new ServicePrincipal('ecs-tasks.amazonaws.com'),
            roleName,
            description: `Allow ${identifier} ECS Fargate task access to AWS resources`,
        });

        // Grant S3 read access if hosting bucket is configured
        const hostingBucketArn = process.env['LISA_HOSTING_BUCKET_ARN'];
        if (hostingBucketArn) {
            role.addToPolicy(new PolicyStatement({
                effect: Effect.ALLOW,
                actions: ['s3:GetObject', 's3:ListBucket'],
                resources: [
                    hostingBucketArn,
                    `${hostingBucketArn}/*`,
                ],
            }));
        }

        // Grant CloudWatch Logs write access
        role.addToPolicy(new PolicyStatement({
            effect: Effect.ALLOW,
            actions: [
                'logs:CreateLogStream',
                'logs:PutLogEvents',
            ],
            resources: ['*'],
        }));

        return role;
    }
}

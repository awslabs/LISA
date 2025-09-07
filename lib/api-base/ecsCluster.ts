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

// ECS Cluster Construct.
import { Duration, RemovalPolicy } from 'aws-cdk-lib';
import { BlockDeviceVolume, GroupMetrics, Monitoring } from 'aws-cdk-lib/aws-autoscaling';
import { LogGroup, RetentionDays } from 'aws-cdk-lib/aws-logs';
import { Metric, Stats } from 'aws-cdk-lib/aws-cloudwatch';
import { InstanceType, ISecurityGroup } from 'aws-cdk-lib/aws-ec2';
import {
    AmiHardwareType,
    Cluster,
    ContainerDefinition,
    ContainerInsights,
    Ec2Service,
    Ec2ServiceProps,
    Ec2TaskDefinition,
    EcsOptimizedImage,
    HealthCheck,
    Host,
    LinuxParameters,
    LogDriver,
    MountPoint,
    Protocol,
    Volume,
} from 'aws-cdk-lib/aws-ecs';
import {
    ApplicationLoadBalancer,
    BaseApplicationListenerProps,
    ListenerCondition,
    SslPolicy,
} from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import { Effect, IRole, ManagedPolicy, PolicyStatement, Role } from 'aws-cdk-lib/aws-iam';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';

import { createCdkId } from '../core/utils';
import { BaseProps, Ec2Metadata, ECSConfig } from '../schema';
import { Vpc } from '../networking/vpc';
import { CodeFactory } from '../util';

/**
 * Properties for the ECSCluster Construct.
 *
 * @property {ECSConfig} ecsConfig - The configuration for the cluster.
 * @property {ISecurityGroup} securityGroup - The security group that the ECS cluster should use.
 * @property {Vpc} vpc - The virtual private cloud (VPC).
 */
type ECSClusterProps = {
    identifier: string,
    ecsConfig: {serveConfig: ECSConfig, workbenchConfig: ECSConfig};
    securityGroup: ISecurityGroup;
    vpc: Vpc;
} & BaseProps;

/**
 * Create an ECS model.
 */
export class ECSCluster extends Construct {
    /** ECS Cluster container definition (primary task for backward compatibility) */
    public readonly container: ContainerDefinition;

    /** IAM role associated with the ECS Cluster task (primary task for backward compatibility) */
    public readonly taskRole: IRole;

    /** Endpoint URL of application load balancer for the cluster. */
    public readonly endpointUrl: string;

    /** Map of all container definitions by identifier */
    public readonly containers: Map<string, ContainerDefinition> = new Map();

    /** Map of all task roles by identifier */
    public readonly taskRoles: Map<string, IRole> = new Map();

    /** Map of all services by identifier */
    public readonly services: Map<string, Ec2Service> = new Map();

    /**
     * Creates a task definition with its associated container and IAM role (base method).
     *
     * @param identifier - The identifier for the task (e.g., 'fastapi', 'workbenchHosting')
     * @param config - The base configuration
     * @param ecsConfig - The ECS configuration
     * @param volumes - Array of volumes to mount
     * @param mountPoints - Array of mount points for the container
     * @param logGroup - CloudWatch log group for container logs
     * @param buildArgs - Optional build arguments for the container image
     * @returns Object containing task definition, container, and task role
     */
    private createTaskDefinition(
        config: any,
        ecsConfig: ECSConfig,
        volumes: Volume[],
        mountPoints: MountPoint[],
        logGroup: LogGroup,
        hostPort: number,
        taskRole: IRole,
        executionRole?: IRole,
        buildArgs?: Record<string, string>
    ): { taskDefinition: Ec2TaskDefinition, container: ContainerDefinition, taskRole: IRole } {
        const taskDefinition = new Ec2TaskDefinition(this, createCdkId([ecsConfig.identifier, 'Ec2TaskDefinition']), {
            family: createCdkId([config.deploymentName, ecsConfig.identifier], 32, 2),
            volumes,
            ...(taskRole && { taskRole }),
            ...(executionRole && { executionRole }),
        });

        // Grant CloudWatch logs permissions to both task role and execution role
        logGroup.grantWrite(taskRole);
        if (executionRole) {
            logGroup.grantWrite(executionRole);
        } else {
            // If no custom execution role, ensure the default execution role has CloudWatch permissions
            // This is critical for log stream creation during container startup
            taskDefinition.addToExecutionRolePolicy(new PolicyStatement({
                effect: Effect.ALLOW,
                actions: [
                    'logs:CreateLogGroup',
                    'logs:CreateLogStream',
                    'logs:PutLogEvents',
                    'logs:DescribeLogStreams'
                ],
                resources: [logGroup.logGroupArn, `${logGroup.logGroupArn}:*`]
            }));
        }

        // Add container to task definition
        const containerHealthCheckConfig = ecsConfig.containerConfig.healthCheckConfig;
        const containerHealthCheck: HealthCheck = {
            command: containerHealthCheckConfig.command,
            interval: Duration.seconds(containerHealthCheckConfig.interval),
            startPeriod: Duration.seconds(containerHealthCheckConfig.startPeriod),
            timeout: Duration.seconds(containerHealthCheckConfig.timeout),
            retries: containerHealthCheckConfig.retries,
        };

        const linuxParameters =
            ecsConfig.containerConfig.sharedMemorySize > 0
                ? new LinuxParameters(this, createCdkId([ecsConfig.identifier, 'LinuxParameters']), {
                    sharedMemorySize: ecsConfig.containerConfig.sharedMemorySize,
                })
                : undefined;

        const image = CodeFactory.createImage(ecsConfig.containerConfig.image, this, ecsConfig.identifier, buildArgs);

        const container = taskDefinition.addContainer(createCdkId([ecsConfig.identifier, 'Container']), {
            containerName: createCdkId([config.deploymentName, ecsConfig.identifier], 32, 2),
            image,
            environment: ecsConfig.environment,
            logging: LogDriver.awsLogs({
                logGroup: logGroup,
                streamPrefix: ecsConfig.identifier
            }),
            gpuCount: Ec2Metadata.get(ecsConfig.instanceType).gpuCount,
            memoryReservationMiB: ecsConfig.containerMemoryReservationMiB,
            portMappings: [{ hostPort, containerPort: 8080, protocol: Protocol.TCP }],
            healthCheck: containerHealthCheck,
            // Model containers need to run with privileged set to true
            privileged: ecsConfig.amiHardwareType === AmiHardwareType.GPU,
            ...(linuxParameters && { linuxParameters }),
        });
        container.addMountPoints(...mountPoints);

        return { taskDefinition, container, taskRole };
    }

    /**
     * Creates the serve/primary task definition and service.
     * 
     * @param config - The base configuration
     * @param ecsConfig - The ECS configuration
     * @param volumes - Array of volumes to mount
     * @param mountPoints - Array of mount points for the container
     * @param logGroup - CloudWatch log group for container logs
     * @param cluster - The ECS cluster
     * @param autoScalingGroup - The auto-scaling group for dependency
     * @returns Object containing task definition, container, task role, and service
     */
    private createServeTaskDefinition(
        config: any,
        ecsConfig: ECSConfig,
        volumes: Volume[],
        mountPoints: MountPoint[],
        logGroup: LogGroup,
        cluster: Cluster,
        autoScalingGroup: any,
        taskRole: IRole,
        executionRole?: IRole,
        memoryReservationMiB?: number
    ): { taskDefinition: Ec2TaskDefinition, container: ContainerDefinition, taskRole: IRole, service: Ec2Service } {
        // Create task definition using the base method
        const taskResult = this.createTaskDefinition(
            config,
            ecsConfig,
            volumes,
            mountPoints,
            logGroup,
            80,
            taskRole,
            executionRole,
            ecsConfig.buildArgs
        );
        const { taskDefinition, container } = taskResult;

        // Store in maps for future reference
        this.containers.set(ecsConfig.identifier, container);
        this.taskRoles.set(ecsConfig.identifier, taskRole);

        // Create ECS service for primary task
        const serviceProps: Ec2ServiceProps = {
            cluster: cluster,
            daemon: true,
            serviceName: createCdkId([config.deploymentName, ecsConfig.identifier], 32, 2),
            taskDefinition: taskDefinition,
            circuitBreaker: !config.region.includes('iso') ? { rollback: true } : undefined,
        };

        const service = new Ec2Service(this, createCdkId([ecsConfig.identifier, 'Ec2Svc']), serviceProps);
        service.node.addDependency(autoScalingGroup);

        // Store primary service in map
        this.services.set(ecsConfig.identifier, service);

        return { taskDefinition, container, taskRole, service };
    }

    /**
     * Creates the workbench hosting task definition and service (stubbed for now).
     * 
     * @param config - The base configuration
     * @param ecsConfig - The ECS configuration (used as template)
     * @param volumes - Array of volumes to mount
     * @param mountPoints - Array of mount points for the container
     * @param logGroup - CloudWatch log group for container logs
     * @param cluster - The ECS cluster
     * @param autoScalingGroup - The auto-scaling group for dependency
     * @returns Object containing task definition, container, task role, and service
     */
    private createWorkbenchHostingTaskDefinition(
        config: any,
        ecsConfig: ECSConfig,
        volumes: Volume[],
        mountPoints: MountPoint[],
        logGroup: LogGroup,
        cluster: Cluster,
        autoScalingGroup: any,
        taskRole: IRole,
        executionRole?: IRole,
    ): { taskDefinition: Ec2TaskDefinition, container: ContainerDefinition, taskRole: IRole, service: Ec2Service } {        
        // TODO: For now, this is stubbed to use the same configuration as the primary task
        // In the future, this should have its own configuration for:
        // - Different container image
        // - Different environment variables
        // - Different health check configuration
        // - Different resource requirements
        
        // Create task definition using the base method
        const taskResult = this.createTaskDefinition(
            config,
            ecsConfig, // TODO: Replace with workbench-specific config
            volumes,
            mountPoints,
            logGroup,
            80,
            taskRole,
            executionRole,
            ecsConfig.buildArgs
        );
        const { taskDefinition, container } = taskResult;

        // Store in maps for future reference
        this.containers.set(ecsConfig.identifier, container);
        this.taskRoles.set(ecsConfig.identifier, taskRole);

        // Create ECS service for workbench hosting task
        const serviceProps: Ec2ServiceProps = {
            cluster: cluster,
            daemon: true,
            serviceName: createCdkId([config.deploymentName, ecsConfig.identifier], 32, 2),
            taskDefinition: taskDefinition,
            circuitBreaker: !config.region.includes('iso') ? { rollback: true } : undefined,
        };

        const service = new Ec2Service(this, createCdkId([ecsConfig.identifier, 'Ec2Svc']), serviceProps);
        service.node.addDependency(autoScalingGroup);

        // Store workbench service in map
        this.services.set(ecsConfig.identifier, service);

        return { taskDefinition, container, taskRole, service };
    }

    /**
   * @param {Construct} scope - The parent or owner of the construct.
   * @param {string} id - The unique identifier for the construct within its scope.
   * @param {ECSClusterProps} props - The properties of the construct.
   */
    constructor (scope: Construct, id: string, props: ECSClusterProps) {
        super(scope, id);
        const { config, identifier, vpc, securityGroup, ecsConfig } = props;

        // Retrieve execution role if it has been overridden
        const executionRole = config.roles ? Role.fromRoleArn(
            this,
            createCdkId([identifier, 'ER']),
            StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/roles/${identifier}EX`),
        ) : undefined;

        // Create ECS task definition
        const taskRole = Role.fromRoleArn(
            this,
            createCdkId([identifier, 'TR']),
            StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/roles/${identifier}`),
        );

        // Create ECS cluster
        const cluster = new Cluster(this, createCdkId(['Cl']), {
            clusterName: createCdkId([config.deploymentName, ecsConfig.serveConfig.identifier], 32, 2),
            vpc: vpc.vpc,
            containerInsightsV2: !config.region.includes('iso') ? ContainerInsights.ENABLED : ContainerInsights.DISABLED,
        });

        // Create auto-scaling group
        const autoScalingGroup = cluster.addCapacity(createCdkId(['ASG']), {
            vpcSubnets: vpc.subnetSelection,
            instanceType: new InstanceType(ecsConfig.serveConfig.instanceType),
            machineImage: EcsOptimizedImage.amazonLinux2(ecsConfig.serveConfig.amiHardwareType),
            minCapacity: ecsConfig.serveConfig.autoScalingConfig.minCapacity,
            maxCapacity: ecsConfig.serveConfig.autoScalingConfig.maxCapacity,
            cooldown: Duration.seconds(ecsConfig.serveConfig.autoScalingConfig.cooldown),
            groupMetrics: [GroupMetrics.all()],
            instanceMonitoring: Monitoring.DETAILED,
            newInstancesProtectedFromScaleIn: false,
            defaultInstanceWarmup: Duration.seconds(ecsConfig.serveConfig.autoScalingConfig.defaultInstanceWarmup),
            blockDevices: [
                {
                    deviceName: '/dev/xvda',
                    volume: BlockDeviceVolume.ebs(ecsConfig.serveConfig.autoScalingConfig.blockDeviceVolumeSize, {
                        encrypted: true,
                    }),
                },
            ],
        });

        const environment = ecsConfig.serveConfig.environment;
        const volumes: Volume[] = [];
        const mountPoints: MountPoint[] = [];

        // If NVMe drive available, mount and use it
        if (Ec2Metadata.get(ecsConfig.serveConfig.instanceType).nvmePath) {
            // EC2 user data to mount ephemeral NVMe drive
            const MOUNT_PATH = config.nvmeHostMountPath;
            const NVME_PATH = Ec2Metadata.get(ecsConfig.serveConfig.instanceType).nvmePath;
            /* eslint-disable no-useless-escape */
            const rawUserData = `#!/bin/bash
    set -e
    # Check if NVMe is already formatted
    if ! blkid ${NVME_PATH}; then
        mkfs.xfs ${NVME_PATH}
    fi

    mkdir -p ${MOUNT_PATH}
    mount ${NVME_PATH} ${MOUNT_PATH}

    # Add to fstab if not already present
    if ! grep -q "${NVME_PATH}" /etc/fstab; then
        echo ${NVME_PATH} ${MOUNT_PATH} xfs defaults,nofail 0 2 >> /etc/fstab
    fi

    # Update Docker root location and restart Docker service
    mkdir -p ${MOUNT_PATH}/docker
    echo '{\"data-root\": \"${MOUNT_PATH}/docker\"}' | tee /etc/docker/daemon.json
    systemctl restart docker
    `;
            /* eslint-enable no-useless-escape */
            autoScalingGroup.addUserData(rawUserData);

            // Create mount point for container
            const sourceVolume = 'nvme';
            const host: Host = { sourcePath: config.nvmeHostMountPath };
            const nvmeVolume: Volume = { name: sourceVolume, host: host };
            const nvmeMountPoint: MountPoint = {
                sourceVolume: sourceVolume,
                containerPath: config.nvmeContainerMountPath,
                readOnly: false,
            };
            volumes.push(nvmeVolume);
            mountPoints.push(nvmeMountPoint);
        }

        // Add CloudWatch Logs permissions to EC2 instance role for ECS logging
        autoScalingGroup.role.addManagedPolicy(ManagedPolicy.fromAwsManagedPolicyName('CloudWatchLogsFullAccess'));
        // Add permissions to use SSM in dev environment for EC2 debugging purposes only
        if (config.deploymentStage === 'dev') {
            autoScalingGroup.role.addManagedPolicy(ManagedPolicy.fromAwsManagedPolicyName('AmazonSSMFullAccess'));
        }

        if (config.region.includes('iso')) {
            const pkiSourceVolume = 'pki';
            const pkiHost: Host = { sourcePath: '/etc/pki' };
            const pkiVolume: Volume = { name: pkiSourceVolume, host: pkiHost };
            const pkiMountPoint: MountPoint = {
                sourceVolume: pkiSourceVolume,
                containerPath: '/etc/pki',
                readOnly: false,
            };
            volumes.push(pkiVolume);
            mountPoints.push(pkiMountPoint);
            // Requires mount point /etc/pki from host
            environment.SSL_CERT_DIR = '/etc/pki/tls/certs';
            environment.SSL_CERT_FILE = config.certificateAuthorityBundle;
            environment.REQUESTS_CA_BUNDLE = config.certificateAuthorityBundle;
            environment.AWS_CA_BUNDLE = config.certificateAuthorityBundle;
            environment.CURL_CA_BUNDLE = config.certificateAuthorityBundle;
        }

        // Create CloudWatch log group with explicit retention
        const logGroup = new LogGroup(this, createCdkId([ecsConfig.serveConfig.identifier, 'LogGroup']), {
            logGroupName: `/aws/ecs/${config.deploymentName}-${ecsConfig.serveConfig.identifier}`,
            retention: RetentionDays.ONE_WEEK,
            removalPolicy: config.removalPolicy
        });

        const memoryReservationMiB = ecsConfig.serveConfig.containerMemoryBuffer + ecsConfig.workbenchConfig.containerMemoryBuffer;

        // Create primary/serve task definition and service
        const primaryTaskResult = this.createServeTaskDefinition(
            config,
            ecsConfig.serveConfig,
            volumes,
            mountPoints,
            logGroup,
            cluster,
            autoScalingGroup,
            taskRole,
            executionRole
        );
        const { taskDefinition, container, service } = primaryTaskResult;

        // Create workbench hosting task definition (stubbed for now)
        const workbenchHostingTaskResult = this.createWorkbenchHostingTaskDefinition(
            config,
            ecsConfig.workbenchConfig,
            volumes,
            mountPoints,
            logGroup,
            cluster,
            autoScalingGroup,
            taskRole,
            executionRole
        );
        const { service: workbenchService } = workbenchHostingTaskResult;

        // Create application load balancer
        const loadBalancer = new ApplicationLoadBalancer(this, createCdkId([ecsConfig.serveConfig.identifier, 'ALB']), {
            deletionProtection: config.removalPolicy !== RemovalPolicy.DESTROY,
            internetFacing: ecsConfig.serveConfig.internetFacing,
            loadBalancerName: createCdkId([config.deploymentName, ecsConfig.serveConfig.identifier], 32, 2).toLowerCase(),
            dropInvalidHeaderFields: true,
            securityGroup,
            vpc: vpc.vpc,
            vpcSubnets: vpc.subnetSelection,
            idleTimeout: Duration.seconds(600)
        });

        // Add listener
        const listenerProps: BaseApplicationListenerProps = {
            port: ecsConfig.serveConfig.loadBalancerConfig.sslCertIamArn ? 443 : 80,
            open: ecsConfig.serveConfig.internetFacing,
            certificates: ecsConfig.serveConfig.loadBalancerConfig.sslCertIamArn
                ? [{ certificateArn: ecsConfig.serveConfig.loadBalancerConfig.sslCertIamArn }]
                : undefined,
            sslPolicy: ecsConfig.serveConfig.loadBalancerConfig.sslCertIamArn ? SslPolicy.RECOMMENDED_TLS : SslPolicy.RECOMMENDED,
        };

        const listener = loadBalancer.addListener(
            createCdkId([ecsConfig.serveConfig.identifier, 'ApplicationListener']),
            listenerProps,
        );
        const protocol = listenerProps.port === 443 ? 'https' : 'http';

        // Create target groups for both services
        const loadBalancerHealthCheckConfig = ecsConfig.serveConfig.loadBalancerConfig.healthCheckConfig;
        
        // Primary service target group (default rule)
        const primaryTargetGroup = listener.addTargets(createCdkId([ecsConfig.serveConfig.identifier, 'TgtGrp']), {
            targetGroupName: createCdkId([config.deploymentName, ecsConfig.serveConfig.identifier], 32, 2).toLowerCase(),
            healthCheck: {
                path: loadBalancerHealthCheckConfig.path,
                interval: Duration.seconds(loadBalancerHealthCheckConfig.interval),
                timeout: Duration.seconds(loadBalancerHealthCheckConfig.timeout),
                healthyThresholdCount: loadBalancerHealthCheckConfig.healthyThresholdCount,
                unhealthyThresholdCount: loadBalancerHealthCheckConfig.unhealthyThresholdCount,
            },
            port: 80,
            targets: [service],
        });

        // Create separate target group for workbench hosting service
        const workbenchTargetGroup = listener.addTargets(createCdkId(['workbenchHosting', 'TgtGrp']), {
            targetGroupName: createCdkId([config.deploymentName, 'workbenchHosting'], 32, 2).toLowerCase(),
            healthCheck: {
                path: loadBalancerHealthCheckConfig.path, // TODO: Use workbench-specific health check path
                interval: Duration.seconds(loadBalancerHealthCheckConfig.interval),
                timeout: Duration.seconds(loadBalancerHealthCheckConfig.timeout),
                healthyThresholdCount: loadBalancerHealthCheckConfig.healthyThresholdCount,
                unhealthyThresholdCount: loadBalancerHealthCheckConfig.unhealthyThresholdCount,
            },
            port: 80,
            targets: [workbenchService],
            priority: 100, // Higher priority than default rule
            conditions: [
                ListenerCondition.pathPatterns(['/api/v2/workbench*'])
            ]
        });

        // Use primary target group for metrics (backward compatibility)
        const targetGroup = primaryTargetGroup;

        // ALB metric for ASG to use for auto scaling EC2 instances
        // TODO: Update this to step scaling for embedding models??
        const requestCountPerTargetMetric = new Metric({
            metricName: ecsConfig.serveConfig.autoScalingConfig.metricConfig.albMetricName,
            namespace: 'AWS/ApplicationELB',
            dimensionsMap: {
                TargetGroup: targetGroup.targetGroupFullName,
                LoadBalancer: loadBalancer.loadBalancerFullName,
            },
            statistic: Stats.SAMPLE_COUNT,
            period: Duration.seconds(ecsConfig.serveConfig.autoScalingConfig.metricConfig.duration),
        });

        // Create hook to scale on ALB metric count exceeding thresholds
        autoScalingGroup.scaleToTrackMetric(createCdkId([ecsConfig.serveConfig.identifier, 'ScalingPolicy']), {
            metric: requestCountPerTargetMetric,
            targetValue: ecsConfig.serveConfig.autoScalingConfig.metricConfig.targetValue,
            estimatedInstanceWarmup: Duration.seconds(ecsConfig.serveConfig.autoScalingConfig.metricConfig.duration),
        });

        const domain =
            ecsConfig.serveConfig.loadBalancerConfig.domainName !== null
                ? ecsConfig.serveConfig.loadBalancerConfig.domainName
                : loadBalancer.loadBalancerDnsName;
        this.endpointUrl = `${protocol}://${domain}`;

        // Update
        this.container = container;
        this.taskRole = taskRole;
    }
}

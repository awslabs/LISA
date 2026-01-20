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
import { Duration, RemovalPolicy, Tags } from 'aws-cdk-lib';
import { AdjustmentType, AutoScalingGroup, BlockDeviceVolume, GroupMetrics, Monitoring, UpdatePolicy, CfnScheduledAction } from 'aws-cdk-lib/aws-autoscaling';
import { LogGroup, RetentionDays } from 'aws-cdk-lib/aws-logs';
import { Metric } from 'aws-cdk-lib/aws-cloudwatch';
import { InstanceType, ISecurityGroup, Port, SecurityGroup } from 'aws-cdk-lib/aws-ec2';
import { Alias } from 'aws-cdk-lib/aws-kms';
import {
    AmiHardwareType,
    AsgCapacityProvider,
    Capability,
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
    ApplicationTargetGroup,
    BaseApplicationListenerProps,
    ListenerCondition,
    SslPolicy,
} from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import { IRole, ManagedPolicy, Role } from 'aws-cdk-lib/aws-iam';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';

import { createCdkId } from '../core/utils';
import { BaseProps, Config, Ec2Metadata, ECSConfig, TaskDefinition } from '../schema';
import { Vpc } from '../networking/vpc';
import { CodeFactory } from '../util';

export enum ECSTasks {
    REST = 'REST',
    MCPWORKBENCH = 'MCPWORKBENCH',
}

/**
 * Properties for the ECSCluster Construct.
 *
 * @property {ECSConfig} ecsConfig - The configuration for the cluster.
 * @property {ISecurityGroup} securityGroup - The security group that the ECS cluster should use.
 * @property {Vpc} vpc - The virtual private cloud (VPC).
 */
type ECSClusterProps = {
    identifier: string,
    ecsConfig: ECSConfig;
    securityGroup: ISecurityGroup;
    vpc: Vpc;
    environment: Record<string, string>;
} & BaseProps;

/**
 * Create an ECS model.
 */
export class ECSCluster extends Construct {

    /** Endpoint URL of application load balancer for the cluster. */
    public readonly endpointUrl: string;

    /** Map of all container definitions by identifier */
    public readonly containers: Partial<Record<ECSTasks, ContainerDefinition>> = {};

    /** Map of all task roles by identifier */
    public readonly taskRoles: Partial<Record<ECSTasks, IRole>> = {};

    /** Map of all services by identifier */
    public readonly services: Partial<Record<ECSTasks, Ec2Service>> = {};

    /** Application Load Balancer */
    public readonly loadBalancer: ApplicationLoadBalancer;

    /** Application Listener */
    public readonly listener: any;

    /** ECS Cluster */
    public readonly cluster: Cluster;

    private readonly targetGroups: Partial<Record<ECSTasks, ApplicationTargetGroup>> = {};
    private readonly config: Config;
    private readonly ecsConfig: ECSConfig;
    private readonly vpc: Vpc;
    private readonly securityGroup: ISecurityGroup;
    private readonly logGroup: LogGroup;
    private readonly volumes: Volume[];
    private readonly mountPoints: MountPoint[];
    private readonly baseEnvironment: Record<string, string>;
    private readonly autoScalingGroup: AutoScalingGroup;
    private readonly asgCapacityProvider: AsgCapacityProvider;
    private readonly identifier: string;

    /**
     * Creates a task definition with its associated container and IAM role (base method).
     *
     * @param identifier - The identifier for the task (e.g., 'fastapi', 'workbenchHosting')
     * @param config - The base configuration
     * @param taskDefinition - The ECS configuration
     * @param volumes - Array of volumes to mount
     * @param mountPoints - Array of mount points for the container
     * @param logGroup - CloudWatch log group for container logs
     * @param buildArgs - Optional build arguments for the container image
     * @returns Object containing task definition, container, and task role
     */
    private createTaskDefinition (
        taskDefinitionName: string,
        config: Config,
        taskDefinition: TaskDefinition,
        ecsConfig: ECSConfig,
        volumes: Volume[],
        mountPoints: MountPoint[],
        logGroup: LogGroup,
        // hostPort: number,
        taskRole: IRole,
        executionRole?: IRole
    ): { taskDefinition: Ec2TaskDefinition, container: ContainerDefinition } {
        const ec2TaskDefinition = new Ec2TaskDefinition(this, createCdkId([taskDefinitionName, 'Ec2TaskDefinition']), {
            family: createCdkId([config.deploymentName, taskDefinitionName], 32, 2),
            volumes,
            ...(taskRole && { taskRole }),
            ...(executionRole && { executionRole }),
        });

        // Grant CloudWatch logs write permissions to task role and execution role
        logGroup.grantWrite(taskRole);
        logGroup.grantWrite(ec2TaskDefinition.obtainExecutionRole());

        // Add container to task definition
        const containerHealthCheckConfig = taskDefinition.containerConfig.healthCheckConfig;
        const containerHealthCheck: HealthCheck = {
            command: containerHealthCheckConfig.command,
            interval: Duration.seconds(containerHealthCheckConfig.interval),
            startPeriod: Duration.seconds(containerHealthCheckConfig.startPeriod),
            timeout: Duration.seconds(containerHealthCheckConfig.timeout),
            retries: containerHealthCheckConfig.retries,
        };

        // Create LinuxParameters for shared memory size and/or Linux capabilities
        const needsLinuxParameters = taskDefinition.containerConfig.sharedMemorySize > 0 ||
            taskDefinition.containerConfig.linuxCapabilities;

        const linuxParameters = needsLinuxParameters
            ? new LinuxParameters(this, createCdkId([taskDefinitionName, 'LinuxParameters']), {
                sharedMemorySize: taskDefinition.containerConfig.sharedMemorySize > 0
                    ? taskDefinition.containerConfig.sharedMemorySize
                    : undefined,
            })
            : undefined;

        // Add Linux capabilities if specified (e.g., SYS_ADMIN for FUSE mounts)
        if (linuxParameters && taskDefinition.containerConfig.linuxCapabilities) {
            const caps = taskDefinition.containerConfig.linuxCapabilities;
            if (caps.add) {
                // Map string capability names to Capability enum values
                const capabilityMap: Record<string, Capability> = {
                    'SYS_ADMIN': Capability.SYS_ADMIN,
                    'NET_ADMIN': Capability.NET_ADMIN,
                    'SYS_PTRACE': Capability.SYS_PTRACE,
                    'AUDIT_CONTROL': Capability.AUDIT_CONTROL,
                    'AUDIT_WRITE': Capability.AUDIT_WRITE,
                    'CHOWN': Capability.CHOWN,
                    'DAC_OVERRIDE': Capability.DAC_OVERRIDE,
                    'FOWNER': Capability.FOWNER,
                    'FSETID': Capability.FSETID,
                    'KILL': Capability.KILL,
                    'MKNOD': Capability.MKNOD,
                    'NET_BIND_SERVICE': Capability.NET_BIND_SERVICE,
                    'SETFCAP': Capability.SETFCAP,
                    'SETGID': Capability.SETGID,
                    'SETUID': Capability.SETUID,
                    'SYS_CHROOT': Capability.SYS_CHROOT,
                };
                const addCaps = caps.add
                    .map(cap => capabilityMap[cap])
                    .filter((cap): cap is Capability => cap !== undefined);
                if (addCaps.length > 0) {
                    linuxParameters.addCapabilities(...addCaps);
                }
            }
            if (caps.drop) {
                const capabilityMap: Record<string, Capability> = {
                    'ALL': Capability.ALL,
                    'SYS_ADMIN': Capability.SYS_ADMIN,
                    'NET_ADMIN': Capability.NET_ADMIN,
                };
                const dropCaps = caps.drop
                    .map(cap => capabilityMap[cap])
                    .filter((cap): cap is Capability => cap !== undefined);
                if (dropCaps.length > 0) {
                    linuxParameters.dropCapabilities(...dropCaps);
                }
            }
        }

        const image = CodeFactory.createImage(taskDefinition.containerConfig.image, this, taskDefinitionName, ecsConfig.buildArgs);

        const container = ec2TaskDefinition.addContainer(createCdkId([taskDefinitionName, 'Container']), {
            containerName: createCdkId([config.deploymentName, taskDefinitionName], 32, 2),
            image,
            environment: {...this.baseEnvironment, ...(taskDefinition.environment as Record<string, string>)},
            logging: LogDriver.awsLogs({
                logGroup: logGroup,
                streamPrefix: taskDefinitionName
            }),
            gpuCount: Ec2Metadata.get(ecsConfig.instanceType).gpuCount,
            memoryReservationMiB: taskDefinition.containerMemoryReservationMiB,
            memoryLimitMiB: ecsConfig.containerMemoryBuffer,
            portMappings: [{ hostPort: 0, containerPort: taskDefinition.applicationTarget?.port ?? 8080, protocol: Protocol.TCP }],
            healthCheck: containerHealthCheck,
            // Model containers need to run with privileged set to true
            privileged: taskDefinition.containerConfig.privileged ?? ecsConfig.amiHardwareType === AmiHardwareType.GPU,
            ...(linuxParameters && { linuxParameters }),
        });
        container.addMountPoints(...mountPoints);

        return { taskDefinition: ec2TaskDefinition, container };
    }

    /**
   * @param {Construct} scope - The parent or owner of the construct.
   * @param {string} id - The unique identifier for the construct within its scope.
   * @param {ECSClusterProps} props - The properties of the construct.
   */
    constructor (scope: Construct, id: string, props: ECSClusterProps) {
        super(scope, id);
        const { config, identifier, vpc, securityGroup, ecsConfig, environment } = props;
        this.identifier = identifier;

        // Create ECS cluster
        const cluster = new Cluster(this, createCdkId([config.deploymentName, config.deploymentStage, 'Cl']), {
            clusterName: createCdkId([config.deploymentName, config.deploymentStage, identifier], 32, 2),
            vpc: vpc.vpc,
            containerInsightsV2: !config.region.includes('iso') ? ContainerInsights.ENABLED : ContainerInsights.DISABLED,
        });

        const asgSecurityGroup = new SecurityGroup(this, 'RestAsgSecurityGroup', {
            allowAllOutbound: true,
            vpc: vpc.vpc,
        });

        // Create auto-scaling group
        const autoScalingGroup = new AutoScalingGroup(this, createCdkId([config.deploymentName, config.deploymentStage, 'ASG']), {
            vpc: vpc.vpc,
            vpcSubnets: vpc.subnetSelection,
            instanceType: new InstanceType(ecsConfig.instanceType),
            machineImage: EcsOptimizedImage.amazonLinux2(ecsConfig.amiHardwareType),
            minCapacity: ecsConfig.autoScalingConfig.minCapacity,
            maxCapacity: ecsConfig.autoScalingConfig.maxCapacity,
            cooldown: Duration.seconds(ecsConfig.autoScalingConfig.cooldown),
            groupMetrics: [GroupMetrics.all()],
            instanceMonitoring: Monitoring.DETAILED,
            defaultInstanceWarmup: Duration.seconds(ecsConfig.autoScalingConfig.defaultInstanceWarmup),
            blockDevices: [
                {
                    deviceName: '/dev/xvda',
                    volume: BlockDeviceVolume.ebs(ecsConfig.autoScalingConfig.blockDeviceVolumeSize, {
                        encrypted: true,
                    }),
                },
            ],
            securityGroup: asgSecurityGroup,
            autoScalingGroupName: createCdkId([config.deploymentName, config.deploymentStage, identifier], 32, 2),
            updatePolicy: UpdatePolicy.rollingUpdate({})
        });

        // Enable SNS topic encryption for ECS lifecycle hooks
        // AppSec Finding #5: SNS topics must use server-side encryption
        // Uses AWS managed key (alias/aws/sns) for lifecycle hook drain notifications
        const snsEncryptionKey = Alias.fromAliasName(
            this,
            createCdkId([config.deploymentName, config.deploymentStage, 'SnsKey']),
            'alias/aws/sns'
        );

        const asgCapacityProvider = new AsgCapacityProvider(this, createCdkId([config.deploymentName, config.deploymentStage, 'AsgCapacityProvider']), {
            autoScalingGroup,
            // Managed scaling tracks cluster reservation to add/remove instances automatically
            // when services want more tasks than the cluster can fit.
            // targetCapacityPercent ~ how "full" you want the cluster (by CPU/memory reservation).
            // 90 means try to keep instances ~90% reserved before adding more.
            // capacityProviderName: [config.deploymentName, config.deploymentStage, 'cp-ec2'].join('-'),

            // disable managed scaling because we are going to setup rules to do it
            enableManagedScaling: false,
            enableManagedTerminationProtection: false,

            // Encrypt SNS topic used for lifecycle hook notifications
            topicEncryptionKey: snsEncryptionKey,
        });
        cluster.addAsgCapacityProvider(asgCapacityProvider);

        const reservationMetric = new Metric({
            namespace: 'AWS/ECS/CapacityProvider',
            metricName: 'CapacityProviderReservation',
            // The dimensions are crucial to target the specific cluster and capacity provider
            dimensionsMap: {
                ClusterName: cluster.clusterName,
                CapacityProviderName: asgCapacityProvider.capacityProviderName,
            },
            statistic: 'Average',
            period: Duration.minutes(1),
        });

        autoScalingGroup.scaleOnMetric(createCdkId(['ASG', identifier, 'ScaleIn']), {
            metric: reservationMetric,
            scalingSteps: [
                { lower: 60, change: 1 },
                { lower: 40, change: 2 }
            ],
            evaluationPeriods: 5,
            adjustmentType: AdjustmentType.CHANGE_IN_CAPACITY,
            cooldown: Duration.seconds(300)
        });

        autoScalingGroup.scaleOnMetric(createCdkId(['ASG', identifier, 'ScaleOut']), {
            metric: reservationMetric,
            scalingSteps: [
                { upper: 80, change: 1 },
                { upper: 90, change: 2 }
            ],
            evaluationPeriods: 2,
            adjustmentType: AdjustmentType.CHANGE_IN_CAPACITY,
            cooldown: Duration.seconds(120)
        });

        // Tag Auto Scaling Group for schedule management
        Tags.of(autoScalingGroup).add('ScheduleManaged', 'true');
        Tags.of(autoScalingGroup).add('LISACluster', identifier);
        Tags.of(autoScalingGroup).add('Environment', config.deploymentStage);

        const baseEnvironment: {
            [key: string]: string;
        } = {...environment};
        const volumes: Volume[] = [];
        const mountPoints: MountPoint[] = [];

        // If NVMe drive available, mount and use it
        if (Ec2Metadata.get(ecsConfig.instanceType).nvmePath) {
            // EC2 user data to mount ephemeral NVMe drive
            const MOUNT_PATH = config.nvmeHostMountPath;
            const NVME_PATH = Ec2Metadata.get(ecsConfig.instanceType).nvmePath;
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
            baseEnvironment.SSL_CERT_DIR = '/etc/pki/tls/certs';
            baseEnvironment.SSL_CERT_FILE = config.certificateAuthorityBundle;
            baseEnvironment.REQUESTS_CA_BUNDLE = config.certificateAuthorityBundle;
            baseEnvironment.AWS_CA_BUNDLE = config.certificateAuthorityBundle;
            baseEnvironment.CURL_CA_BUNDLE = config.certificateAuthorityBundle;
        }

        // Create CloudWatch log group with explicit retention
        const logGroup = new LogGroup(this, createCdkId([config.deploymentPrefix, identifier, 'LogGroup']), {
            logGroupName: `/aws/ecs/${config.deploymentName}-${config.deploymentStage}-${identifier}`,
            retention: RetentionDays.ONE_WEEK,
            removalPolicy: config.removalPolicy
        });

        // Create application load balancer
        const loadBalancer = new ApplicationLoadBalancer(this, createCdkId([config.deploymentName, config.deploymentStage, identifier, 'ALB']), {
            deletionProtection: config.removalPolicy !== RemovalPolicy.DESTROY,
            internetFacing: ecsConfig.internetFacing,
            loadBalancerName: createCdkId([config.deploymentName, config.deploymentStage, identifier], 32, 2).toLowerCase(),
            dropInvalidHeaderFields: true,
            securityGroup,
            vpc: vpc.vpc,
            vpcSubnets: vpc.subnetSelection,
            idleTimeout: Duration.seconds(600)
        });

        asgSecurityGroup.addIngressRule(securityGroup, Port.allTcp());

        // Add listener
        // AppSec TLS Configuration: Use TLS 1.2/1.3 policy with forward secrecy (ECDHE cipher suites only)
        // SslPolicy.TLS13_RES maps to ELBSecurityPolicy-TLS13-1-2-2021-06
        // This policy excludes RSA key exchange cipher suites to meet tlscheckerv2 compliance requirements
        const listenerProps: BaseApplicationListenerProps = {
            port: ecsConfig.loadBalancerConfig.sslCertIamArn ? 443 : 80,
            open: ecsConfig.internetFacing,
            certificates: ecsConfig.loadBalancerConfig.sslCertIamArn
                ? [{ certificateArn: ecsConfig.loadBalancerConfig.sslCertIamArn }]
                : undefined,
            sslPolicy: ecsConfig.loadBalancerConfig.sslCertIamArn ? SslPolicy.TLS13_RES : undefined,
        };

        const listener = loadBalancer.addListener(
            createCdkId([identifier, 'ApplicationListener']),
            listenerProps,
        );

        // Expose load balancer, listener, and cluster for shared use
        this.loadBalancer = loadBalancer;
        this.listener = listener;
        this.cluster = cluster;
        const protocol = listenerProps.port === 443 ? 'https' : 'http';

        const domain =
            ecsConfig.loadBalancerConfig.domainName !== null
                ? ecsConfig.loadBalancerConfig.domainName
                : loadBalancer.loadBalancerDnsName;
        this.endpointUrl = `${protocol}://${domain}`;
        baseEnvironment.CORS_ORIGINS = [loadBalancer.loadBalancerDnsName, ecsConfig.loadBalancerConfig.domainName].filter(Boolean)
            .map((domain) => `${protocol}://${domain}`)
            .concat('*')
            .join(',');

        // Store configuration for later use by addTask method
        this.config = config;
        this.ecsConfig = ecsConfig;
        this.vpc = vpc;
        this.securityGroup = securityGroup;
        this.logGroup = logGroup;
        this.volumes = volumes;
        this.mountPoints = mountPoints;
        this.baseEnvironment = baseEnvironment;
        this.autoScalingGroup = autoScalingGroup;
        this.asgCapacityProvider = asgCapacityProvider;
    }

    /**
     * Create a scheduled scaling action for the Auto Scaling Group
     */
    public createScheduledAction (
        actionName: string,
        schedule: string,
        minSize?: number,
        maxSize?: number,
        desiredCapacity?: number,
        timezone?: string
    ): CfnScheduledAction {
        const scheduledAction = new CfnScheduledAction(this, createCdkId([this.identifier, actionName, 'ScheduledAction']), {
            autoScalingGroupName: this.autoScalingGroup.autoScalingGroupName,
            recurrence: schedule,
            ...(minSize !== undefined && { minSize }),
            ...(maxSize !== undefined && { maxSize }),
            ...(desiredCapacity !== undefined && { desiredCapacity }),
            ...(timezone && { timeZone: timezone })
        });

        // Add tags to track the scheduled action
        Tags.of(scheduledAction).add('ActionType', 'Schedule');
        Tags.of(scheduledAction).add('LISACluster', this.identifier);
        Tags.of(scheduledAction).add('CreatedBy', 'LISA-ScheduleManagement');

        return scheduledAction;
    }

    /**
     * Get Auto Scaling Group name for external schedule management
     */
    public getAutoScalingGroupName (): string {
        return this.autoScalingGroup.autoScalingGroupName;
    }

    /**
     * Get Auto Scaling Group ARN for external schedule management
     */
    public getAutoScalingGroupArn (): string {
        return this.autoScalingGroup.autoScalingGroupArn;
    }

    /**
     * Add schedule-aware service discovery capabilities
     */
    public addScheduleAwareService (
        taskName: ECSTasks,
        taskDefinition: TaskDefinition,
        scheduleConfig?: {
            scheduleEnabled: boolean;
            scheduleType: string;
            timezone: string;
        }
    ): { service: Ec2Service; targetGroup?: ApplicationTargetGroup } {
        const result = this.addTask(taskName, taskDefinition);
        const { service } = result;

        // Add schedule-related tags to the service
        if (scheduleConfig?.scheduleEnabled) {
            Tags.of(service).add('ScheduleEnabled', 'true');
            Tags.of(service).add('ScheduleType', scheduleConfig.scheduleType);
            Tags.of(service).add('Timezone', scheduleConfig.timezone);
            Tags.of(service).add('ScheduleManaged', 'true');
        } else {
            Tags.of(service).add('ScheduleEnabled', 'false');
            Tags.of(service).add('RunsAllTime', 'true');
        }

        // Add schedule-related environment variables
        if (scheduleConfig?.scheduleEnabled) {
            const container = service.taskDefinition.findContainer(createCdkId([taskName, 'Container']));
            if (container) {
                container.addEnvironment('SCHEDULE_ENABLED', 'true');
                container.addEnvironment('SCHEDULE_TYPE', scheduleConfig.scheduleType);
                container.addEnvironment('SCHEDULE_TIMEZONE', scheduleConfig.timezone);
            }
        }

        return result;
    }

    /**
     * Get service discovery information for schedule management
     */
    public getServiceDiscoveryInfo (taskName: ECSTasks): {
        serviceName: string;
        serviceArn: string;
        clusterName: string;
        autoScalingGroupName: string;
    } | null {
        const service = this.services[taskName];
        if (!service) {
            return null;
        }

        return {
            serviceName: service.serviceName,
            serviceArn: service.serviceArn,
            clusterName: this.cluster.clusterName,
            autoScalingGroupName: this.autoScalingGroup.autoScalingGroupName
        };
    }

    /**
     * Add a task to the ECS cluster with its own target group and service.
     *
     * @param taskName - The name of the task (e.g., ECSTasks.REST, ECSTasks.MCPWORKBENCH)
     * @param taskDefinition - The task definition configuration. Environment variables within task definition will be merged with
     *                         cluster environment variables.
     * @param identifier - The identifier for naming resources
     * @returns Object containing the created service and target group
     */
    public addTask (
        taskName: ECSTasks,
        taskDefinition: TaskDefinition,
    ): { service: Ec2Service; targetGroup?: ApplicationTargetGroup } {
        // Retrieve task role and execution role for the task
        const taskRole = Role.fromRoleArn(
            this,
            createCdkId([taskName, 'TR']),
            StringParameter.valueForStringParameter(this, `${this.config.deploymentPrefix}/roles/${taskName}`),
        );
        const executionRole = Role.fromRoleArn(
            this,
            createCdkId([taskName, 'ER']),
            StringParameter.valueForStringParameter(this, `${this.config.deploymentPrefix}/roles/${taskName}EX`),
        );

        const taskResult = this.createTaskDefinition(
            taskName,
            this.config,
            taskDefinition,
            this.ecsConfig,
            this.volumes,
            this.mountPoints,
            this.logGroup,
            taskRole,
            executionRole
        );
        const { taskDefinition: ec2TaskDefinition, container } = taskResult;

        // Store references
        this.containers[taskName] = container;
        this.taskRoles[taskName] = taskRole;

        // Create ECS service
        const serviceProps: Ec2ServiceProps = {
            cluster: this.cluster,
            serviceName: createCdkId([taskName], 32, 2),
            taskDefinition: ec2TaskDefinition,
            circuitBreaker: !this.config.region.includes('iso') ? { rollback: true } : undefined,
            capacityProviderStrategies: [
                { capacityProvider: this.asgCapacityProvider.capacityProviderName, weight: 1 }
            ]
        };

        const service = new Ec2Service(this, createCdkId([this.config.deploymentName, taskName, 'Ec2Svc']), serviceProps);
        service.node.addDependency(this.autoScalingGroup);

        // Store service reference
        this.services[taskName] = service;

        // Allow load balancer to access the service
        service.connections.allowFrom(this.loadBalancer, Port.allTcp());

        const loadBalancerHealthCheckConfig = this.ecsConfig.loadBalancerConfig.healthCheckConfig;

        const targetGroup = this.listener.addTargets(createCdkId([this.identifier, taskName, 'TgtGrp']), {
            targetGroupName: createCdkId([this.config.deploymentName, this.identifier, taskName], 32, 2).toLowerCase(),
            healthCheck: {
                path: loadBalancerHealthCheckConfig.path,
                interval: Duration.seconds(loadBalancerHealthCheckConfig.interval),
                timeout: Duration.seconds(loadBalancerHealthCheckConfig.timeout),
                healthyThresholdCount: loadBalancerHealthCheckConfig.healthyThresholdCount,
                unhealthyThresholdCount: loadBalancerHealthCheckConfig.unhealthyThresholdCount,
            },
            port: 80,
            targets: [service],
            ...(taskDefinition.applicationTarget?.priority && {
                priority: taskDefinition.applicationTarget.priority,
                conditions: taskDefinition.applicationTarget.conditions?.map(({ type, values }) => {
                    switch (type) {
                        case 'pathPatterns':
                            return ListenerCondition.pathPatterns(values);
                    }
                })
            })
        });

        return { service, targetGroup };
    }
}

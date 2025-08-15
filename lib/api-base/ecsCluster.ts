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
import { AdjustmentType, AutoScalingGroup, BlockDeviceVolume, GroupMetrics, Monitoring, UpdatePolicy } from 'aws-cdk-lib/aws-autoscaling';
import { LogGroup, RetentionDays } from 'aws-cdk-lib/aws-logs';
import { Metric } from 'aws-cdk-lib/aws-cloudwatch';
import { InstanceType, ISecurityGroup, Port, SecurityGroup } from 'aws-cdk-lib/aws-ec2';
import {
    AmiHardwareType,
    AsgCapacityProvider,
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
import { Effect, IRole, ManagedPolicy, PolicyStatement, Role } from 'aws-cdk-lib/aws-iam';
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

    private readonly targetGroups: Partial<Record<ECSTasks, ApplicationTargetGroup>> = {};

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
        baseEnvironment: Record<string, string>,
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

        // Grant CloudWatch logs permissions to both task role and execution role
        logGroup.grantWrite(taskRole);
        if (executionRole) {
            logGroup.grantWrite(executionRole);
        } else {
            // If no custom execution role, ensure the default execution role has CloudWatch permissions
            // This is critical for log stream creation during container startup
            ec2TaskDefinition.addToExecutionRolePolicy(new PolicyStatement({
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
        const containerHealthCheckConfig = taskDefinition.containerConfig.healthCheckConfig;
        const containerHealthCheck: HealthCheck = {
            command: containerHealthCheckConfig.command,
            interval: Duration.seconds(containerHealthCheckConfig.interval),
            startPeriod: Duration.seconds(containerHealthCheckConfig.startPeriod),
            timeout: Duration.seconds(containerHealthCheckConfig.timeout),
            retries: containerHealthCheckConfig.retries,
        };

        const linuxParameters =
            taskDefinition.containerConfig.sharedMemorySize > 0
                ? new LinuxParameters(this, createCdkId([taskDefinitionName, 'LinuxParameters']), {
                    sharedMemorySize: taskDefinition.containerConfig.sharedMemorySize,
                })
                : undefined;

        const image = CodeFactory.createImage(taskDefinition.containerConfig.image, this, taskDefinitionName, ecsConfig.buildArgs);

        const container = ec2TaskDefinition.addContainer(createCdkId([taskDefinitionName, 'Container']), {
            containerName: createCdkId([config.deploymentName, taskDefinitionName], 32, 2),
            image,
            environment: {...baseEnvironment, ...taskDefinition.environment},
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

        const baseEnvironment: {
            [key: string]: string;
        } = {};
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

        // Retrieve execution role if it has been overridden
        const executionRole = config.roles ? Role.fromRoleArn(
            this,
            createCdkId([ecsConfig.identifier, 'ER']),
            StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/roles/${ecsConfig.identifier}EX`),
        ) : undefined;

        // Create ECS task definition
        const taskRole = Role.fromRoleArn(
            this,
            createCdkId([ecsConfig.identifier, 'TR']),
            StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/roles/${ecsConfig.identifier}`),
        );
        
        // Grant CloudWatch logs permissions to both task role and execution role
        logGroup.grantWrite(taskRole);
        if (executionRole) {
            logGroup.grantWrite(executionRole);
        }
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

        const image = CodeFactory.createImage(ecsConfig.containerConfig.image, this, ecsConfig.identifier, ecsConfig.buildArgs);

        const container = taskDefinition.addContainer(createCdkId([ecsConfig.identifier, 'Container']), {
            containerName: createCdkId([config.deploymentName, ecsConfig.identifier], 32, 2),
            image,
            environment,
            logging: LogDriver.awsLogs({
                logGroup: logGroup,
                streamPrefix: ecsConfig.identifier
            }),
            gpuCount: Ec2Metadata.get(ecsConfig.instanceType).gpuCount,
            memoryReservationMiB: Ec2Metadata.get(ecsConfig.instanceType).memory - ecsConfig.containerMemoryBuffer,
            portMappings: [{ containerPort: 8080, protocol: Protocol.TCP }],
            healthCheck: containerHealthCheck,
            // Model containers need to run with privileged set to true
            privileged: ecsConfig.amiHardwareType === AmiHardwareType.GPU,
            ...(linuxParameters && { linuxParameters }),
        });
        container.addMountPoints(...mountPoints);

        // Create ECS service
        const serviceProps: Ec2ServiceProps = {
            cluster: cluster,
            daemon: true,
            serviceName: createCdkId([config.deploymentName, ecsConfig.identifier], 32, 2),
            taskDefinition: taskDefinition,
            circuitBreaker: !config.region.includes('iso') ? { rollback: true } : undefined,
        };

        const service = new Ec2Service(this, createCdkId([ecsConfig.identifier, 'Ec2Svc']), serviceProps);

        service.node.addDependency(autoScalingGroup);

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
        const listenerProps: BaseApplicationListenerProps = {
            port: ecsConfig.loadBalancerConfig.sslCertIamArn ? 443 : 80,
            open: ecsConfig.internetFacing,
            certificates: ecsConfig.loadBalancerConfig.sslCertIamArn
                ? [{ certificateArn: ecsConfig.loadBalancerConfig.sslCertIamArn }]
                : undefined,
            sslPolicy: ecsConfig.loadBalancerConfig.sslCertIamArn ? SslPolicy.RECOMMENDED_TLS : SslPolicy.RECOMMENDED,
        };

        const listener = loadBalancer.addListener(
            createCdkId([identifier, 'ApplicationListener']),
            listenerProps,
        );
        const protocol = listenerProps.port === 443 ? 'https' : 'http';

        // Add targets
        const loadBalancerHealthCheckConfig = ecsConfig.loadBalancerConfig.healthCheckConfig;
        const targetGroup = listener.addTargets(createCdkId([ecsConfig.identifier, 'TgtGrp']), {
            targetGroupName: createCdkId([config.deploymentName, ecsConfig.identifier], 32, 2).toLowerCase(),
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

        // ALB metric for ASG to use for auto scaling EC2 instances
        // TODO: Update this to step scaling for embedding models??
        const requestCountPerTargetMetric = new Metric({
            metricName: ecsConfig.autoScalingConfig.metricConfig.albMetricName,
            namespace: 'AWS/ApplicationELB',
            dimensionsMap: {
                TargetGroup: targetGroup.targetGroupFullName,
                LoadBalancer: loadBalancer.loadBalancerFullName,
            },
            statistic: Stats.SAMPLE_COUNT,
            period: Duration.seconds(ecsConfig.autoScalingConfig.metricConfig.duration),
        });

        // Create hook to scale on ALB metric count exceeding thresholds
        autoScalingGroup.scaleToTrackMetric(createCdkId([ecsConfig.identifier, 'ScalingPolicy']), {
            metric: requestCountPerTargetMetric,
            targetValue: ecsConfig.autoScalingConfig.metricConfig.targetValue,
            estimatedInstanceWarmup: Duration.seconds(ecsConfig.autoScalingConfig.metricConfig.duration),
        });

        const domain =
            ecsConfig.loadBalancerConfig.domainName !== null
                ? ecsConfig.loadBalancerConfig.domainName
                : loadBalancer.loadBalancerDnsName;
        this.endpointUrl = `${protocol}://${domain}`;

        // Update
        this.container = container;
        this.taskRole = taskRole;
    }
}

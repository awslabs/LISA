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
import { Metric, Stats } from 'aws-cdk-lib/aws-cloudwatch';
import { InstanceType, IVpc, SecurityGroup } from 'aws-cdk-lib/aws-ec2';
import { Repository } from 'aws-cdk-lib/aws-ecr';
import {
    AmiHardwareType,
    Cluster,
    ContainerDefinition,
    ContainerImage,
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
    ApplicationProtocol,
    BaseApplicationListenerProps,
    NetworkLoadBalancer,
    NetworkTargetGroup
} from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import { IRole, ManagedPolicy, Role } from 'aws-cdk-lib/aws-iam';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';

import { createCdkId } from '../core/utils';
import { BaseProps, Ec2Metadata, ECSConfig, EcsSourceType } from '../schema';
import { AlbTarget } from 'aws-cdk-lib/aws-elasticloadbalancingv2-targets';

/**
 * Properties for the ECSCluster Construct.
 *
 * @property {IVpc} vpc - The virtual private cloud (VPC).
 * @property {SecurityGroups} securityGroups - The security group that the ECS cluster should use.
 * @property {ECSConfig} ecsConfig - The configuration for the cluster.
 */
type ECSClusterProps = {
    ecsConfig: ECSConfig;
    securityGroup: SecurityGroup;
    vpc: IVpc;
    addNlb?: boolean;
} & BaseProps;

/**
 * Create an ECS model.
 */
export class ECSCluster extends Construct {
    /** ECS Cluster container definition */
    public readonly container: ContainerDefinition;

    /** IAM role associated with the ECS Cluster task */
    public readonly taskRole: IRole;

    /** Endpoint URL of application load balancer for the cluster. */
    public readonly endpointUrl: string;

    public readonly alb: ApplicationLoadBalancer;

    public readonly nlb: NetworkLoadBalancer;

    /**
   * @param {Construct} scope - The parent or owner of the construct.
   * @param {string} id - The unique identifier for the construct within its scope.
   * @param {ECSClusterProps} props - The properties of the construct.
   */
    constructor (scope: Construct, id: string, props: ECSClusterProps) {
        super(scope, id);
        const { config, vpc, securityGroup, ecsConfig } = props;

        // Create ECS cluster
        const cluster = new Cluster(this, createCdkId([ecsConfig.identifier, 'Cl']), {
            clusterName: createCdkId([config.deploymentName, ecsConfig.identifier], 32, 2),
            vpc: vpc,
            containerInsights: !config.region.includes('iso'),
        });

        // Create auto scaling group
        const autoScalingGroup = cluster.addCapacity(createCdkId([ecsConfig.identifier, 'ASG']), {
            instanceType: new InstanceType(ecsConfig.instanceType),
            machineImage: EcsOptimizedImage.amazonLinux2(ecsConfig.amiHardwareType),
            minCapacity: ecsConfig.autoScalingConfig.minCapacity,
            maxCapacity: ecsConfig.autoScalingConfig.maxCapacity,
            cooldown: Duration.seconds(ecsConfig.autoScalingConfig.cooldown),
            groupMetrics: [GroupMetrics.all()],
            instanceMonitoring: Monitoring.DETAILED,
            newInstancesProtectedFromScaleIn: false,
            defaultInstanceWarmup: Duration.seconds(ecsConfig.autoScalingConfig.defaultInstanceWarmup),
            blockDevices: [
                {
                    deviceName: '/dev/xvda',
                    volume: BlockDeviceVolume.ebs(30, {
                        encrypted: true,
                    }),
                },
            ],
        });

        const environment = ecsConfig.environment;
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
        }

        // Create ECS task definition
        const taskRole = Role.fromRoleArn(
            this,
            createCdkId([ecsConfig.identifier, 'TR']),
            StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/roles/${ecsConfig.identifier}`),
        );
        const taskDefinition = new Ec2TaskDefinition(this, createCdkId([ecsConfig.identifier, 'Ec2TaskDefinition']), {
            family: createCdkId([config.deploymentName, ecsConfig.identifier], 32, 2),
            taskRole: taskRole,
            volumes: volumes,
        });

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

        let image: ContainerImage;
        switch (ecsConfig.containerConfig.image.type) {
            case EcsSourceType.ECR: {
                const repository = Repository.fromRepositoryArn(
                    this,
                    createCdkId([ecsConfig.identifier, 'Repo']),
                    ecsConfig.containerConfig.image.repositoryArn,
                );
                image = ContainerImage.fromEcrRepository(repository, ecsConfig.containerConfig.image.tag);
                break;
            }
            case EcsSourceType.REGISTRY: {
                image = ContainerImage.fromRegistry(ecsConfig.containerConfig.image.registry);
                break;
            }
            case EcsSourceType.TARBALL: {
                image = ContainerImage.fromTarball(ecsConfig.containerConfig.image.path);
                break;
            }
            default: {
                image = ContainerImage.fromAsset(ecsConfig.containerConfig.image.path, { buildArgs: ecsConfig.buildArgs });
                break;
            }
        }

        const container = taskDefinition.addContainer(createCdkId([ecsConfig.identifier, 'Container']), {
            containerName: createCdkId([config.deploymentName, ecsConfig.identifier], 32, 2),
            image,
            environment,
            logging: LogDriver.awsLogs({ streamPrefix: ecsConfig.identifier }),
            gpuCount: Ec2Metadata.get(ecsConfig.instanceType).gpuCount,
            memoryReservationMiB: Ec2Metadata.get(ecsConfig.instanceType).memory - ecsConfig.containerMemoryBuffer,
            portMappings: [{ hostPort: 80, containerPort: 8080, protocol: Protocol.TCP }],
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
        this.alb = new ApplicationLoadBalancer(this, createCdkId([ecsConfig.identifier, 'ALB']), {
            deletionProtection: config.removalPolicy !== RemovalPolicy.DESTROY,
            internetFacing: false,
            loadBalancerName: createCdkId([config.deploymentName, ecsConfig.identifier, 'ALB'], 32, 2),
            dropInvalidHeaderFields: true,
            securityGroup,
            vpc,
        });

        if (props.addNlb) {
            this.nlb = new NetworkLoadBalancer(this, createCdkId([ecsConfig.identifier, 'NLB']), {
                deletionProtection: config.removalPolicy !== RemovalPolicy.DESTROY,
                crossZoneEnabled: false,
                internetFacing: false,
                loadBalancerName: createCdkId([config.deploymentName, ecsConfig.identifier, 'NLB'], 32, 2),
                securityGroups: [securityGroup],
                vpc,
            });

            const nlbListener = this.nlb.addListener('Listener', { port: 80 });

            const albTargetGroup = new NetworkTargetGroup(this, 'ALB-Target-Group', {
                port: 80,
                vpc: vpc,
                targets: [new AlbTarget(this.alb, 80)],
                healthCheck: {
                    path: ecsConfig.loadBalancerConfig.healthCheckConfig.path
                }
            });

            nlbListener.addTargetGroups('ALB-Target-Group', albTargetGroup);
        }

        // Add listener
        const listenerProps: BaseApplicationListenerProps = {
            port: 80,
            open: false,
            protocol: ApplicationProtocol.HTTP
        };

        const listener = this.alb.addListener(
            createCdkId([ecsConfig.identifier, 'ApplicationListener']),
            listenerProps,
        );

        // Add targets
        const loadBalancerHealthCheckConfig = ecsConfig.loadBalancerConfig.healthCheckConfig;
        const targetGroup = listener.addTargets(createCdkId([ecsConfig.identifier, 'TgtGrp']), {
            targetGroupName: createCdkId([config.deploymentName, ecsConfig.identifier], 32, 2),
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
            metricName: ecsConfig.autoScalingConfig.metricConfig.AlbMetricName,
            namespace: 'AWS/ApplicationELB',
            dimensionsMap: {
                TargetGroup: targetGroup.targetGroupFullName,
                LoadBalancer: this.alb.loadBalancerFullName,
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
          : this.alb.loadBalancerDnsName;
        const endpoint = `http://${domain}`;
        this.endpointUrl = endpoint;

        // Update
        this.container = container;
        this.taskRole = taskRole;
    }
}

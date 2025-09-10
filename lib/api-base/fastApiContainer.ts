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

import { CfnOutput } from 'aws-cdk-lib';
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
    constructor(scope: Construct, id: string, props: FastApiContainerProps) {
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
                        MCPWORKBENCH_BUCKET: [config.deploymentName, config.deploymentStage, 'MCPWorkbench'].join('-').toLowerCase()
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

        if (tokenTable) {
            Object.entries(apiCluster.taskRoles).forEach(([_, role]) => {
                tokenTable.grantReadData(role);
            })
        }

        this.endpoint = apiCluster.endpointUrl;

        // Update
        this.containers = Object.values(apiCluster.containers);
        this.taskRoles = apiCluster.taskRoles;

        // CFN output
        new CfnOutput(this, `${props.apiName}Url`, {
            value: apiCluster.endpointUrl,
        });
    }
}

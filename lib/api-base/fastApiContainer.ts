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
import { AmiHardwareType } from 'aws-cdk-lib/aws-ecs';
import { Construct } from 'constructs';
import { dump as yamlDump } from 'js-yaml';

import { ECSCluster, ECSTasks } from './ecsCluster';
import { BaseProps, Ec2Metadata, ECSConfig, EcsSourceType } from '../schema';
import { Vpc } from '../networking/vpc';
import { REST_API_PATH } from '../util';
import * as child_process from 'child_process';
import * as path from 'path';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';

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
    managementKeyName: string;
} & BaseProps;

/**
 * FastApiContainer Construct.
 */
export class FastApiContainer extends Construct {
    /** ECS Cluster **/
    public readonly apiCluster: ECSCluster;

    /** FastAPI URL **/
    public readonly endpoint: string;

    /**
   * @param {Construct} scope - The parent or owner of the construct.
   * @param {string} id - The unique identifier for the construct within its scope.
   * @param {FastApiContainerProps} props - The properties of the construct.
   */
    constructor (scope: Construct, id: string, props: FastApiContainerProps) {
        super(scope, id);

        const { config, securityGroup, tokenTable, vpc, managementKeyName} = props;

        const instanceType = 'm5.xlarge';

        const buildArgs: Record<string, string> | undefined = {
            BASE_IMAGE: config.baseImage,
            PYPI_INDEX_URL: config.pypiConfig.indexUrl,
            PYPI_TRUSTED_HOST: config.pypiConfig.trustedHost,
            LITELLM_CONFIG: yamlDump(config.litellmConfig),
        };

        // Add build config overrides if provided
        if (config.restApiConfig.buildConfig?.PRISMA_CACHE_DIR) {
            buildArgs.PRISMA_CACHE_DIR = config.restApiConfig.buildConfig.PRISMA_CACHE_DIR;
        }

        // Add MCP Workbench build config overrides if provided
        if (config.mcpWorkbenchBuildConfig) {
            Object.entries(config.mcpWorkbenchBuildConfig).forEach(([key, value]) => {
                if (value) {
                    buildArgs[key] = value;
                }
            });
        }

        // Environment variables for all containers
        const environment: Record<string, string> = {
            LOG_LEVEL: config.logLevel,
            AWS_REGION: config.region,
            AWS_REGION_NAME: config.region, // for supporting SageMaker endpoints in LiteLLM
            THREADS: Ec2Metadata.get(instanceType).vCpus.toString(),
            USE_AUTH: 'true',
            AUTHORITY: config.authConfig!.authority,
            CLIENT_ID: config.authConfig!.clientId,
            ADMIN_GROUP: config.authConfig!.adminGroup,
            USER_GROUP: config.authConfig!.userGroup,
            JWT_GROUPS_PROP: config.authConfig!.jwtGroupsProperty,
            MANAGEMENT_KEY_NAME: managementKeyName
        };

        if (tokenTable) {
            environment.TOKEN_TABLE_NAME = tokenTable.tableName;
        }

        // Requires mount point /etc/pki from host
        if (config.region.includes('iso')) {
            environment.SSL_CERT_DIR = '/etc/pki/tls/certs';
            environment.SSL_CERT_FILE = config.certificateAuthorityBundle;
            environment.REQUESTS_CA_BUNDLE = config.certificateAuthorityBundle;
            environment.AWS_CA_BUNDLE = config.certificateAuthorityBundle;
            environment.CURL_CA_BUNDLE = config.certificateAuthorityBundle;
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
                blockDeviceVolumeSize: 50,
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
            tasks: {},
            // reserve at least enough memory for each task and a buffer for the instance to use
            containerMemoryBuffer: Ec2Metadata.get(instanceType).memory - (INSTANCE_MEMORY_RESERVATION + SERVE_CONTAINER_MEMORY_RESERVATION + (config.deployMcpWorkbench ? WORKBENCH_CONTAINER_MEMORY_RESERVATION : 0)),
            instanceType,
            internetFacing: config.restApiConfig.internetFacing,
            loadBalancerConfig: {
                healthCheckConfig: {
                    path: '/health',
                    interval: 60,
                    timeout: 30,
                    healthyThresholdCount: 2,
                    unhealthyThresholdCount: 3  // Reduced from 10 to 3 for faster failure detection
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
            vpc,
            environment
        });

        // Add the REST API task to the cluster (default target, no priority/conditions)
        apiCluster.addTask(ECSTasks.REST, {
            environment: {
                LITELLM_KEY: config.litellmConfig.db_key,
                OPENAI_API_KEY: config.litellmConfig.db_key,
                TIKTOKEN_CACHE_DIR: '/app/TIKTOKEN_CACHE',
            },
            containerConfig: {
                image: restApiImage,
                healthCheckConfig,
                environment: {},
                sharedMemorySize: 0
            },
            containerMemoryReservationMiB: SERVE_CONTAINER_MEMORY_RESERVATION,
            applicationTarget: {
                port: 8080
            }
        });

        if (tokenTable) {
            // Grant token table access to REST API task role only
            const restTaskRole = apiCluster.taskRoles[ECSTasks.REST];
            if (restTaskRole) {
                tokenTable.grantReadData(restTaskRole);
            }
        }

        this.apiCluster = apiCluster;
        this.endpoint = apiCluster.endpointUrl;

        new StringParameter(scope, 'FastApiEndpoint', {
            parameterName: `${config.deploymentPrefix}/serve/endpoint`,
            stringValue: this.endpoint
        });

        // CFN output
        new CfnOutput(this, `${props.apiName}Url`, {
            value: apiCluster.endpointUrl,
        });
    }
}

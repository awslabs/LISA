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
import { SecurityGroup } from 'aws-cdk-lib/aws-ec2';
import { AmiHardwareType, ContainerDefinition } from 'aws-cdk-lib/aws-ecs';
import { IRole } from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';
import { dump as yamlDump } from 'js-yaml';

import { ECSCluster } from './ecsCluster';
import { BaseProps, Ec2Metadata, EcsSourceType } from '../schema';
import { Vpc } from '../networking/vpc';

// This is the amount of memory to buffer (or subtract off) from the total instance memory, if we don't include this,
// the container can have a hard time finding available RAM resources to start and the tasks will fail deployment
const CONTAINER_MEMORY_BUFFER = 1024 * 2;

/**
 * Properties for FastApiContainer Construct.
 *
 * @property {IVpc} vpc - The virtual private cloud (VPC).
 * @property {SecurityGroup} securityGroups - The security groups of the application.
 */
type FastApiContainerProps = {
    apiName: string;
    resourcePath: string;
    securityGroup: SecurityGroup;
    tokenTable: ITable | undefined;
    vpc: Vpc;
} & BaseProps;

/**
 * FastApiContainer Construct.
 */
export class FastApiContainer extends Construct {
    /** FastAPI container */
    public readonly container: ContainerDefinition;

    /** FastAPI IAM task role */
    public readonly taskRole: IRole;

    /** FastAPI URL **/
    public readonly endpoint: string;

    /**
   * @param {Construct} scope - The parent or owner of the construct.
   * @param {string} id - The unique identifier for the construct within its scope.
   * @param {RestApiProps} props - The properties of the construct.
   */
    constructor (scope: Construct, id: string, props: FastApiContainerProps) {
        super(scope, id);

        const { config, securityGroup, tokenTable, vpc } = props;

        const buildArgs: Record<string, string> | undefined = {
            BASE_IMAGE: 'python:3.10',
            PYPI_INDEX_URL: config.pypiConfig.indexUrl,
            PYPI_TRUSTED_HOST: config.pypiConfig.trustedHost,
            LITELLM_CONFIG: yamlDump(config.litellmConfig),
        };
        const environment: Record<string, string> = {
            LOG_LEVEL: config.logLevel,
            AWS_REGION: config.region,
            AWS_REGION_NAME: config.region, // for supporting SageMaker endpoints in LiteLLM
            THREADS: Ec2Metadata.get('m5.large').vCpus.toString(),
            LITELLM_KEY: config.litellmConfig.db_key,
        };

        if (config.restApiConfig.internetFacing) {
            environment.USE_AUTH = 'true';
            environment.AUTHORITY = config.authConfig!.authority;
            environment.CLIENT_ID = config.authConfig!.clientId;
            environment.ADMIN_GROUP = config.authConfig!.adminGroup;
            environment.JWT_GROUPS_PROP = config.authConfig!.jwtGroupsProperty;
        } else {
            environment.USE_AUTH = 'false';
        }

        if (tokenTable) {
            environment.TOKEN_TABLE_NAME = tokenTable.tableName;
        }

        const apiCluster = new ECSCluster(scope, `${id}-ECSCluster`, {
            config,
            ecsConfig: {
                amiHardwareType: AmiHardwareType.STANDARD,
                autoScalingConfig: {
                    blockDeviceVolumeSize: 30,
                    minCapacity: 1,
                    maxCapacity: 1,
                    cooldown: 60,
                    defaultInstanceWarmup: 60,
                    metricConfig: {
                        AlbMetricName: 'RequestCountPerTarget',
                        targetValue: 1000,
                        duration: 60,
                        estimatedInstanceWarmup: 30
                    }
                },
                buildArgs,
                containerConfig: {
                    image: {
                        baseImage: 'python:3.10',
                        path: 'lib/serve/rest-api',
                        type: EcsSourceType.ASSET
                    },
                    healthCheckConfig: {
                        command: ['CMD-SHELL', 'exit 0'],
                        interval: 10,
                        startPeriod: 30,
                        timeout: 5,
                        retries: 3
                    },
                    environment: {},
                    sharedMemorySize: 0
                },
                containerMemoryBuffer: CONTAINER_MEMORY_BUFFER,
                environment,
                identifier: props.apiName,
                instanceType: 'm5.large',
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
            },
            securityGroup,
            vpc
        });

        if (tokenTable) {
            tokenTable.grantReadData(apiCluster.taskRole);
        }

        this.endpoint = apiCluster.endpointUrl;

        // Update
        this.container = apiCluster.container;
        this.taskRole = apiCluster.taskRole;

        // CFN output
        new CfnOutput(this, `${props.apiName}Url`, {
            value: apiCluster.endpointUrl,
        });
    }
}

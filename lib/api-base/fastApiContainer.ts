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
import { SecurityGroup, IVpc } from 'aws-cdk-lib/aws-ec2';
import { AmiHardwareType, ContainerDefinition } from 'aws-cdk-lib/aws-ecs';
import { IRole } from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';
import { dump as yamlDump } from 'js-yaml';

import { ECSCluster } from './ecsCluster';
import { BaseProps, Ec2Metadata, EcsSourceType, FastApiContainerConfig } from '../schema';

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
    taskConfig: FastApiContainerConfig;
    tokenTable: ITable | undefined;
    vpc: IVpc;
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

        const { config, securityGroup, taskConfig, tokenTable, vpc } = props;

        let buildArgs: Record<string, string> | undefined = undefined;
        if (taskConfig.containerConfig.image.type === EcsSourceType.ASSET) {
            buildArgs = {
                BASE_IMAGE: taskConfig.containerConfig.image.baseImage,
                PYPI_INDEX_URL: config.pypiConfig.indexUrl,
                PYPI_TRUSTED_HOST: config.pypiConfig.trustedHost,
                LITELLM_CONFIG: yamlDump(config.litellmConfig),
            };
        }
        const environment: Record<string, string> = {
            LOG_LEVEL: config.logLevel,
            AWS_REGION: config.region,
            AWS_REGION_NAME: config.region, // for supporting SageMaker endpoints in LiteLLM
            THREADS: Ec2Metadata.get(taskConfig.instanceType).vCpus.toString(),
        };

        if (config.restApiConfig.internetFacing) {
            environment.USE_AUTH = 'true';
            environment.AUTHORITY = config.authConfig!.authority;
            environment.CLIENT_ID = config.authConfig!.clientId;
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
                autoScalingConfig: taskConfig.autoScalingConfig,
                buildArgs,
                containerConfig: taskConfig.containerConfig,
                containerMemoryBuffer: CONTAINER_MEMORY_BUFFER,
                environment,
                identifier: props.apiName,
                instanceType: taskConfig.instanceType,
                internetFacing: config.restApiConfig.internetFacing,
                loadBalancerConfig: taskConfig.loadBalancerConfig,
            },
            securityGroup,
            vpc,
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

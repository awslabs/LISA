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

// ECS Model Construct.
import { ISecurityGroup, IVpc, SubnetSelection } from 'aws-cdk-lib/aws-ec2';
import { AmiHardwareType } from 'aws-cdk-lib/aws-ecs';
import { Bucket } from 'aws-cdk-lib/aws-s3';
import { Construct } from 'constructs';

import { ECSCluster } from './ecsCluster';
import { getModelIdentifier } from './utils';
import { BaseProps, Config, Ec2Metadata, EcsClusterConfig, EcsSourceType } from '../../../lib/schema';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';

// This is the amount of memory to buffer (or subtract off) from the total instance memory, if we don't include this,
// the container can have a hard time finding available RAM resources to start and the tasks will fail deployment
const CONTAINER_MEMORY_BUFFER = 1024 * 5;

/**
 * Properties for the EcsModel Construct.
 *
 * @property {IVpc} vpc - The virtual private cloud (VPC).
 * @property {ISecurityGroup} securityGroup - The security group to use for the ECS cluster
 * @property {EcsClusterConfig} modelConfig - The model configuration.
 */
type ECSModelProps = {
    modelConfig: EcsClusterConfig;
    securityGroup: ISecurityGroup;
    vpc: IVpc;
    subnetSelection?: SubnetSelection;
} & BaseProps;

/**
 * Create an ECS model.
 */
export class EcsModel extends Construct {
    /** Model endpoint URL of application load balancer. */
    public readonly endpointUrl: string;

    /**
   * @param {Construct} scope - The parent or owner of the construct.
   * @param {string} id - The unique identifier for the construct within its scope.
   * @param {ECSModelProps} props - The properties of the construct.
   */
    constructor (scope: Construct, id: string, props: ECSModelProps) {
        super(scope, id);
        const { config, modelConfig, securityGroup, vpc, subnetSelection } = props;

        const modelCluster = new ECSCluster(scope, `${id}-ECC`, {
            config,
            ecsConfig: {
                amiHardwareType: AmiHardwareType.GPU,
                autoScalingConfig: modelConfig.autoScalingConfig,
                buildArgs: this.getBuildArguments(config, modelConfig),
                containerConfig: modelConfig.containerConfig,
                containerMemoryBuffer: CONTAINER_MEMORY_BUFFER,
                environment: this.getEnvironmentVariables(config, modelConfig),
                identifier: getModelIdentifier(modelConfig),
                instanceType: modelConfig.instanceType,
                internetFacing: false,
                loadBalancerConfig: modelConfig.loadBalancerConfig,
            },
            securityGroup,
            vpc,
            subnetSelection
        });

        // Single bucket for all models
        const s3BucketModels = Bucket.fromBucketName(this, 'Bucket', config.s3BucketModels);
        s3BucketModels.grantReadWrite(modelCluster.taskRole);

        // Update
        this.endpointUrl = modelCluster.endpointUrl;
    }

    /**
   * Generates environment variables for Docker at runtime based on the configuration. The environment variables
   * include the local model path, S3 bucket for models, model name, and other variables depending on the model type.
   *
   * @param {Config} config - The application configuration.
     * @param {EcsClusterConfig} modelConfig - Configuration for the specific model.
   * @returns {Object} An object containing the environment variables. The object has string keys and values, which
   *                   represent the environment variables for Docker at runtime.
   */
    private getEnvironmentVariables (config: Config, modelConfig: EcsClusterConfig): { [key: string]: string } {
        const environment: { [key: string]: string } = {
            LOCAL_MODEL_PATH: `${config.nvmeContainerMountPath}/model`,
            S3_BUCKET_MODELS: config.s3BucketModels,
            MODEL_NAME: modelConfig.modelName,
            LOCAL_CODE_PATH: modelConfig.localModelCode, // Only needed when s5cmd is used, but just keep for now
            AWS_REGION: config.region, // needed for s5cmd
            MANAGEMENT_KEY_NAME: StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/managementKeySecretName`)
        };

        if (modelConfig.modelType === 'embedding') {
            environment.SAGEMAKER_BASE_DIR = config.nvmeContainerMountPath;
        }

        if (config.mountS3DebUrl) {
            environment.S3_MOUNT_POINT = 's3-models-mount';
            // More threads than files during S3 mount point copy to NVMe is fine; by default use half threads
            environment.THREADS = Math.ceil(Ec2Metadata.get(modelConfig.instanceType).vCpus / 2).toString();
        }

        if (modelConfig.containerConfig.environment) {
            for (const [key, value] of Object.entries(modelConfig.containerConfig.environment)) {
                if (value !== null) {
                    environment[key] = String(value);
                }
            }
        }

        return environment;
    }

    /**
   * Generates build arguments for the Docker build based on the configuration. The build arguments include the base
   * image, and depending on the model type, either the local code path or the S3 deb URL.
   *
   * @param {Config} config - The application configuration.
     * @param {EcsClusterConfig} modelConfig - Configuration for the specific model.
   * @returns {Object} An object containing the build arguments. The object has string keys and values, which represent
   *                   the arguments for the Docker build.
   */
    private getBuildArguments (config: Config, modelConfig: EcsClusterConfig): { [key: string]: string } | undefined {
        if (modelConfig.containerConfig.image.type !== EcsSourceType.ASSET) {
            return undefined;
        }

        const buildArgs: { [key: string]: string } = {
            BASE_IMAGE: modelConfig.containerConfig.image.baseImage,
        };

        if (modelConfig.modelType === 'embedding') {
            buildArgs.LOCAL_CODE_PATH = modelConfig.localModelCode;
        }
        if (config.mountS3DebUrl) {
            buildArgs.MOUNTS3_DEB_URL = config.mountS3DebUrl;
        }
        if (config.pypiConfig.indexUrl) {
            buildArgs.PYPI_INDEX_URL = config.pypiConfig.indexUrl;
            buildArgs.PYPI_TRUSTED_HOST = config.pypiConfig.trustedHost;
        }
        if (config.condaUrl) {
            buildArgs.CONDA_URL = config.condaUrl;
        }

        return buildArgs;
    }
}

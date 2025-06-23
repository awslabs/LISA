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
import { z } from 'zod';

import { AmiHardwareType, EcsSourceType, RemovalPolicy } from './cdk';
import { RagRepositoryConfigSchema, RdsInstanceConfig } from './ragSchema';

/**
 * Custom security groups for application.
 *
 * @property {T SecurityGroup} ecsModelAlbSg - ECS model application load balancer security group.
 * @property {T SecurityGroup} restApiAlbSg - REST API application load balancer security group.
 * @property {T SecurityGroup} lambdaSg - Lambda security group.
 * @property {T SecurityGroup} liteLlmSg - litellm security group.
 * @property {T SecurityGroup} openSearchSg - OpenSearch security group used by RAG.
 * @property {T SecurityGroup} pgVectorSg - PGVector security group used by RAG.
 */
export type SecurityGroups<T> = {
    ecsModelAlbSg: T;
    restApiAlbSg: T;
    lambdaSg: T;
    liteLlmSg?: T;
    openSearchSg?: T;
    pgVectorSg?: T;
};

/**
 * Enum for different types of models.
 */
export enum ModelType {
    TEXTGEN = 'textgen',
    EMBEDDING = 'embedding',
}

/**
 * Configuration schema for Security Group imports.
 * These values are none/small/all, meaning a user can import any number of these or none of these.
 *
 * @property {string} modelSecurityGroupId - Security Group ID.
 * @property {string} restAlbSecurityGroupId - Security Group ID
 * @property {string} lambdaSecurityGroupId - Security Group ID
 * @property {string} liteLlmDbSecurityGroupId - Security Group ID.
 * @property {string} openSearchSecurityGroupId - Security Group ID.
 * @property {string} pgVectorSecurityGroupId - Security Group ID.
 */
export const SecurityGroupConfigSchema = z.object({
    modelSecurityGroupId: z.string().startsWith('sg-'),
    restAlbSecurityGroupId: z.string().startsWith('sg-'),
    lambdaSecurityGroupId: z.string().startsWith('sg-'),
    liteLlmDbSecurityGroupId: z.string().startsWith('sg-'),
    openSearchSecurityGroupId: z.string().startsWith('sg-').optional(),
    pgVectorSecurityGroupId: z.string().startsWith('sg-').optional(),
})
    .describe('Security Group Overrides used across stacks.');

const Ec2TypeSchema = z.object({
    memory: z.number().describe('Memory in megabytes (MB)'),
    gpuCount: z.number().min(0).describe('Number of GPUs'),
    nvmePath: z.string().default('').describe('Path to NVMe drive to mount'),
    maxThroughput: z.number().describe('Maximum network throughput in gigabits per second (Gbps)'),
    vCpus: z.number().describe('Number of virtual CPUs (vCPUs)'),
}).describe('Metadata for a specific EC2 instance type.');

type Ec2Type = z.infer<typeof Ec2TypeSchema>;

/**
 * Provides access to metadata for various EC2 instance types. This class is a utility that helps to retrieve the
 * metadata of specific EC2 instance types. The metadata includes properties like memory, GPU count, NVMe path,
 * maximum throughput, and virtual CPUs.
 */
export class Ec2Metadata {
    private static instances: Record<string, Ec2Type> = {
        'm5.large': {
            memory: 8 * 1000,
            gpuCount: 0,
            nvmePath: '',
            maxThroughput: 10,
            vCpus: 2,
        },
        'm5.xlarge': {
            memory: 16 * 1000,
            gpuCount: 0,
            nvmePath: '',
            maxThroughput: 10,
            vCpus: 4,
        },
        'm5.2xlarge': {
            memory: 32 * 1000,
            gpuCount: 0,
            nvmePath: '',
            maxThroughput: 10,
            vCpus: 8,
        },
        'm5d.xlarge': {
            memory: 16 * 1000,
            gpuCount: 0,
            nvmePath: '/dev/nvme1n1',
            maxThroughput: 10,
            vCpus: 4,
        },
        'm5d.2xlarge': {
            memory: 32 * 1000,
            gpuCount: 0,
            nvmePath: '/dev/nvme1n1',
            maxThroughput: 10,
            vCpus: 8,
        },
        'g4dn.xlarge': {
            memory: 16 * 1000,
            gpuCount: 1,
            nvmePath: '/dev/nvme1n1',
            maxThroughput: 25,
            vCpus: 4,
        },
        'g4dn.2xlarge': {
            memory: 32 * 1000,
            gpuCount: 1,
            nvmePath: '/dev/nvme1n1',
            maxThroughput: 25,
            vCpus: 8,
        },
        'g4dn.4xlarge': {
            memory: 64 * 1000,
            gpuCount: 1,
            nvmePath: '/dev/nvme1n1',
            maxThroughput: 25,
            vCpus: 16,
        },
        'g4dn.8xlarge': {
            memory: 128 * 1000,
            gpuCount: 1,
            nvmePath: '/dev/nvme1n1',
            maxThroughput: 50,
            vCpus: 32,
        },
        'g4dn.16xlarge': {
            memory: 256 * 1000,
            gpuCount: 1,
            nvmePath: '/dev/nvme1n1',
            maxThroughput: 50,
            vCpus: 64,
        },
        'g4dn.12xlarge': {
            memory: 192 * 1000,
            gpuCount: 4,
            nvmePath: '/dev/nvme1n1',
            maxThroughput: 50,
            vCpus: 48,
        },
        'g4dn.metal': {
            memory: 384 * 1000,
            gpuCount: 8,
            nvmePath: '/dev/nvme1n1',
            maxThroughput: 100,
            vCpus: 96,
        },
        'g5.xlarge': {
            memory: 16 * 1000,
            gpuCount: 1,
            nvmePath: '/dev/nvme1n1',
            maxThroughput: 10,
            vCpus: 4,
        },
        'g5.2xlarge': {
            memory: 32 * 1000,
            gpuCount: 1,
            nvmePath: '/dev/nvme1n1',
            maxThroughput: 10,
            vCpus: 8,
        },
        'g5.4xlarge': {
            memory: 64 * 1000,
            gpuCount: 1,
            nvmePath: '/dev/nvme1n1',
            maxThroughput: 25,
            vCpus: 16,
        },
        'g5.8xlarge': {
            memory: 128 * 1000,
            gpuCount: 1,
            nvmePath: '/dev/nvme1n1',
            maxThroughput: 25,
            vCpus: 32,
        },
        'g5.16xlarge': {
            memory: 256 * 1000,
            gpuCount: 1,
            nvmePath: '/dev/nvme1n1',
            maxThroughput: 25,
            vCpus: 64,
        },
        'g5.12xlarge': {
            memory: 192 * 1000,
            gpuCount: 4,
            nvmePath: '/dev/nvme1n1',
            maxThroughput: 40,
            vCpus: 48,
        },
        'g5.24xlarge': {
            memory: 384 * 1000,
            gpuCount: 4,
            nvmePath: '/dev/nvme1n1',
            maxThroughput: 50,
            vCpus: 96,
        },
        'g5.48xlarge': {
            memory: 768 * 1000,
            gpuCount: 8,
            nvmePath: '/dev/nvme1n1',
            maxThroughput: 100,
            vCpus: 192,
        },
        'g6.xlarge': {
            memory: 16 * 1000,
            gpuCount: 1,
            nvmePath: '/dev/nvme1n1',
            maxThroughput: 10,
            vCpus: 4,
        },
        'g6.2xlarge': {
            memory: 32 * 1000,
            gpuCount: 1,
            nvmePath: '/dev/nvme1n1',
            maxThroughput: 10,
            vCpus: 8,
        },
        'g6.4xlarge': {
            memory: 64 * 1000,
            gpuCount: 1,
            nvmePath: '/dev/nvme1n1',
            maxThroughput: 25,
            vCpus: 16,
        },
        'g6.8xlarge': {
            memory: 128 * 1000,
            gpuCount: 1,
            nvmePath: '/dev/nvme1n1',
            maxThroughput: 25,
            vCpus: 32,
        },
        'g6.16xlarge': {
            memory: 256 * 1000,
            gpuCount: 1,
            nvmePath: '/dev/nvme1n1',
            maxThroughput: 25,
            vCpus: 64,
        },
        'g6.12xlarge': {
            memory: 192 * 1000,
            gpuCount: 4,
            nvmePath: '/dev/nvme1n1',
            maxThroughput: 40,
            vCpus: 48,
        },
        'g6.24xlarge': {
            memory: 384 * 1000,
            gpuCount: 4,
            nvmePath: '/dev/nvme1n1',
            maxThroughput: 50,
            vCpus: 96,
        },
        'g6.48xlarge': {
            memory: 768 * 1000,
            gpuCount: 8,
            nvmePath: '/dev/nvme1n1',
            maxThroughput: 100,
            vCpus: 192,
        },
        'g6e.xlarge': {
            memory: 32 * 1000,
            gpuCount: 1,
            nvmePath: '/dev/nvme1n1',
            maxThroughput: 20,
            vCpus: 4,
        },
        'g6e.2xlarge': {
            memory: 64 * 1000,
            gpuCount: 1,
            nvmePath: '/dev/nvme1n1',
            maxThroughput: 20,
            vCpus: 8,
        },
        'g6e.4xlarge': {
            memory: 128 * 1000,
            gpuCount: 1,
            nvmePath: '/dev/nvme1n1',
            maxThroughput: 20,
            vCpus: 16,
        },
        'g6e.8xlarge': {
            memory: 256 * 1000,
            gpuCount: 1,
            nvmePath: '/dev/nvme1n1',
            maxThroughput: 25,
            vCpus: 32,
        },
        'g6e.16xlarge': {
            memory: 512 * 1000,
            gpuCount: 1,
            nvmePath: '/dev/nvme1n1',
            maxThroughput: 35,
            vCpus: 64,
        },
        'g6e.12xlarge': {
            memory: 384 * 1000,
            gpuCount: 4,
            nvmePath: '/dev/nvme1n1',
            maxThroughput: 100,
            vCpus: 48,
        },
        'g6e.24xlarge': {
            memory: 768 * 1000,
            gpuCount: 4,
            nvmePath: '/dev/nvme1n1',
            maxThroughput: 200,
            vCpus: 96,
        },
        'g6e.48xlarge': {
            memory: 1536 * 1000,
            gpuCount: 8,
            nvmePath: '/dev/nvme1n1',
            maxThroughput: 400,
            vCpus: 192,
        },
        'p4d.24xlarge': {
            memory: 1152 * 1000,
            gpuCount: 8,
            nvmePath: '/dev/nvme1n1',
            maxThroughput: 400,
            vCpus: 96,
        },
        'p5.48xlarge': {
            memory: 2000 * 1000,
            gpuCount: 8,
            nvmePath: '/dev/nvme1n1',
            maxThroughput: 3200,
            vCpus: 192,
        },
        'p5e.48xlarge': {
            memory: 2000 * 1000,
            gpuCount: 8,
            nvmePath: '/dev/nvme1n1',
            maxThroughput: 3200,
            vCpus: 192,
        },
        'p5en.48xlarge': {
            memory: 2000 * 1000,
            gpuCount: 8,
            nvmePath: '/dev/nvme1n1',
            maxThroughput: 3200,
            vCpus: 192,
        },
    };

    /**
     * Getter method to access EC2 metadata. Retrieves the metadata for a specific EC2 instance type.
     *
     * @param {string} key - .describe('The key representing the EC2 instance type (e.g., 'g4dn.xlarge').')
     * @throws {Error} Throws an error if no metadata is found for the specified EC2 instance type.
     * @returns {Ec2Type} The metadata for the specified EC2 instance type.
     */
    static get (key: string): Ec2Type {
        const instance = this.instances[key];
        if (!instance) {
            throw new Error(`No EC2 type found for key: ${key}`);
        }
        return instance;
    }

    /**
     * Get EC2 instances defined with metadata.
     *
     * @returns {string[]} Array of EC2 instances.
     */
    static getValidInstanceKeys (): string[] {
        return Object.keys(this.instances);
    }
}

export const VALID_INSTANCE_KEYS = Ec2Metadata.getValidInstanceKeys() as [string, ...string[]];

const ContainerHealthCheckConfigSchema = z.object({
    command: z.array(z.string()).default(['CMD-SHELL', 'exit 0']).describe('The command to run for health checks'),
    interval: z.number().default(10).describe('The time interval between health checks, in seconds.'),
    startPeriod: z.number().default(30).describe('The time to wait before starting the first health check, in seconds.'),
    timeout: z.number().default(5).describe('The maximum time allowed for each health check to complete, in seconds'),
    retries: z.number().default(2).describe('The number of times to retry a failed health check before considering the container as unhealthy.'),
})
    .describe('Configuration for container health checks');

export const ImageTarballAsset = z.object({
    path: z.string(),
    type: z.literal(EcsSourceType.TARBALL)
})
    .describe('Container image that will use tarball on disk');

export const ImageSourceAsset = z.object({
    baseImage: z.string(),
    path: z.string(),
    type: z.literal(EcsSourceType.ASSET),
})
    .describe('Container image that will be built based on Dockerfile and assets at the supplied path');

export const ImageECRAsset = z.object({
    repositoryArn: z.string(),
    tag: z.string().optional(),
    type: z.literal(EcsSourceType.ECR),
})
    .describe('Container image that will be pulled from the specified ECR repository');

export const ImageRegistryAsset = z.object({
    registry: z.string(),
    type: z.literal(EcsSourceType.REGISTRY),
})
    .describe('Container image that will be pulled from the specified public registry');

export const ImageExternalAsset = z.object({
    type: z.literal(EcsSourceType.EXTERNAL),
    code: z.any()
})
    .describe('Container image from external source. Use provided image without modification.');

export const ImageAssetSchema = z.union([ImageTarballAsset, ImageSourceAsset, ImageECRAsset, ImageRegistryAsset, ImageExternalAsset]);
export type ImageAsset = z.infer<typeof ImageAssetSchema>;

export const ContainerConfigSchema = z.object({
    image: ImageAssetSchema.describe('Base image for the container.'),
    environment: z
        .record(z.any())
        .transform((obj) => {
            return Object.entries(obj).reduce(
                (acc, [key, value]) => {
                    acc[key] = String(value);
                    return acc;
                },
                {} as Record<string, string>,
            );
        })
        .default({})
        .describe('Environment variables for the container.'),
    sharedMemorySize: z.number().min(0).default(0).describe('The value for the size of the /dev/shm volume.'),
    healthCheckConfig: ContainerHealthCheckConfigSchema.default({}),
}).describe('Configuration for the container.');

const HealthCheckConfigSchema = z.object({
    path: z.string().describe('Path for the health check.'),
    interval: z.number().default(30).describe('Interval in seconds between health checks.'),
    timeout: z.number().default(10).describe('Timeout in seconds for each health check.'),
    healthyThresholdCount: z.number().default(2).describe('Number of consecutive successful health checks required to consider the target healthy.'),
    unhealthyThresholdCount: z.number().default(2).describe('Number of consecutive failed health checks required to consider the target unhealthy.'),
})
    .describe('Health check configuration for the load balancer.');

export const LoadBalancerConfigSchema = z.object({
    sslCertIamArn: z.string().nullish().default(null).describe('SSL certificate IAM ARN for load balancer.'),
    healthCheckConfig: HealthCheckConfigSchema,
    domainName: z.string().nullish().default(null).describe('Domain name to use instead of the load balancer\'s default DNS name.'),
})
    .describe('Configuration for load balancer settings.');

export const MetricConfigSchema = z.object({
    albMetricName: z.string().describe('Name of the ALB metric.'),
    targetValue: z.number().describe('Target value for the metric.'),
    duration: z.number().default(60).describe('Duration in seconds for metric evaluation.'),
    estimatedInstanceWarmup: z.number().min(0).default(180).describe('Estimated warm-up time in seconds until a newly launched instance can send metrics to CloudWatch.'),
})
    .describe('Metric configuration for ECS auto scaling.');

export const AutoScalingConfigSchema = z.object({
    blockDeviceVolumeSize: z.number().min(30).default(30),
    minCapacity: z.number().min(1).default(1).describe('Minimum capacity for auto scaling. Must be at least 1.'),
    maxCapacity: z.number().min(1).default(2).describe('Maximum capacity for auto scaling. Must be at least 1.'),
    defaultInstanceWarmup: z.number().default(180).describe('Default warm-up time in seconds until a newly launched instance can'),
    cooldown: z.number().min(1).default(420).describe('Cool down period in seconds between scaling activities.'),
    metricConfig: MetricConfigSchema,
})
    .describe('Configuration for auto scaling settings.');


/**
 * Configuration schema for an ECS model.
 *
 * @property {AmiHardwareType} amiHardwareType - Name of the model.
 * @property {AutoScalingConfigSchema} autoScalingConfig - Configuration for auto scaling settings.
 * @property {Record<string,string>} buildArgs - Optional build args to be applied when creating the
 *                                              task container if containerConfig.image.type is ASSET
 * @property {ContainerConfigSchema} containerConfig - Configuration for the container.
 * @property {number} [containerMemoryBuffer=2048] - This is the amount of memory to buffer (or subtract off)
 *                                                from the total instance memory, if we don't include this,
 *                                                the container can have a hard time finding available RAM
 *                                                resources to start and the tasks will fail deployment
 * @property {Record<string,string>} environment - Environment variables set on the task container
 * @property {identifier} modelType - Unique identifier for the cluster which will be used when naming resources
 * @property {string} instanceType - EC2 instance type for running the model.
 * @property {boolean} [internetFacing=false] - Whether or not the cluster will be configured as internet facing
 * @property {LoadBalancerConfigSchema} loadBalancerConfig - Configuration for load balancer settings.
 */
export const EcsBaseConfigSchema = z.object({
    amiHardwareType: z.nativeEnum(AmiHardwareType).describe('Name of the model.'),
    autoScalingConfig: AutoScalingConfigSchema.describe('Configuration for auto scaling settings.'),
    buildArgs: z.record(z.string()).optional()
        .describe('Optional build args to be applied when creating the task container if containerConfig.image.type is ASSET'),
    containerConfig: ContainerConfigSchema,
    containerMemoryBuffer: z.number().default(1024 * 2)
        .describe('This is the amount of memory to buffer (or subtract off)  from the total instance memory, ' +
            'if we don\'t include this, the container can have a hard time finding available RAM resources to start and the tasks will fail deployment'),
    environment: z.record(z.string()).describe('Environment variables set on the task container'),
    identifier: z.string(),
    instanceType: z.enum(VALID_INSTANCE_KEYS).describe('EC2 instance type for running the model.'),
    internetFacing: z.boolean().default(false).describe('Whether or not the cluster will be configured as internet facing'),
    loadBalancerConfig: LoadBalancerConfigSchema,
});


/**
 * Details and configurations of a registered model.
 *
 * @property {string} provider - Model provider, of the form <engine>.<type>.
 * @property {string} modelName - The unique name that identifies the model.
 * @property {string} modelId - The unique user-provided name for the model.
 * @property {ModelType} modelType - Specifies the type of model (e.g., 'textgen', 'embedding').
 * @property {string} endpointUrl - The URL endpoint where the model can be accessed or invoked.
 * @property {boolean} streaming - Indicates whether the model supports streaming capabilities.
 */
export type RegisteredModel = {
    provider: string;
    modelId: string;
    modelName: string;
    modelType: ModelType;
    endpointUrl: string;
    streaming?: boolean;
};


/**
 * Type representing configuration for an ECS model.
 */
type EcsBaseConfig = z.infer<typeof EcsBaseConfigSchema>;

/**
 * Union model type representing various model configurations.
 */
export type ECSConfig = EcsBaseConfig;

/**
 * Configuration schema for an ECS model.
 *
 * @property {string} modelName - Name of the model.
 * @property {string} modelId - An optional short id to use when creating cdk ids for model related
 *                              resources
 * @property {boolean} [deploy=true] - Whether to deploy model.
 * @property {boolean} [streaming=null] - Whether the model supports streaming.
 * @property {string} modelType - Type of model.
 * @property {string} instanceType - EC2 instance type for running the model.
 * @property {string} inferenceContainer - Prebuilt inference container for serving model.
 * @property {ContainerConfigSchema} containerConfig - Configuration for the container.
 * @property {AutoScalingConfigSchema} autoScalingConfig - Configuration for auto scaling settings.
 * @property {LoadBalancerConfigSchema} loadBalancerConfig - Configuration for load balancer settings.
 * @property {string} [localModelCode='/opt/model-code'] - Path in container for local model code.
 * @property {string} [modelHosting='ecs'] - Model hosting.
 */
export const EcsClusterConfigSchema = z
    .object({
        modelName: z.string(),
        modelId: z.string().optional(),
        deploy: z.boolean().default(true),
        streaming: z.boolean().nullable().default(null),
        modelType: z.nativeEnum(ModelType),
        instanceType: z.enum(VALID_INSTANCE_KEYS),
        inferenceContainer: z
            .union([z.literal('tgi'), z.literal('tei'), z.literal('instructor'), z.literal('vllm')])
            .refine((data) => {
                return !data.includes('.'); // string cannot contain a period
            }),
        containerConfig: ContainerConfigSchema,
        autoScalingConfig: AutoScalingConfigSchema,
        loadBalancerConfig: LoadBalancerConfigSchema,
        localModelCode: z.string().default('/opt/model-code'),
        modelHosting: z
            .string()
            .default('ecs')
            .refine((data) => {
                return !data.includes('.'); // string cannot contain a period
            }),
    })
    .refine(
        (data) => {
            // 'textgen' type must have boolean streaming, 'embedding' type must have null streaming
            const isValidForTextgen = data.modelType === 'textgen' && typeof data.streaming === 'boolean';
            const isValidForEmbedding = data.modelType === 'embedding' && data.streaming === null;

            return isValidForTextgen || isValidForEmbedding;
        },
        {
            message: `For 'textgen' models, 'streaming' must be true or false.
            For 'embedding' models, 'streaming' must not be set.`,
            path: ['streaming'],
        },
    );

/**
 * Type representing configuration for an ECS model.
 */
export type EcsClusterConfig = z.infer<typeof EcsClusterConfigSchema>;

const InferenceContainer = {
    tgi: 'tgi',
    tei: 'tei',
    instructor: 'instructor',
    vllm: 'vllm',
} as const;

const InferenceContainerSchema = z.object({
    tgi: z.literal(InferenceContainer.tgi).describe('Text Generation Inference'),
    tei: z.literal(InferenceContainer.tei).describe('Text Embeddings Inference'),
    instructor: z.literal(InferenceContainer.instructor).describe('Instructor Library'),
    vllm: z.literal(InferenceContainer.vllm).describe('vLLM (Virtual Large Language Model) Library'),
});

const EcsModelConfigSchema = z
    .object({
        modelName: z.string().describe('Name of the model.'),
        baseImage: z.string().describe('Base image for the container.'),
        inferenceContainer: z
            .union([InferenceContainerSchema.shape.tgi, InferenceContainerSchema.shape.tei, InferenceContainerSchema.shape.instructor, InferenceContainerSchema.shape.vllm])
            .refine((data) => {
                return !data.includes('.'); // string cannot contain a period
            })
            .describe('Prebuilt inference container for serving model.'),
    })
    .describe('Configuration schema for an ECS model.');

/**
 * Type representing configuration for an ECS model.
 */
type EcsModelConfig = z.infer<typeof EcsModelConfigSchema>;

/**
 * Union model type representing various model configurations.
 */
export type ModelConfig = EcsModelConfig;

const AuthConfigSchema = z.object({
    authority: z.string().transform((value) => {
        if (value.endsWith('/')) {
            return value.slice(0, -1);
        } else {
            return value;
        }
    })
        .describe('URL of OIDC authority.'),
    clientId: z.string().describe('Client ID for OIDC IDP .'),
    adminGroup: z.string().default('').describe('Name of the admin group.'),
    jwtGroupsProperty: z.string().default('').describe('Name of the JWT groups property.'),
    additionalScopes: z.array(z.string()).default([]).describe('Additional JWT scopes to request.'),
}).describe('Configuration schema for authorization.');

const FastApiContainerConfigSchema = z.object({
    internetFacing: z.boolean().default(true).describe('Whether the REST API ALB will be configured as internet facing.'),
    domainName: z.string().nullish().default(null),
    sslCertIamArn: z.string().nullish().default(null).describe('ARN of the self-signed cert to be used throughout the system'),
    imageConfig: ImageAssetSchema.optional().describe('Override image configuration for ECS FastAPI Containers'),
    rdsConfig: RdsInstanceConfig
        .default({
            dbName: 'postgres',
            username: 'postgres',
            dbPort: 5432,
        })
        .refine(
            (config) => {
                return !config.dbHost && !config.passwordSecretId;
            },
            {
                message:
                    'We do not allow using an existing DB for LiteLLM because of its requirement in internal model management ' +
                    'APIs. Please do not define the dbHost or passwordSecretId fields for the FastAPI container DB config.',
            },
        ),
}).describe('Configuration schema for REST API.');


const RagFileProcessingConfigSchema = z.object({
    chunkSize: z.number().min(100).max(10000),
    chunkOverlap: z.number().min(0),
})
    .describe('Configuration schema for RAG file processing. Determines the chunk size and chunk overlap when processing documents.');

const PypiConfigSchema = z.object({
    indexUrl: z.string().default('').describe('URL for the pypi index.'),
    trustedHost: z.string().default('').describe('Trusted host for pypi.'),
})
    .describe('Configuration schema for pypi');

/**
 * Enum for different types of stack synthesizers
 */
export enum stackSynthesizerType {
    CliCredentialsStackSynthesizer = 'CliCredentialsStackSynthesizer',
    DefaultStackSynthesizer = 'DefaultStackSynthesizer',
    LegacyStackSynthesizer = 'LegacyStackSynthesizer',
}

const ApiGatewayConfigSchema = z
    .object({
        domainName: z.string().nullish().default(null).describe('Custom domain name for API Gateway Endpoint'),
    })
    .optional()
    .describe('Configuration schema for API Gateway Endpoint');

const LiteLLMConfig = z.object({
    db_key: z.string().refine(
        (key) => key.startsWith('sk-'), // key needed for model management actions
        'Key string must be defined for model management operations, and it must start with "sk-".' +
        'This can be any string, and a random UUID is recommended. Example: sk-f132c7cc-059c-481b-b5ca-a42e191672aa',
    ),
    general_settings: z.any().optional(),
    litellm_settings: z.any().optional(),
    router_settings: z.any().optional(),
    environment_variables: z.any().optional(),
})
    .describe('Core LiteLLM configuration - see https://litellm.vercel.app/docs/proxy/configs#all-settings for more details about each field.');

const RoleConfig = z.object({
    DockerImageBuilderDeploymentRole: z.string().max(64),
    DockerImageBuilderEC2Role: z.string().max(64),
    DockerImageBuilderRole: z.string().max(64),
    DocsRole: z.string().max(64).optional(),
    DocsDeployerRole: z.string().max(64).optional(),
    ECSModelDeployerRole: z.string().max(64),
    ECSModelTaskRole: z.string().max(64),
    ECSRestApiRole: z.string().max(64),
    ECSRestApiExRole: z.string().max(64),
    LambdaExecutionRole: z.string().max(64),
    LambdaConfigurationApiExecutionRole: z.string().max(64),
    ModelApiRole: z.string().max(64),
    ModelsSfnLambdaRole: z.string().max(64),
    ModelSfnRole: z.string().max(64),
    RagLambdaExecutionRole: z.string().max(64).optional(),
    RestApiAuthorizerRole: z.string().max(64),
    S3ReaderRole: z.string().max(64).optional(),
    UIDeploymentRole: z.string().max(64).optional(),
    VectorStoreCreatorRole: z.string().max(64).optional(),
})
    .describe('Role overrides used across stacks.');


export const RawConfigObject = z.object({
    appName: z.string().default('lisa').describe('Name of the application.'),
    profile: z
        .string()
        .nullish()
        .transform((value) => value ?? '')
        .describe('AWS CLI profile for deployment.'),
    deploymentName: z.string().default('prod').describe('Name of the deployment.'),
    accountNumber: z
        .number()
        .or(z.string())
        .transform((value) => value.toString())
        .refine((value) => value.length === 12, {
            message: 'AWS account number should be 12 digits. If your account ID starts with 0, then please surround the ID with quotation marks.',
        })
        .describe('AWS account number for deployment. Must be 12 digits.'),
    region: z.string().describe('AWS region for deployment.'),
    partition: z.string().default('aws').describe('AWS partition for deployment.'),
    domain: z.string().default('amazonaws.com').describe('AWS domain for deployment'),
    restApiConfig: FastApiContainerConfigSchema,
    vpcId: z.string().optional().describe('VPC ID for the application. (e.g. vpc-0123456789abcdef)'),
    subnets: z.array(z.object({
        subnetId: z.string().startsWith('subnet-'),
        ipv4CidrBlock: z.string(),
        availabilityZone: z.string().describe('Specify the availability zone for the subnet in the format {region}{letter} (e.g., us-east-1a).'),
    })).optional().describe('Array of subnet objects for the application. These contain a subnetId(e.g. [subnet-fedcba9876543210] and ipv4CidrBlock'),
    securityGroupConfig: SecurityGroupConfigSchema.optional(),
    deploymentStage: z.string().default('prod').describe('Deployment stage for the application.'),
    removalPolicy: z.enum([RemovalPolicy.DESTROY, RemovalPolicy.RETAIN])
        .default(RemovalPolicy.DESTROY)
        .describe('Removal policy for resources (destroy or retain).'),
    runCdkNag: z.boolean().default(false).describe('Whether to run CDK Nag checks.'),
    privateEndpoints: z.boolean().default(false).describe('Whether to use privateEndpoints for REST API.'),
    s3BucketModels: z.string().describe('S3 bucket for models.'),
    mountS3DebUrl: z.string().describe('URL for S3-mounted Debian package.'),
    imageBuilderVolumeSize: z.number().default(30).describe('EC2 volume size for image builder. Needs to be large enough for system plus inference container.'),
    accountNumbersEcr: z
        .array(z.union([z.number(), z.string()]))
        .transform((arr) => arr.map(String))
        .refine((value) => value.every((num) => num.length === 12), {
            message: 'AWS account number should be 12 digits. If your account ID starts with 0, then please surround the ID with quotation marks.',
        })
        .optional()
        .describe('List of AWS account numbers for ECR repositories.'),
    deployRag: z.boolean().default(true).describe('Whether to deploy RAG stacks.'),
    deployChat: z.boolean().default(true).describe('Whether to deploy chat stacks.'),
    deployDocs: z.boolean().default(true).describe('Whether to deploy docs stacks.'),
    deployUi: z.boolean().default(true).describe('Whether to deploy UI stacks.'),
    logLevel: z.union([z.literal('DEBUG'), z.literal('INFO'), z.literal('WARNING'), z.literal('ERROR')])
        .default('DEBUG')
        .describe('Log level for application.'),
    authConfig: AuthConfigSchema.optional().describe('Authorization configuration.'),
    roles: RoleConfig.optional(),
    pypiConfig: PypiConfigSchema.default({
        indexUrl: '',
        trustedHost: '',
    }).describe('Pypi configuration.'),
    baseImage: z.string().default('python:3.11').describe('Base image used for LISA serve components'),
    nodejsImage: z.string().default('public.ecr.aws/lambda/nodejs:18').describe('Base image used for LISA NodeJS lambda deployments'),
    condaUrl: z.string().default('').describe('Conda URL configuration'),
    certificateAuthorityBundle: z.string().default('').describe('Certificate Authority Bundle file'),
    ragRepositories: z.array(RagRepositoryConfigSchema).describe('Rag Repository configuration.'),
    ragFileProcessingConfig: RagFileProcessingConfigSchema.optional().describe('Rag file processing configuration.'),
    ecsModels: z.array(EcsModelConfigSchema).optional().describe('Array of ECS model configurations.'),
    apiGatewayConfig: ApiGatewayConfigSchema,
    nvmeHostMountPath: z.string().default('/nvme').describe('Host path for NVMe drives.'),
    nvmeContainerMountPath: z.string().default('/nvme').describe('Container path for NVMe drives.'),
    tags: z
        .array(
            z.object({
                Key: z.string(),
                Value: z.string(),
            }),
        )
        .optional()
        .describe('Array of key-value pairs for tagging.'),
    tagContainers: z.boolean().default(false).describe('Add repeatable container tags to each cdk deployed container'),
    deploymentPrefix: z.string().optional().describe('Prefix for deployment resources.'),
    webAppAssetsPath: z.string().optional().describe('Optional path to precompiled webapp assets. If not specified the web application will be built at deploy time.'),
    ecsModelDeployerPath: z.string().optional().describe('Optional path to precompiled ecs model deployer. If not specified the ecs model deployer will be built at deploy time.'),
    vectorStoreDeployerPath: z.string().optional().describe('Optional path to precompiled vector store deployer. If not specified the vector store deployer will be built at deploy time.'),
    documentsPath: z.string().optional().describe('Optional path to precompiled LISA documents. If not specified the LISA docs will be built at deploy time.'),
    lambdaPath: z.any().optional().describe('Optional path to precompiled LISA lambda. If not specified the LISA lambda will be built at deploy time.'),
    lambdaLayerAssets: z
        .object({
            authorizerLayerPath: z.string().optional().describe('Lambda Authorizer code path'),
            commonLayerPath: z.string().optional().describe('Lambda common layer code path'),
            fastapiLayerPath: z.string().optional().describe('Lambda API code path'),
            ragLayerPath: z.string().optional().describe('Lambda RAG layer code path'),
            sdkLayerPath: z.string().optional().describe('Lambda SDK layer code path'),
        })
        .optional()
        .describe('Configuration for local Lambda layer code'),
    permissionsBoundaryAspect: z
        .object({
            permissionsBoundaryPolicyName: z.string(),
            rolePrefix: z.string().max(20).optional(),
            policyPrefix: z.string().max(20).optional(),
            instanceProfilePrefix: z.string().optional(),
        })
        .optional()
        .describe('Aspect CDK injector for permissions. Ref: https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_iam.PermissionsBoundary.html'),
    stackSynthesizer: z.nativeEnum(stackSynthesizerType).optional().describe('Set the stack synthesize type. Ref: https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.StackSynthesizer.html'),
    litellmConfig: LiteLLMConfig,
    convertInlinePoliciesToManaged: z.boolean().optional().default(false).describe('Convert inline policies to managed policies'),
    iamRdsAuth: z.boolean().optional().default(false).describe('Enable IAM authentication for RDS'),
});

export const RawConfigSchema = RawConfigObject
    .refine((config) => (config.pypiConfig.indexUrl && config.region.includes('iso')) || !config.region.includes('iso'), {
        message: 'Must set PypiConfig if in an iso region',
    })
    .refine(
        (config) => {
            return !config.deployUi || config.deployChat;
        },
        {
            message: 'Chat stack is needed for UI stack. You must set deployChat to true if deployUi is true.',
        },
    )
    .refine(
        (config) => {
            return (
                !(config.deployChat || config.deployRag || config.deployUi) ||
                config.authConfig
            );
        },
        {
            message:
                'An auth config must be provided when deploying the chat, RAG, or UI stacks or when deploying an internet ' +
                'facing ALB. Check that `deployChat`, `deployRag`, `deployUi`, and `restApiConfig.internetFacing` are all ' +
                'false or that an `authConfig` is provided.',
        },
    )
    .describe('Raw application configuration schema.');

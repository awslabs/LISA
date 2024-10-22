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

// Models for schema validation.
import * as fs from 'fs';
import * as path from 'path';

import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import { AmiHardwareType } from 'aws-cdk-lib/aws-ecs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import { z } from 'zod';

const HERE: string = path.resolve(__dirname);
const VERSION_PATH: string = path.resolve(HERE, '..', 'VERSION');
const VERSION: string = fs.readFileSync(VERSION_PATH, 'utf8').trim();
const PYTHON_VERSIONS: Record<string, lambda.Runtime> = {
    PYTHON_3_8: lambda.Runtime.PYTHON_3_8,
    PYTHON_3_9: lambda.Runtime.PYTHON_3_9,
    PYTHON_3_10: lambda.Runtime.PYTHON_3_10,
    PYTHON_3_11: lambda.Runtime.PYTHON_3_11,
};

const REMOVAL_POLICIES: Record<string, cdk.RemovalPolicy> = {
    destroy: cdk.RemovalPolicy.DESTROY,
    retain: cdk.RemovalPolicy.RETAIN,
};

/**
 * Configuration schema for Lambda.
 */
const lambdaConfigSchema = z.object({
    pythonRuntime: z
        .union([z.literal('PYTHON_3_8'), z.literal('PYTHON_3_9'), z.literal('PYTHON_3_10'), z.literal('PYTHON_3_11')])
        .default('PYTHON_3_9')
        .transform((value) => PYTHON_VERSIONS[value]),
    logLevel: z.union([z.literal('DEBUG'), z.literal('INFO'), z.literal('WARNING'), z.literal('ERROR')]),
});

/**
 * Enum for different types of models.
 */
export enum ModelType {
    TEXTGEN = 'textgen',
    EMBEDDING = 'embedding',
}

/**
 * Enum for different types of ECS container image sources.
 */
export enum EcsSourceType {
    ASSET = 'asset',
    ECR = 'ecr',
    REGISTRY = 'registry',
    TARBALL = 'tarball',
}

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
 * Custom security groups for application.
 *
 * @property {ec2.SecurityGroup} ecsModelAlbSg - ECS model application load balancer security group.
 * @property {ec2.SecurityGroup} restApiAlbSg - REST API application load balancer security group.
 * @property {ec2.SecurityGroup} lambdaSecurityGroup - Lambda security group.
 */
export type SecurityGroups = {
    ecsModelAlbSg: ec2.SecurityGroup;
    restApiAlbSg: ec2.SecurityGroup;
    lambdaSecurityGroup: ec2.SecurityGroup;
};

/**
 * Metadata for a specific EC2 instance type.
 *
 * @property {number} memory - Memory in megabytes (MB).
 * @property {number} gpuCount - Number of GPUs.
 * @property {string} nvmePath - Path to NVMe drive to mount.
 * @property {number} maxThroughput - Maximum network throughput in gigabits per second (Gbps).
 * @property {number} vCpus - Number of virtual CPUs (vCPUs).
 */
const Ec2TypeSchema = z.object({
    memory: z.number(),
    gpuCount: z.number().min(0),
    nvmePath: z.string().optional().default(''),
    maxThroughput: z.number(),
    vCpus: z.number(),
});

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
        'p4d.24xlarge': {
            memory: 1152 * 1000,
            gpuCount: 8,
            nvmePath: '/dev/nvme1n1',
            maxThroughput: 400,
            vCpus: 96,
        },
    };

    /**
   * Getter method to access EC2 metadata. Retrieves the metadata for a specific EC2 instance type.
   *
   * @param {string} key - The key representing the EC2 instance type (e.g., 'g4dn.xlarge').
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

const VALID_INSTANCE_KEYS = Ec2Metadata.getValidInstanceKeys() as [string, ...string[]];

/**
 * Configuration for container health checks.
 *
 * @property {string[]} [command=['CMD-SHELL', 'exit 0']] - The command to run for health checks.
 * @property {number} [interval=10] - The time interval between health checks, in seconds.
 * @property {number} [startPeriod=30] - The time to wait before starting the first health check, in seconds.
 * @property {number} [timeout=5] - The maximum time allowed for each health check to complete, in seconds.
 * @property {number} [retries=2] - The number of times to retry a failed health check before considering the container
 *                                  as unhealthy.
 */
const ContainerHealthCheckConfigSchema = z.object({
    command: z.array(z.string()).default(['CMD-SHELL', 'exit 0']),
    interval: z.number().default(10),
    startPeriod: z.number().default(30),
    timeout: z.number().default(5),
    retries: z.number().default(2),
});

/**
 * Container image that will use tarball on disk
 */
const ImageTarballAsset = z.object({
    path: z.string(),
    type: z.literal(EcsSourceType.TARBALL),
});

/**
 * Container image that will be built based on Dockerfile and assets at the supplied path
 */
const ImageSourceAsset = z.object({
    baseImage: z.string(),
    path: z.string(),
    type: z.literal(EcsSourceType.ASSET),
});

/**
 * Container image that will be pulled from the specified ECR repository
 */
const ImageECRAsset = z.object({
    repositoryArn: z.string(),
    tag: z.string().optional(),
    type: z.literal(EcsSourceType.ECR),
});

/**
 * Container image that will be pulled from the specified public registry
 */
const ImageRegistryAsset = z.object({
    registry: z.string(),
    type: z.literal(EcsSourceType.REGISTRY),
});

/**
 * Configuration for a container.
 *
 * @property {string} baseImage - Base image for the container.
 * @property {Record<string, string>} [environment={}] - Environment variables for the container.
 * @property {ContainerHealthCheckConfig} [healthCheckConfig={}] - Health check configuration for the container.
 * @property {number} [sharedMemorySize=0] - The value for the size of the /dev/shm volume.
 */
const ContainerConfigSchema = z.object({
    image: z.union([ImageTarballAsset, ImageSourceAsset, ImageECRAsset, ImageRegistryAsset]),
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
        .default({}),
    sharedMemorySize: z.number().min(0).optional().default(0),
    healthCheckConfig: ContainerHealthCheckConfigSchema.default({}),
});

/**
 * Configuration schema for health checks in load balancer settings.
 *
 * @property {string} path - Path for the health check.
 * @property {number} [interval=30] - Interval in seconds between health checks.
 * @property {number} [timeout=10] - Timeout in seconds for each health check.
 * @property {number} [healthyThresholdCount=2] - Number of consecutive successful health checks required to consider
 *                                                the target healthy.
 * @property {number} [unhealthyThresholdCount=2] - Number of consecutive failed health checks required to consider the
 *                                                  target unhealthy.
 */
const HealthCheckConfigSchema = z.object({
    path: z.string(),
    interval: z.number().default(30),
    timeout: z.number().default(10),
    healthyThresholdCount: z.number().default(2),
    unhealthyThresholdCount: z.number().default(2),
});

/**
 * Configuration schema for the load balancer.
 *
 * @property {string} [sslCertIamArn=null] - SSL certificate IAM ARN for load balancer.
 * @property {HealthCheckConfig} healthCheckConfig - Health check configuration for the load balancer.
 * @property {string} domainName - Domain name to use instead of the load balancer's default DNS name.
 */
const LoadBalancerConfigSchema = z.object({
    sslCertIamArn: z.string().optional().nullable().default(null),
    healthCheckConfig: HealthCheckConfigSchema,
    domainName: z.string().optional().nullable().default(null),
});

/**
 * Configuration schema for ECS auto scaling metrics.
 *
 * @property {string} AlbMetricName - Name of the ALB metric.
 * @property {number} targetValue - Target value for the metric.
 * @property {number} [duration=60] - Duration in seconds for metric evaluation.
 * @property {number} [estimatedInstanceWarmup=180] - Estimated warm-up time in seconds until a newly launched instance
 *                                                    can send metrics to CloudWatch.
 *
 */
const MetricConfigSchema = z.object({
    AlbMetricName: z.string(),
    targetValue: z.number(),
    duration: z.number().default(60),
    estimatedInstanceWarmup: z.number().min(0).default(180),
});

/**
 * Configuration schema for ECS auto scaling settings.
*
* @property {number} [minCapacity=1] - Minimum capacity for auto scaling. Must be at least 1.
* @property {number} [maxCapacity=2] - Maximum capacity for auto scaling. Must be at least 1.
* @property {number} [cooldown=420] - Cool down period in seconds between scaling activities.
* @property {number} [defaultInstanceWarmup=180] - Default warm-up time in seconds until a newly launched instance can
                                                   send metrics to CloudWatch.
* @property {MetricConfig} metricConfig - Metric configuration for auto scaling.
*/
const AutoScalingConfigSchema = z.object({
    blockDeviceVolumeSize: z.number().min(30).default(30),
    minCapacity: z.number().min(1).default(1),
    maxCapacity: z.number().min(1).default(2),
    defaultInstanceWarmup: z.number().default(180),
    cooldown: z.number().min(1).default(420),
    metricConfig: MetricConfigSchema,
});

/**
 * Configuration schema for an ECS model.
 *
 * @property {AmiHardwareType} amiHardwareType - Name of the model.
 * @property {AutoScalingConfigSchema} autoScalingConfig - Configuration for auto scaling settings.
 * @property {Record<string,string>} buildArgs - Optional build args to be applied when creating the
 *                                              task container if containerConfig.image.type is ASSET
 * @property {ContainerConfig} containerConfig - Configuration for the container.
 * @property {number} [containerMemoryBuffer=2048] - This is the amount of memory to buffer (or subtract off)
 *                                                from the total instance memory, if we don't include this,
 *                                                the container can have a hard time finding available RAM
 *                                                resources to start and the tasks will fail deployment
 * @property {Record<string,string>} environment - Environment variables set on the task container
 * @property {identifier} modelType - Unique identifier for the cluster which will be used when naming resources
 * @property {string} instanceType - EC2 instance type for running the model.
 * @property {boolean} [internetFacing=false] - Whether or not the cluster will be configured as internet facing
 * @property {LoadBalancerConfig} loadBalancerConfig - Configuration for load balancer settings.
 */
const EcsBaseConfigSchema = z.object({
    amiHardwareType: z.nativeEnum(AmiHardwareType),
    autoScalingConfig: AutoScalingConfigSchema,
    buildArgs: z.record(z.string()).optional(),
    containerConfig: ContainerConfigSchema,
    containerMemoryBuffer: z.number().default(1024 * 2),
    environment: z.record(z.string()),
    identifier: z.string(),
    instanceType: z.enum(VALID_INSTANCE_KEYS),
    internetFacing: z.boolean().default(false),
    loadBalancerConfig: LoadBalancerConfigSchema,
});

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
 * @property {string} baseImage - Base image for the container.
 * @property {string} inferenceContainer - Prebuilt inference container for serving model.
 */
const EcsModelConfigSchema = z
    .object({
        modelName: z.string(),
        baseImage: z.string(),
        inferenceContainer: z
            .union([z.literal('tgi'), z.literal('tei'), z.literal('instructor'), z.literal('vllm')])
            .refine((data) => {
                return !data.includes('.'); // string cannot contain a period
            })
    });

/**
 * Type representing configuration for an ECS model.
 */
type EcsModelConfig = z.infer<typeof EcsModelConfigSchema>;

/**
 * Union model type representing various model configurations.
 */
export type ModelConfig = EcsModelConfig;

/**
 * Configuration schema for authorization.
 *
 * @property {string} [authority=null] - URL of OIDC authority.
 * @property {string} [clientId=null] - Client ID for OIDC IDP .
 * @property {string} [adminGroup=null] - Name of the admin group.
 * @property {string} [jwtGroupsProperty=null] - Name of the JWT groups property.
 * @property {string[]} [additionalScopes=null] - Additional JWT scopes to request.
 */
const AuthConfigSchema = z.object({
    authority: z.string().transform((value) => {
        if (value.endsWith('/')) {
            return value.slice(0, -1);
        } else {
            return value;
        }
    }),
    clientId: z.string(),
    adminGroup: z.string().optional().default(''),
    jwtGroupsProperty: z.string().optional().default(''),
    additionalScopes: z.array(z.string()).optional().default([]),
});

/**
 * Configuration schema for RDS Instances needed for LiteLLM scaling or PGVector RAG operations.
 *
 * The optional fields can be omitted to create a new database instance, otherwise fill in all fields to use
 * an existing database instance.
 *
 * @property {string} username - Database username.
 * @property {string} passwordSecretId - SecretsManager Secret ID that stores an existing database password.
 * @property {string} dbHost - Database hostname for existing database instance.
 * @property {string} dbName - Database name for existing database instance.
 * @property {number} dbPort - Port to open on the database instance.
 */
const RdsInstanceConfig = z.object({
    username: z.string().optional().default('postgres'),
    passwordSecretId: z.string().optional(),
    dbHost: z.string().optional(),
    dbName: z.string().optional().default('postgres'),
    dbPort: z.number().optional().default(5432),
});

/**
 * Configuration schema for REST API.
 *
 * @property {string} instanceType - EC2 instance type.
 * @property {ContainerConfig} containerConfig - Configuration for the container.
 * @property {AutoScalingConfigSchema} autoScalingConfig - Configuration for auto scaling settings.
 * @property {LoadBalancerConfig} loadBalancerConfig - Configuration for load balancer settings.
 * @property {boolean} [internetFacing=true] - Whether or not the REST API ALB will be configured as internet facing.
 * @property {RdsInstanceConfig} rdsConfig - Configuration for LiteLLM scaling database.
 */
const FastApiContainerConfigSchema = z.object({
    apiVersion: z.literal('v2'),
    instanceType: z.enum(VALID_INSTANCE_KEYS),
    containerConfig: ContainerConfigSchema,
    autoScalingConfig: AutoScalingConfigSchema,
    loadBalancerConfig: LoadBalancerConfigSchema,
    internetFacing: z.boolean().default(true),
    rdsConfig: RdsInstanceConfig.optional()
        .default({
            dbName: 'postgres',
            username: 'postgres',
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
});

/**
 * Enum for different types of RAG repositories available
 */
export enum RagRepositoryType {
    OPENSEARCH = 'opensearch',
    PGVECTOR = 'pgvector',
}

const OpenSearchNewClusterConfig = z.object({
    dataNodes: z.number().min(1),
    dataNodeInstanceType: z.string(),
    masterNodes: z.number().min(0),
    masterNodeInstanceType: z.string(),
    volumeSize: z.number().min(10),
    multiAzWithStandby: z.boolean().default(false),
});

const OpenSearchExistingClusterConfig = z.object({
    endpoint: z.string(),
});

/**
 * Configuration schema for RAG repository. Defines settings for OpenSearch.
 */
const RagRepositoryConfigSchema = z
    .object({
        repositoryId: z.string(),
        type: z.nativeEnum(RagRepositoryType),
        opensearchConfig: z.union([OpenSearchExistingClusterConfig, OpenSearchNewClusterConfig]).optional(),
        rdsConfig: RdsInstanceConfig.optional(),
    })
    .refine((input) => {
        if (
            (input.type === RagRepositoryType.OPENSEARCH && input.opensearchConfig === undefined) ||
      (input.type === RagRepositoryType.PGVECTOR && input.rdsConfig === undefined)
        ) {
            return false;
        }
        return true;
    });

/**
 * Configuration schema for RAG file processing. Determines the chunk size and chunk overlap when processing documents.
 */
const RagFileProcessingConfigSchema = z.object({
    chunkSize: z.number().min(100).max(10000),
    chunkOverlap: z.number().min(0),
});

/**
 * Configuration schema for pypi.
 *
 * @property {string} [indexUrl=''] - URL for the pypi index.
 * @property {string} [trustedHost=''] - Trusted host for pypi.
 */
const PypiConfigSchema = z.object({
    indexUrl: z.string().optional().default(''),
    trustedHost: z.string().optional().default(''),
});

/**
 * Enum for different types of stack synthesizers
 */
export enum stackSynthesizerType {
    CliCredentialsStackSynthesizer = 'CliCredentialsStackSynthesizer',
    DefaultStackSynthesizer = 'DefaultStackSynthesizer',
    LegacyStackSynthesizer = 'LegacyStackSynthesizer',
}

/**
 * Configuration schema for API Gateway Endpoint
 *
 * @property {string} domainName - Custom domain name for API Gateway Endpoint
 */
const ApiGatewayConfigSchema = z
    .object({
        domainName: z.string().optional().nullable().default(null),
    })
    .optional();

/**
 * Configuration for models inside the LiteLLM Config
 * See https://litellm.vercel.app/docs/proxy/configs#all-settings for more details.
 *
 * The `lisa_params` are custom for the LISA installation to add model metadata to allow the models to be referenced
 * correctly within the Chat UI. LiteLLM will ignore these parameters as it is not looking for them, and it will not
 * fail to initialize as a result of them existing.
 */
const LiteLLMModel = z.object({
    model_name: z.string(),
    litellm_params: z.object({
        model: z.string(),
        api_base: z.string().optional(),
        api_key: z.string().optional(),
        aws_region_name: z.string().optional(),
    }),
    lisa_params: z
        .object({
            streaming: z.boolean().nullable().default(null),
            model_type: z.nativeEnum(ModelType),
        })
        .refine(
            (data) => {
                // 'textgen' type must have boolean streaming, 'embedding' type must have null streaming
                const isValidForTextgen = data.model_type === 'textgen' && typeof data.streaming === 'boolean';
                const isValidForEmbedding = data.model_type === 'embedding' && data.streaming === null;

                return isValidForTextgen || isValidForEmbedding;
            },
            {
                message: `For 'textgen' models, 'streaming' must be true or false.
            For 'embedding' models, 'streaming' must not be set.`,
                path: ['streaming'],
            },
        ),
    model_info: z
        .object({
            id: z.string().optional(),
            mode: z.string().optional(),
            input_cost_per_token: z.number().optional(),
            output_cost_per_token: z.number().optional(),
            max_tokens: z.number().optional(),
            base_model: z.string().optional(),
        })
        .optional(),
});

/**
 * Core LiteLLM configuration.
 * See https://litellm.vercel.app/docs/proxy/configs#all-settings for more details about each field.
 */
const LiteLLMConfig = z.object({
    environment_variables: z.map(z.string(), z.string()).optional(),
    model_list: z
        .array(LiteLLMModel)
        .optional()
        .nullable()
        .default([])
        .transform((value) => value ?? []),
    litellm_settings: z.object({
    // ALL (https://github.com/BerriAI/litellm/blob/main/litellm/__init__.py)
        telemetry: z.boolean().default(false).optional(),
        drop_params: z.boolean().default(true).optional(),
    }),
    general_settings: z
        .object({
            completion_model: z.string().optional(),
            disable_spend_logs: z.boolean().optional(), // turn off writing each transaction to the db
            disable_master_key_return: z.boolean().optional(), // turn off returning master key on UI
            disable_reset_budget: z.boolean().optional(), // turn off reset budget scheduled task
            enable_jwt_auth: z.boolean().optional(), // allow proxy admin to auth in via jwt tokens with 'litellm_proxy_admin'
            enforce_user_param: z.boolean().optional(), // requires all openai endpoint requests to have a 'user' param
            allowed_routes: z.array(z.string()).optional(), // list of allowed proxy API routes a user can access. (JWT only)
            key_management_system: z.string().optional(), // either google_kms or azure_kms
            master_key: z.string().refine(
                (key) => key.startsWith('sk-'), // key needed for model management actions
                'Key string must be defined for model management operations, and it must start with "sk-".' +
                'This can be any string, and a random UUID is recommended. Example: sk-f132c7cc-059c-481b-b5ca-a42e191672aa',
            ),
            database_url: z.string().optional(),
            database_connection_pool_limit: z.number().optional(), // default 100
            database_connection_timeout: z.number().optional(), // default 60s
            database_type: z.string().optional(),
            database_args: z
                .object({
                    billing_mode: z.string().optional(),
                    read_capacity_units: z.number().optional(),
                    write_capacity_units: z.number().optional(),
                    ssl_verify: z.boolean().optional(),
                    region_name: z.string().optional(),
                    user_table_name: z.string().optional(),
                    key_table_name: z.string().optional(),
                    config_table_name: z.string().optional(),
                    spend_table_name: z.string().optional(),
                })
                .optional(),
            otel: z.boolean().optional(),
            custom_auth: z.string().optional(),
            max_parallel_requests: z.number().optional(),
            infer_model_from_keys: z.boolean().optional(),
            background_health_checks: z.boolean().optional(),
            health_check_interval: z.number().optional(),
            alerting: z.array(z.string()).optional(),
            alerting_threshold: z.number().optional(),
        }),
});

/**
 * Raw application configuration schema.
 *
 * @property {string} [appName='lisa'] - Name of the application.
 * @property {string} [profile=null] - AWS CLI profile for deployment.
 * @property {string} deploymentName - Name of the deployment.
 * @property {string} accountNumber - AWS account number for deployment. Must be 12 digits.
 * @property {string} region - AWS region for deployment.
 * @property {string} deploymentStage - Deployment stage for the application.
 * @property {string} removalPolicy - Removal policy for resources (destroy or retain).
 * @property {boolean} [runCdkNag=false] - Whether to run CDK Nag checks.
 * @property {lambdaConfigSchema} lambdaConfig - Lambda configuration.
 * @property {string} [lambdaSourcePath='./lambda'] - Path to Lambda source code dir.
 * @property {string} s3BucketModels - S3 bucket for models.
 * @property {string} mountS3DebUrl - URL for S3-mounted Debian package.
 * @property {string[]} [accountNumbersEcr=null] - List of AWS account numbers for ECR repositories.
 * @property {boolean} [deployRag=false] - Whether to deploy RAG stacks.
 * @property {boolean} [deployChat=true] - Whether to deploy chat stacks.
 * @property {boolean} [deployUi=true] - Whether to deploy UI stacks.
 * @property {string} logLevel - Log level for application.
 * @property {AuthConfigSchema} authConfig - Authorization configuration.
 * @property {FastApiContainerConfigSchema} restApiConfig - REST API configuration.
 * @property {RagRepositoryConfigSchema} ragRepositoryConfig - Rag Repository configuration.
 * @property {RagFileProcessingConfigSchema} ragFileProcessingConfig - Rag file processing configuration.
 * @property {EcsModelConfigSchema[]} ecsModels - Array of ECS model configurations.
 * @property {ApiGatewayConfigSchema} apiGatewayConfig - API Gateway Endpoint configuration.
 * @property {string} [nvmeHostMountPath='/nvme'] - Host path for NVMe drives.
 * @property {string} [nvmeContainerMountPath='/nvme'] - Container path for NVMe drives.
 * @property {Array<{ Key: string, Value: string }>} [tags=null] - Array of key-value pairs for tagging.
 * @property {string} [deploymentPrefix=null] - Prefix for deployment resources.
 * @property {string} [webAppAssetsPath=null] - Optional path to precompiled webapp assets. If not
 *                                              specified the web application will be built at deploy
 *                                              time.
 */
const RawConfigSchema = z
    .object({
        appName: z.string().default('lisa'),
        profile: z
            .string()
            .optional()
            .nullable()
            .transform((value) => value ?? ''),
        deploymentName: z.string(),
        accountNumber: z
            .number()
            .or(z.string())
            .transform((value) => value.toString())
            .refine((value) => value.length === 12, {
                message: 'AWS account number should be 12 digits. If your account ID starts with 0, then please surround the ID with quotation marks.',
            }),
        region: z.string(),
        vpcId: z.string().optional(),
        subnetIds: z.array(z.string()).optional(),
        deploymentStage: z.string(),
        removalPolicy: z.union([z.literal('destroy'), z.literal('retain')]).transform((value) => REMOVAL_POLICIES[value]),
        runCdkNag: z.boolean().default(false),
        privateEndpoints: z.boolean().optional().default(false),
        s3BucketModels: z.string(),
        mountS3DebUrl: z.string().optional(),
        accountNumbersEcr: z
            .array(z.union([z.number(), z.string()]))
            .transform((arr) => arr.map(String))
            .refine((value) => value.every((num) => num.length === 12), {
                message: 'AWS account number should be 12 digits. If your account ID starts with 0, then please surround the ID with quotation marks.',
            })
            .optional(),
        deployRag: z.boolean().optional().default(false),
        deployChat: z.boolean().optional().default(true),
        deployUi: z.boolean().optional().default(true),
        logLevel: z.union([z.literal('DEBUG'), z.literal('INFO'), z.literal('WARNING'), z.literal('ERROR')]),
        lambdaConfig: lambdaConfigSchema,
        lambdaSourcePath: z.string().optional().default('./lambda'),
        authConfig: AuthConfigSchema.optional(),
        pypiConfig: PypiConfigSchema.optional().default({
            indexUrl: '',
            trustedHost: '',
        }),
        condaUrl: z.string().optional().default(''),
        certificateAuthorityBundle: z.string().optional().default(''),
        ragRepositories: z.array(RagRepositoryConfigSchema).default([]),
        ragFileProcessingConfig: RagFileProcessingConfigSchema.optional(),
        restApiConfig: FastApiContainerConfigSchema,
        ecsModels: z.array(EcsModelConfigSchema).optional(),
        apiGatewayConfig: ApiGatewayConfigSchema.optional(),
        nvmeHostMountPath: z.string().default('/nvme'),
        nvmeContainerMountPath: z.string().default('/nvme'),
        tags: z
            .array(
                z.object({
                    Key: z.string(),
                    Value: z.string(),
                }),
            )
            .optional(),
        deploymentPrefix: z.string().optional(),
        webAppAssetsPath: z.string().optional(),
        lambdaLayerAssets: z
            .object({
                authorizerLayerPath: z.string().optional(),
                commonLayerPath: z.string().optional(),
                fastapiLayerPath: z.string().optional(),
                ragLayerPath: z.string().optional(),
                sdkLayerPath: z.string().optional(),
            })
            .optional(),
        systemBanner: z
            .object({
                text: z.string(),
                backgroundColor: z.string(),
                fontColor: z.string(),
            })
            .optional(),
        permissionsBoundaryAspect: z
            .object({
                permissionsBoundaryPolicyName: z.string(),
                rolePrefix: z.string().max(20).optional(),
                policyPrefix: z.string().max(20).optional(),
                instanceProfilePrefix: z.string().optional(),
            })
            .optional(),
        stackSynthesizer: z.nativeEnum(stackSynthesizerType).optional(),
        litellmConfig: LiteLLMConfig,
    })
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
                !(config.deployChat || config.deployRag || config.deployUi || config.restApiConfig.internetFacing) ||
        config.authConfig
            );
        },
        {
            message:
        'An auth config must be provided when deploying the chat, RAG, or UI stacks or when deploying an internet ' +
        'facing ALB. Check that `deployChat`, `deployRag`, `deployUi`, and `restApiConfig.internetFacing` are all ' +
        'false or that an `authConfig` is provided.',
        },
    );

/**
 * Apply transformations to the raw application configuration schema.
 *
 * @param {Object} rawConfig - The raw application configuration.
 * @returns {Object} The transformed application configuration.
 */
export const ConfigSchema = RawConfigSchema.transform((rawConfig) => {
    let deploymentPrefix = rawConfig.deploymentPrefix;

    if (!deploymentPrefix && rawConfig.appName && rawConfig.deploymentStage && rawConfig.deploymentName) {
        deploymentPrefix = `/${rawConfig.deploymentStage}/${rawConfig.deploymentName}/${rawConfig.appName}`;
    }

    let tags = rawConfig.tags;

    if (!tags && deploymentPrefix) {
        tags = [
            { Key: 'deploymentPrefix', Value: deploymentPrefix },
            { Key: 'deploymentName', Value: rawConfig.deploymentName },
            { Key: 'deploymentStage', Value: rawConfig.deploymentStage },
            { Key: 'region', Value: rawConfig.region },
            { Key: 'version', Value: VERSION },
        ];
    }

    let awsRegionArn;
    if (rawConfig.region.includes('iso-b')) {
        awsRegionArn = 'aws-iso-b';
    } else if (rawConfig.region.includes('iso')) {
        awsRegionArn = 'aws-iso';
    } else if (rawConfig.region.includes('gov')) {
        awsRegionArn = 'aws-gov';
    } else {
        awsRegionArn = 'aws';
    }

    return {
        ...rawConfig,
        deploymentPrefix: deploymentPrefix,
        tags: tags,
        awsRegionArn,
    };
});

/**
 * Application configuration type.
 */
export type Config = z.infer<typeof ConfigSchema>;

export type FastApiContainerConfig = z.infer<typeof FastApiContainerConfigSchema>;

/**
 * Basic properties required for a stack definition in CDK.
 *
 * @property {Config} config - The application configuration.
 */
export type BaseProps = {
    config: Config;
};

export type ConfigFile = Record<string, any>;

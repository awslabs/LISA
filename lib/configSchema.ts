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

import { AmiHardwareType, EbsDeviceVolumeType, EcsSourceType, RemovalPolicy } from './cdk';

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

const VALID_INSTANCE_KEYS = Ec2Metadata.getValidInstanceKeys() as [string, ...string[]];

const ContainerHealthCheckConfigSchema = z.object({
    command: z.array(z.string()).default(['CMD-SHELL', 'exit 0']).describe('The command to run for health checks'),
    interval: z.number().default(10).describe('The time interval between health checks, in seconds.'),
    startPeriod: z.number().default(30).describe('The time to wait before starting the first health check, in seconds.'),
    timeout: z.number().default(5).describe('The maximum time allowed for each health check to complete, in seconds'),
    retries: z.number().default(2).describe('The number of times to retry a failed health check before considering the container as unhealthy.'),
})
    .describe('Configuration for container health checks');

const ImageTarballAsset = z.object({
    path: z.string(),
    type: z.literal(EcsSourceType.TARBALL),
})
    .describe('Container image that will use tarball on disk');

const ImageSourceAsset = z.object({
    baseImage: z.string(),
    path: z.string(),
    type: z.literal(EcsSourceType.ASSET),
})
    .describe('Container image that will be built based on Dockerfile and assets at the supplied path');

const ImageECRAsset = z.object({
    repositoryArn: z.string(),
    tag: z.string().optional(),
    type: z.literal(EcsSourceType.ECR),
})
    .describe('Container image that will be pulled from the specified ECR repository');

const ImageRegistryAsset = z.object({
    registry: z.string(),
    type: z.literal(EcsSourceType.REGISTRY),
})
    .describe('Container image that will be pulled from the specified public registry');

const ContainerConfigSchema = z.object({
    image: z.union([ImageTarballAsset, ImageSourceAsset, ImageECRAsset, ImageRegistryAsset]).describe('Base image for the container.'),
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

const LoadBalancerConfigSchema = z.object({
    sslCertIamArn: z.string().nullish().default(null).describe('SSL certificate IAM ARN for load balancer.'),
    healthCheckConfig: HealthCheckConfigSchema,
    domainName: z.string().nullish().default(null).describe('Domain name to use instead of the load balancer\'s default DNS name.'),
})
    .describe('Configuration for load balancer settings.');

const MetricConfigSchema = z.object({
    AlbMetricName: z.string().describe('Name of the ALB metric.'),
    targetValue: z.number().describe('Target value for the metric.'),
    duration: z.number().default(60).describe('Duration in seconds for metric evaluation.'),
    estimatedInstanceWarmup: z.number().min(0).default(180).describe('Estimated warm-up time in seconds until a newly launched instance can send metrics to CloudWatch.'),
})
    .describe('Metric configuration for ECS auto scaling.');

const AutoScalingConfigSchema = z.object({
    blockDeviceVolumeSize: z.number().min(30).default(30),
    minCapacity: z.number().min(1).default(1).describe('Minimum capacity for auto scaling. Must be at least 1.'),
    maxCapacity: z.number().min(1).default(2).describe('Maximum capacity for auto scaling. Must be at least 1.'),
    defaultInstanceWarmup: z.number().default(180).describe('Default warm-up time in seconds until a newly launched instance can'),
    cooldown: z.number().min(1).default(420).describe('Cool down period in seconds between scaling activities.'),
    metricConfig: MetricConfigSchema,
})
    .describe('Configuration for auto scaling settings.');

const EcsBaseConfigSchema = z.object({
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
})
    .describe('Configuration schema for an ECS model');

/**
 * Type representing configuration for an ECS model.
 */
type EcsBaseConfig = z.infer<typeof EcsBaseConfigSchema>;

/**
 * Union model type representing various model configurations.
 */
export type ECSConfig = EcsBaseConfig;

const EcsModelConfigSchema = z
    .object({
        modelName: z.string().describe('Name of the model.'),
        baseImage: z.string().describe('Base image for the container.'),
        inferenceContainer: z
            .union([z.literal('tgi'), z.literal('tei'), z.literal('instructor'), z.literal('vllm')])
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

export const RdsInstanceConfig = z.object({
    username: z.string().default('postgres').describe('The username used for database connection.'),
    passwordSecretId: z.string().optional().describe('The SecretsManager Secret ID that stores the existing database password.'),
    dbHost: z.string().optional().describe('The database hostname for the existing database instance.'),
    dbName: z.string().default('postgres').describe('The name of the database for the database instance.'),
    dbPort: z.number().default(5432).describe('The port of the existing database instance or the port to be opened on the database instance.'),
}).describe('Configuration schema for RDS Instances needed for LiteLLM scaling or PGVector RAG operations.\n \n ' +
    'The optional fields can be omitted to create a new database instance, otherwise fill in all fields to use an existing database instance.');

export type RdsConfig = z.infer<typeof RdsInstanceConfig>;

const FastApiContainerConfigSchema = z.object({
    internetFacing: z.boolean().default(true).describe('Whether the REST API ALB will be configured as internet facing.'),
    domainName: z.string().nullish().default(null),
    sslCertIamArn: z.string().nullish().default(null).describe('ARN of the self-signed cert to be used throughout the system'),
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

/**
 * Enum for different types of RAG repositories available
 */
export enum RagRepositoryType {
    OPENSEARCH = 'opensearch',
    PGVECTOR = 'pgvector',
}

export const OpenSearchNewClusterConfig = z.object({
    dataNodes: z.number().min(1).default(2).describe('The number of data nodes (instances) to use in the Amazon OpenSearch Service domain.'),
    dataNodeInstanceType: z.string().default('r7g.large.search').describe('The instance type for your data nodes'),
    masterNodes: z.number().min(0).default(0).describe('The number of instances to use for the master node'),
    masterNodeInstanceType: z.string().default('r7g.large.search').describe('The hardware configuration of the computer that hosts the dedicated master node'),
    volumeSize: z.number().min(20).default(20).describe('The size (in GiB) of the EBS volume for each data node. The minimum and maximum size of an EBS volume depends on the EBS volume type and the instance type to which it is attached.'),
    volumeType: z.nativeEnum(EbsDeviceVolumeType).default(EbsDeviceVolumeType.GP3).describe('The EBS volume type to use with the Amazon OpenSearch Service domain'),
    multiAzWithStandby: z.boolean().default(false).describe('Indicates whether Multi-AZ with Standby deployment option is enabled.'),
});

export const OpenSearchExistingClusterConfig = z.object({
    endpoint: z.string().nonempty().describe('Existing OpenSearch Cluster endpoint'),
});

export const RagRepositoryPipeline = z.object({
    chunkSize: z.number().default(512).describe('The size of the chunks used for document segmentation.'),
    chunkOverlap: z.number().default(51).describe('The size of the overlap between chunks.'),
    embeddingModel: z.string().describe('The embedding model used for document ingestion in this pipeline.'),
    s3Bucket: z.string().describe('The S3 bucket monitored by this pipeline for document processing.'),
    s3Prefix: z.string().describe('The prefix within the S3 bucket monitored for document processing.'),
    trigger: z.union([z.literal('daily').describe('This ingestion pipeline is scheduled to run once per day'), z.literal('event').describe('This ingestion pipeline runs whenever changes are detected.')]).default('event').describe('The event type that triggers document ingestion.'),
    autoRemove: z.boolean().default(true).describe('Enable removal of document from vector store when deleted from S3. This will also remove the file from S3 if file is deleted from vector store through API/UI.'),
});

export type PipelineConfig = z.infer<typeof RagRepositoryPipeline>;
export type OpenSearchConfig =
    z.infer<typeof OpenSearchNewClusterConfig>
    | z.infer<typeof OpenSearchExistingClusterConfig>;

export const RagRepositoryConfigSchema = z
    .object({
        repositoryId: z.string().nonempty().describe('A unique identifier for the repository, used in API calls and the UI. It must be distinct across all repositories.'),
        repositoryName: z.string().optional().describe('The user-friendly name displayed in the UI.'),
        type: z.nativeEnum(RagRepositoryType).describe('The vector store designated for this repository.'),
        opensearchConfig: z.union([OpenSearchExistingClusterConfig, OpenSearchNewClusterConfig]).optional(),
        rdsConfig: RdsInstanceConfig.optional(),
        pipelines: z.array(RagRepositoryPipeline).optional().default([]).describe('Rag ingestion pipeline for automated inclusion into a vector store from S3'),
        allowedGroups: z.array(z.string().nonempty()).optional().default([]).describe('The groups provided by the Identity Provider that have access to this repository. If no groups are specified, access is granted to everyone.'),
    })
    .refine((input) => {
        return !((input.type === RagRepositoryType.OPENSEARCH && input.opensearchConfig === undefined) ||
            (input.type === RagRepositoryType.PGVECTOR && input.rdsConfig === undefined));
    })
    .describe('Configuration schema for RAG repository. Defines settings for OpenSearch.');

export type RagRepositoryConfig = z.infer<typeof RagRepositoryConfigSchema>;

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
    condaUrl: z.string().default('').describe('Conda URL configuration'),
    certificateAuthorityBundle: z.string().default('').describe('Certificate Authority Bundle file'),
    ragRepositories: z.array(RagRepositoryConfigSchema).optional().default([]).describe('Rag Repository configuration.'),
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
    deploymentPrefix: z.string().optional().describe('Prefix for deployment resources.'),
    webAppAssetsPath: z.string().optional().describe('Optional path to precompiled webapp assets. If not specified the web application will be built at deploy time.'),
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
            return !(config.deployRag && !config.deployUi);
        },
        {
            message: 'UI Stack is needed for Rag stack. You must set deployUI to true if deployRag is true.',
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

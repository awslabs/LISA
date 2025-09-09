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
import { EbsDeviceVolumeType } from './cdk';

/**
 * Enum for different types of RAG repositories available
 */
export enum RagRepositoryType {
    OPENSEARCH = 'opensearch',
    PGVECTOR = 'pgvector',
    BEDROCK_KNOWLEDGE_BASE = 'bedrock_knowledge_base',
}

export const BedrockKnowledgeBaseInstanceConfig = z.object({
    bedrockKnowledgeBaseName: z.string().describe('The name of the Bedrock Knowledge Base.'),
    bedrockKnowledgeBaseId: z.string().describe('The id of the Bedrock Knowledge Base.'),
    bedrockKnowledgeDatasourceName: z.string().describe('The name of the Bedrock Knowledge Datasource.'),
    bedrockKnowledgeDatasourceId: z.string().describe('The id of the Bedrock Knowledge Datasource.'),
    bedrockKnowledgeDatasourceS3Bucket: z.string().describe('The S3 bucket of the Bedrock Knowledge Base.'),
});

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
const triggerEnum = {
    daily: 'daily',
    event: 'event',
} as const;

const triggerSchema = z.object({
    daily: z.literal(triggerEnum.daily).describe('This ingestion pipeline is scheduled to run once per day'),
    event: z.literal(triggerEnum.event).describe('This ingestion pipeline runs whenever changes are detected.'),
});

export const RagRepositoryPipeline = z.object({
    chunkSize: z.number().default(512).describe('The size of the chunks used for document segmentation.'),
    chunkOverlap: z.number().default(51).describe('The size of the overlap between chunks.'),
    embeddingModel: z.string().describe('The embedding model used for document ingestion in this pipeline.'),
    s3Bucket: z.string().describe('The S3 bucket monitored by this pipeline for document processing.'),
    s3Prefix: z.string()
        .regex(/^(?!.*(?:^|\/)\.\.?(\/|$)).*/, 'Prefix cannot contain relative path components (ie `.` or `..`)')
        .regex(/^([a-zA-Z0-9!_.*'()/=-]+\/)*[a-zA-Z0-9!_.*'()/=-]*$/, 'Prefix must be a valid S3 prefix.')
        .regex(/^(?!\/).*/, 'Prefix must not start with /')
        .default('').describe('The prefix within the S3 bucket monitored for document processing.'),
    trigger: z.union([triggerSchema.shape.daily, triggerSchema.shape.event])
        .default('event').describe('The event type that triggers document ingestion.'),
    autoRemove: z.boolean().default(true).describe('Enable removal of document from vector store when deleted from S3. This will also remove the file from S3 if file is deleted from vector store through API/UI.'),
});

export type PipelineConfig = z.infer<typeof RagRepositoryPipeline>;
export type OpenSearchConfig =
    z.infer<typeof OpenSearchNewClusterConfig>
    | z.infer<typeof OpenSearchExistingClusterConfig>;

export const RdsInstanceConfig = z.object({
    username: z.string().default('postgres').describe('The username used for database connection.'),
    passwordSecretId: z.string().optional().describe('The SecretsManager Secret ID that stores the existing database password.'),
    dbHost: z.string().optional().describe('The database hostname for the existing database instance.'),
    dbName: z.string().default('postgres').describe('The name of the database for the database instance.'),
    dbPort: z.number().default(5432).describe('The port of the existing database instance or the port to be opened on the database instance.'),
}).describe('Configuration schema for RDS Instances needed for LiteLLM scaling or PGVector RAG operations.\n \n ' +
    'The optional fields can be omitted to create a new database instance, otherwise fill in all fields to use an existing database instance.');

export type RdsConfig = z.infer<typeof RdsInstanceConfig>;

export type BedrockKnowledgeBaseConfig = z.infer<typeof BedrockKnowledgeBaseInstanceConfig>;

export const RagRepositoryConfigSchema = z
    .object({
        repositoryId: z.string()
            .nonempty()
            .regex(/^[a-z0-9-]{1,63}/, 'Only lowercase alphanumeric characters and \'-\' are supported.')
            .regex(/^(?!-).*(?<!-)$/, 'Cannot start or end with a \'-\'.')
            .describe('A unique identifier for the repository, used in API calls and the UI. It must be distinct across all repositories.'),
        repositoryName: z.string().optional().describe('The user-friendly name displayed in the UI.'),
        embeddingModelId: z.string().optional().describe('The default embedding model to be used when selecting repository.'),
        type: z.nativeEnum(RagRepositoryType).describe('The vector store designated for this repository.'),
        opensearchConfig: z.union([OpenSearchExistingClusterConfig, OpenSearchNewClusterConfig]).optional(),
        rdsConfig: RdsInstanceConfig.optional(),
        bedrockKnowledgeBaseConfig: BedrockKnowledgeBaseInstanceConfig.optional(),
        pipelines: z.array(RagRepositoryPipeline).optional().default([]).describe('Rag ingestion pipeline for automated inclusion into a vector store from S3'),
        allowedGroups: z.array(z.string().nonempty()).optional().default([]).describe('The groups provided by the Identity Provider that have access to this repository. If no groups are specified, access is granted to everyone.'),
    })
    .refine((input) => {
        return !((input.type === RagRepositoryType.OPENSEARCH && input.opensearchConfig === undefined) ||
            (input.type === RagRepositoryType.PGVECTOR && input.rdsConfig === undefined));
    })
    .describe('Configuration schema for RAG repository. Defines settings for OpenSearch.');

export type RagRepositoryConfig = z.infer<typeof RagRepositoryConfigSchema>;
export type RDSConfig = RagRepositoryConfig['rdsConfig'];

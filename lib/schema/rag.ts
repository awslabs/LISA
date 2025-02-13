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


import * as z from 'zod';
import { EbsDeviceVolumeType } from 'aws-cdk-lib/aws-ec2';
import { RdsInstanceConfig } from './app-private';

/**
 * Enum for different types of RAG repositories available
 */
export enum RagRepositoryType {
    OPENSEARCH = 'opensearch',
    PGVECTOR = 'pgvector',
}

const OpenSearchNewClusterConfig = z.object({
    dataNodes: z.number().min(1).default(2),
    dataNodeInstanceType: z.string().default('r7g.large.search'),
    masterNodes: z.number().min(0).default(0),
    masterNodeInstanceType: z.string().default('r7g.large.search'),
    volumeSize: z.number().min(20),
    volumeType: z.nativeEnum(EbsDeviceVolumeType).default(EbsDeviceVolumeType.GP3),
    multiAzWithStandby: z.boolean().default(false),
});

const OpenSearchExistingClusterConfig = z.object({
    endpoint: z.string(),
});

export const RagRepositoryPipeline = z.object({
    chunkOverlap: z.number().describe('The number of tokens to overlap between chunks'),
    chunkSize: z.number().describe('The size of each document chunk'),
    embeddingModel: z.string().describe('The ID of the embedding model to be used'),
    s3Bucket: z.string().describe('The source S3 bucket where documents are stored'),
    s3Prefix: z.string().describe('The prefix within the S3 bucket'),
    trigger: z.union([z.literal('daily'), z.literal('event')]).describe('Specifies when the ingestion should occur'),
    autoRemove: z.boolean().default(true).describe('Enable removal of document from vector store when deleted from S3. This will also remove the file from S3 if file is deleted from vector store through API/UI.'),
});

export const RagRepositoryConfigSchema = z
    .object({
        repositoryId: z.string().describe('The ID of the RAG repository'),
        repositoryName: z.string().optional().describe('Name to display in the UI'),
        type: z.nativeEnum(RagRepositoryType).describe('The type of vector store to use for the RAG pository'),
        opensearchConfig: z.union([OpenSearchExistingClusterConfig, OpenSearchNewClusterConfig]).optional().describe('OpenSearch configuration'),
        rdsConfig: RdsInstanceConfig.optional().describe('PGVector configuration'),
        pipelines: z.array(RagRepositoryPipeline).optional().describe('Rag ingestion pipeline for automated inclusion into a vector store from S3'),
        allowedGroups: z.array(z.string()).optional().default([]).describe('What groups can interact with this repository. If blank the repository is available to all users.')
    })
    .refine((input) => {
        return !((input.type === RagRepositoryType.OPENSEARCH && input.opensearchConfig === undefined) ||
            (input.type === RagRepositoryType.PGVECTOR && input.rdsConfig === undefined));
    })
    .describe('Configuration schema for RAG repository. Defines settings for OpenSearch.');

export type RagRepositoryConfig = z.infer<typeof RagRepositoryConfigSchema>;

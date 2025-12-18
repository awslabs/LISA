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

import { createApi } from '@reduxjs/toolkit/query/react';
import { lisaBaseQuery } from '@/shared/reducers/reducer.utils';
import { PaginatedDocumentResponse } from '@/components/types';
import { Document } from '@langchain/core/documents';
import {
    RagRepositoryConfig,
    ChunkingStrategy,
    RagCollectionConfig as SchemaRagCollectionConfig,
    CollectionMetadata,
} from '#root/lib/schema';

export type S3UploadRequest = {
    url: string;
    body: any;
};

type IngestDocumentRequest = {
    documents: string[],
    repositoryId: string,
    collectionId?: string,
    repostiroyType: string,
    chunkingStrategy?: ChunkingStrategy;
    metadata?: CollectionMetadata;
};

type IngestDocumentJob = {
    jobId: string;
    documentId: string;
    status: string;
    s3Path: string;
};

type IngestDocumentResponse = {
    jobs: IngestDocumentJob[];
    collectionId: string;
    collectionName?: string;
};

type RelevantDocRequest = {
    repositoryId: string,
    collectionId?: string
    query: string,
    topK: number,
    modelName?: string,
};

type ListRagDocumentRequest = {
    repositoryId: string,
    collectionId?: string,
    lastEvaluatedKey?: {
        pk: string;
        document_id: string;
        repository_id: string;
    } | null,
    pageSize?: number
};

type DeleteRagDocumentRequest = {
    repositoryId: string,
    documentIds: string[]
};



export type IngestionJob = {
    id: string;
    s3_path: string;
    collection_id: string;
    document_id: string;
    repository_id: string;
    chunk_strategy: ChunkingStrategy;
    username: string;
    status: string;
    created_date: string;
    error_message?: string | null;
    document_name: string;
    auto: boolean;
};

type GetIngestionJobsRequest = {
    repositoryId: string;
    pageSize?: number;
    lastEvaluatedKey?: any | null; // Can be a complex object with repository_id, created_date, id
    timeLimit?: number;
};

export type PaginatedIngestionJobsResponse = {
    jobs: IngestionJob[];
    lastEvaluatedKey?: any | null; // Can be a complex object with repository_id, created_date, id
    hasNextPage?: boolean;
    hasPreviousPage?: boolean;
};

// Collection types - using schema definitions
export type RagCollectionConfig = SchemaRagCollectionConfig;

type ListCollectionsRequest = {
    repositoryId: string;
    pageSize?: number;
    lastEvaluatedKey?: any;
};

type ListCollectionsResponse = {
    collections: RagCollectionConfig[];
    totalCount?: number;
    hasNextPage?: boolean;
    lastEvaluatedKey?: any;
};

type CollectionRequest = {
    repositoryId: string;
    collectionId: string;
};

type DiscoverDataSourcesRequest = {
    kbId: string;
    repositoryId?: string;
    refresh?: boolean;
};

type KnowledgeBase = {
    knowledgeBaseId: string;
    name: string;
    description?: string;
    status: string;
    available?: boolean;
    unavailableReason?: string;
    createdAt?: string;
    updatedAt?: string;
};

type DataSource = {
    dataSourceId: string;
    name: string;
    description?: string;
    status: string;
    s3Bucket: string;
    s3Prefix?: string;
    createdAt?: string;
    updatedAt?: string;
    managed?: boolean;
    collectionId?: string;
};

type DiscoverKnowledgeBasesResponse = {
    knowledgeBases: KnowledgeBase[];
    totalKnowledgeBases: number;
};

type DiscoverDataSourcesResponse = {
    knowledgeBase: {
        id: string;
        name: string;
        status?: string;
        description?: string;
    };
    dataSources: DataSource[];
    totalDataSources?: number;
};

export const ragApi = createApi({
    reducerPath: 'rag',
    baseQuery: lisaBaseQuery(),
    tagTypes: ['repositories', 'docs', 'repository-status', 'jobs', 'collections'],
    refetchOnFocus: true,
    refetchOnMountOrArgChange: true,
    endpoints: (builder) => ({
        listRagRepositories: builder.query<RagRepositoryConfig[], void>({
            query: () => ({
                url: '/repository'
            }),
            providesTags: ['repositories'],
        }),
        createRagRepository: builder.mutation<RagRepositoryConfig, RagRepositoryConfig>({
            query: (body) => ({
                url: '/repository',
                method: 'POST',
                data: body,
            }),
            invalidatesTags: ['repositories'],
        }),
        updateRagRepository: builder.mutation<RagRepositoryConfig, { repositoryId: string; updates: Partial<RagRepositoryConfig> }>({
            query: ({ repositoryId, updates }) => ({
                url: `/repository/${repositoryId}`,
                method: 'PUT',
                data: updates,
            }),
            invalidatesTags: ['repositories'],
        }),
        deleteRagRepository: builder.mutation<undefined, string>({
            query: (repositoryId) => ({
                url: `/repository/${repositoryId}`,
                method: 'DELETE',
            }),
            invalidatesTags: ['repositories', 'collections', 'docs', 'jobs'],
        }),
        getPresignedUrl: builder.query<any, string>({
            query: (body) => ({
                url: '/repository/presigned-url',
                method: 'POST',
                data: body
            }),
        }),
        getRelevantDocuments: builder.query<Document[], RelevantDocRequest>({
            query: (request) => {
                const params: any = {
                    query: request.query,
                    topK: request.topK
                };

                if (request.collectionId) {
                    params.collectionId = request.collectionId;
                } else if (request.modelName) {
                    params.modelName = request.modelName;
                }

                const queryString = new URLSearchParams(params).toString();
                return {
                    url: `repository/${request.repositoryId}/similaritySearch?${queryString}`,
                };
            },
        }),
        uploadToS3: builder.mutation<void, S3UploadRequest>({
            query: (request) => ({
                url: request.url,
                method: 'POST',
                data: request.body,
            }),
            transformErrorResponse: (baseQueryReturnValue) => ({
                name: 'Upload to S3 failed',
                message: baseQueryReturnValue.data?.type === 'RequestValidationError' ? baseQueryReturnValue.data.detail.map((error) => error.msg).join(', ') : baseQueryReturnValue.data.message
            }),
        }),
        ingestDocuments: builder.mutation<IngestDocumentResponse, IngestDocumentRequest>({
            query: (request) => ({
                url: `repository/${request.repositoryId}/bulk`,
                method: 'POST',
                data: {
                    keys: request.documents,
                    collectionId: request.collectionId,
                    chunkingStrategy: request.chunkingStrategy
                }
            }),
            transformErrorResponse: (baseQueryReturnValue) => ({
                name: 'Upload to S3 failed',
                message: baseQueryReturnValue.data?.type === 'RequestValidationError' ? baseQueryReturnValue.data.detail.map((error) => error.msg).join(', ') : baseQueryReturnValue.data.message
            }),
            invalidatesTags: ['jobs'], // Invalidate jobs cache when new ingestion starts
        }),
        listRagDocuments: builder.query<PaginatedDocumentResponse, ListRagDocumentRequest>({
            query: (request) => {
                const params: any = {};

                // Add collectionId parameter if provided
                if (request.collectionId) {
                    params.collectionId = request.collectionId;
                }

                // Add pageSize parameter if provided
                if (request.pageSize) {
                    params.pageSize = request.pageSize;
                }

                // Construct lastEvaluatedKey parameters in the format the API expects
                // Note: Using dot notation instead of brackets to avoid API Gateway limitations
                if (request.lastEvaluatedKey) {
                    params['lastEvaluatedKeyPk'] = request.lastEvaluatedKey.pk;
                    params['lastEvaluatedKeyDocumentId'] = request.lastEvaluatedKey.document_id;
                    params['lastEvaluatedKeyRepositoryId'] = request.lastEvaluatedKey.repository_id;
                }

                return {
                    url: `/repository/${request.repositoryId}/document`,
                    params,
                };
            },
            transformResponse: (response) => response,
            providesTags: ['docs'],
        }),
        deleteRagDocuments: builder.mutation<undefined, DeleteRagDocumentRequest>({
            query: (request) => ({
                url: `/repository/${request.repositoryId}/document`,
                method: 'DELETE',
                data: {
                    documentIds: request.documentIds,
                },
            }),
            transformErrorResponse: (baseQueryReturnValue) => ({
                name: 'Delete RAG Document Error',
                message: baseQueryReturnValue.data?.type === 'RequestValidationError' ? baseQueryReturnValue.data.detail.map((error) => error.msg).join(', ') : baseQueryReturnValue.data.message,
            }),
            invalidatesTags: ['docs'],
        }),
        downloadRagDocument: builder.query<string, { documentId: string, repositoryId: string }>({
            query: ({ documentId, repositoryId }) => ({
                url: `/repository/${repositoryId}/${documentId}/download`,
                method: 'GET',
            }),
        }),
        getIngestionJobs: builder.query<PaginatedIngestionJobsResponse, GetIngestionJobsRequest>({
            query: (request) => {
                let url = `/repository/${request.repositoryId}/jobs?timeLimit=${request.timeLimit || 1}&pageSize=${request.pageSize || 10}`;

                // If lastEvaluatedKey is provided, JSON encode and URL encode it for the API
                if (request.lastEvaluatedKey) {
                    const encodedKey = encodeURIComponent(JSON.stringify(request.lastEvaluatedKey));
                    url += `&lastEvaluatedKey=${encodedKey}`;
                }

                return {
                    url,
                    method: 'GET',
                };
            },
            providesTags: ['jobs'], // Add cache tags for invalidation
        }),
        listCollections: builder.query<RagCollectionConfig[], ListCollectionsRequest>({
            query: (request) => ({
                url: `/repository/${request.repositoryId}/collection`,
                params: {
                    pageSize: request.pageSize,
                    lastEvaluatedKey: request.lastEvaluatedKey,
                },
            }),
            transformResponse: (response: ListCollectionsResponse) => response.collections,
            providesTags: (result) => result ?
                [
                    ...result.map(({ repositoryId, collectionId }) => ({
                        type: 'collections' as const,
                        id: `${repositoryId}/${collectionId}`,
                    })),
                    { type: 'collections', id: 'LIST' },
                ] : [{ type: 'collections', id: 'LIST' }],
        }),
        listAllCollections: builder.query<RagCollectionConfig[], void>({
            query: () => ({
                url: '/repository/collections',
            }),
            transformResponse: (response: ListCollectionsResponse) => response.collections,
            providesTags: (result) => result ? [
                ...result.map(({ repositoryId, collectionId }) => ({
                    type: 'collections' as const,
                    id: `${repositoryId}/${collectionId}`,
                })),
                { type: 'collections', id: 'LIST' },
            ] : [{ type: 'collections', id: 'LIST' }],
        }),
        getCollection: builder.query<RagCollectionConfig, CollectionRequest>({
            query: (request) => ({
                url: `/repository/${request.repositoryId}/collection/${request.collectionId}`,
            }),
            providesTags: (result, error, arg) => [
                { type: 'collections', id: `${arg.repositoryId}/${arg.collectionId}` },
            ],
        }),
        createCollection: builder.mutation<RagCollectionConfig, RagCollectionConfig>({
            query: (request) => ({
                url: `/repository/${request.repositoryId}/collection`,
                method: 'POST',
                data: {
                    name: request.name,
                    description: request.description,
                    embeddingModel: request.embeddingModel,
                    chunkingStrategy: request.chunkingStrategy,
                    allowedGroups: request.allowedGroups,
                    metadata: request.metadata,
                },
            }),
            transformErrorResponse: (baseQueryReturnValue) => ({
                name: 'Create Collection Error',
                message: baseQueryReturnValue.data?.type === 'RequestValidationError'
                    ? baseQueryReturnValue.data.detail.map((error) => error.msg).join(', ')
                    : baseQueryReturnValue.data.message
            }),
            invalidatesTags: [{ type: 'collections', id: 'LIST' }],
        }),
        deleteCollection: builder.mutation<void, CollectionRequest & { embeddingModel?: string; default?: boolean }>({
            query: (request) => ({
                url: `/repository/${request.repositoryId}/collection/${request.collectionId}`,
                method: 'DELETE',
                params: {
                    // For Default 'Collection', pass in the embedding model name
                    ...(request.default && { embeddingName: request.embeddingModel })
                }
            }),
            transformErrorResponse: (baseQueryReturnValue) => ({
                name: 'Delete Collection Error',
                message: baseQueryReturnValue.data?.type === 'RequestValidationError'
                    ? baseQueryReturnValue.data.detail.map((error) => error.msg).join(', ')
                    : baseQueryReturnValue.data.message
            }),
            invalidatesTags: (result, error, arg) => [
                { type: 'collections', id: `${arg.repositoryId}/${arg.collectionId}` },
                { type: 'collections', id: 'LIST' },
            ],
        }),
        updateCollection: builder.mutation<RagCollectionConfig, RagCollectionConfig>({
            query: (request) => ({
                url: `/repository/${request.repositoryId}/collection/${request.collectionId}`,
                method: 'PUT',
                data: {
                    name: request.name,
                    description: request.description,
                    chunkingStrategy: request.chunkingStrategy,
                    allowedGroups: request.allowedGroups,
                    metadata: request.metadata,
                    allowChunkingOverride: request.allowChunkingOverride,
                    status: request.status,
                },
            }),
            transformErrorResponse: (baseQueryReturnValue) => ({
                name: 'Update Collection Error',
                message: baseQueryReturnValue.data?.type === 'RequestValidationError'
                    ? baseQueryReturnValue.data.detail.map((error) => error.msg).join(', ')
                    : baseQueryReturnValue.data.message
            }),
            invalidatesTags: (result, error, arg) => [
                { type: 'collections', id: `${arg.repositoryId}/${arg.collectionId}` },
                { type: 'collections', id: 'LIST' },
            ],
        }),
        // Bedrock KB Discovery endpoints
        listBedrockKnowledgeBases: builder.query<DiscoverKnowledgeBasesResponse, void>({
            query: () => ({
                url: '/bedrock-kb',
            }),
            transformErrorResponse: (baseQueryReturnValue) => ({
                name: 'List Knowledge Bases Error',
                message: baseQueryReturnValue.data?.type === 'RequestValidationError'
                    ? baseQueryReturnValue.data.detail.map((error) => error.msg).join(', ')
                    : baseQueryReturnValue.data.message
            }),
        }),
        listBedrockDataSources: builder.query<DiscoverDataSourcesResponse, DiscoverDataSourcesRequest>({
            query: (request) => {
                const params: any = {};
                if (request.repositoryId) {
                    params.repositoryId = request.repositoryId;
                }
                if (request.refresh) {
                    params.refresh = 'true';
                }
                const queryString = new URLSearchParams(params).toString();
                return {
                    url: `/bedrock-kb/${request.kbId}/data-sources${queryString ? `?${queryString}` : ''}`,
                };
            },
            transformErrorResponse: (baseQueryReturnValue) => ({
                name: 'List Data Sources Error',
                message: baseQueryReturnValue.data?.type === 'RequestValidationError'
                    ? baseQueryReturnValue.data.detail.map((error) => error.msg).join(', ')
                    : baseQueryReturnValue.data.message
            }),
        }),
    }),
});

export const {
    useListRagRepositoriesQuery,
    useCreateRagRepositoryMutation,
    useUpdateRagRepositoryMutation,
    useDeleteRagRepositoryMutation,
    useLazyGetPresignedUrlQuery,
    useUploadToS3Mutation,
    useIngestDocumentsMutation,
    useListRagDocumentsQuery,
    useDeleteRagDocumentsMutation,
    useLazyGetRelevantDocumentsQuery,
    useLazyDownloadRagDocumentQuery,
    useGetIngestionJobsQuery,
    useLazyGetIngestionJobsQuery,
    useListCollectionsQuery,
    useListAllCollectionsQuery,
    useGetCollectionQuery,
    useCreateCollectionMutation,
    useUpdateCollectionMutation,
    useDeleteCollectionMutation,
    useListBedrockKnowledgeBasesQuery,
    useLazyListBedrockKnowledgeBasesQuery,
    useListBedrockDataSourcesQuery,
    useLazyListBedrockDataSourcesQuery,
} = ragApi;

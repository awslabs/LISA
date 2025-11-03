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
import { lisaBaseQuery } from './reducer.utils';
import { Model, PaginatedDocumentResponse } from '../../components/types';
import { Document } from '@langchain/core/documents';
import { RagRepositoryConfig } from '#root/lib/schema';
import { RagStatus } from '../model/rag.model';

export type S3UploadRequest = {
    url: string;
    body: any;
};

type IngestDocumentRequest = {
    documents: string[],
    repositoryId: string,
    collectionId?: string,
    repostiroyType: string,
    chunkSize: number,
    chunkOverlap: number
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
    query: string,
    modelName: string,
    repositoryType: string,
    topK: number
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

type CreateRepositoryRequest = {
    ragConfig: RagRepositoryConfig
};

export type IngestionJob = {
    id: string;
    s3_path: string;
    collection_id: string;
    document_id: string;
    repository_id: string;
    chunk_strategy: {
        type: string;
        size: number;
        overlap: number;
    };
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

// Collection types
export type RagCollectionConfig = {
    collectionId: string;
    repositoryId: string;
    name?: string;
    description?: string;
    embeddingModel: string;
    chunkingStrategy?: {
        type: string;
        size: number;
        overlap: number;
    };
    allowedGroups?: string[];
    createdBy: string;
    createdAt: string;
    updatedAt: string;
    status: 'ACTIVE' | 'ARCHIVED' | 'DELETED';
    private: boolean;
    metadata?: {
        tags?: string[];
        customFields?: Record<string, any>;
    };
    allowChunkingOverride?: boolean;
    pipelines?: Array<{
        chunkSize?: number;
        chunkOverlap?: number;
        embeddingModel?: string;
        s3Bucket: string;
        s3Prefix?: string;
        trigger?: 'daily' | 'event';
        autoRemove?: boolean;
    }>;
};

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

type CreateCollectionRequest = {
    repositoryId: string;
    name: string;
    description?: string;
    embeddingModel?: string;
    chunkingStrategy?: any;
    allowedGroups?: string[];
    metadata?: any;
    private?: boolean;
    pipelines?: Array<{
        chunkSize?: number;
        chunkOverlap?: number;
        embeddingModel?: string;
        s3Bucket?: string;
        s3Prefix?: string;
        trigger?: 'daily' | 'event';
        autoRemove?: boolean;
    }>;
};

type DeleteCollectionRequest = {
    repositoryId: string;
    collectionId: string;
};

type GetCollectionRequest = {
    repositoryId: string;
    collectionId: string;
};

type UpdateCollectionRequest = {
    repositoryId: string;
    collectionId: string;
    name?: string;
    description?: string;
    chunkingStrategy?: any;
    allowedGroups?: string[];
    metadata?: any;
    private?: boolean;
    allowChunkingOverride?: boolean;
    pipelines?: Array<{
        chunkSize?: number;
        chunkOverlap?: number;
        embeddingModel?: string;
        s3Bucket?: string;
        s3Prefix?: string;
        trigger?: 'daily' | 'event';
        autoRemove?: boolean;
    }>;
    status?: 'ACTIVE' | 'ARCHIVED' | 'DELETED';
};

export const ragApi = createApi({
    reducerPath: 'rag',
    baseQuery: lisaBaseQuery(),
    tagTypes: ['repositories', 'docs', 'repository-status', 'jobs', 'collections'],
    refetchOnFocus: true,
    refetchOnReconnect: true,
    endpoints: (builder) => ({
        listRagRepositories: builder.query<RagRepositoryConfig[], void>({
            query: () => ({
                url: '/repository'
            }),
            providesTags: ['repositories'],
        }),
        createRagRepository: builder.mutation<RagRepositoryConfig, CreateRepositoryRequest>({
            query: (body) => ({
                url: '/repository',
                method: 'POST',
                data: body,
            }),
            invalidatesTags: ['repositories'],
        }),
        deleteRagRepository: builder.mutation<undefined, string>({
            query: (repositoryId) => ({
                url: `/repository/${repositoryId}`,
                method: 'DELETE',
            }),
            invalidatesTags: ['repositories'],
        }),
        getRagStatus: builder.query<RagStatus, void>({
            query: () => ({
                url: '/repository/status',
            }),
            providesTags: ['repository-status'],
        }),
        getPresignedUrl: builder.query<any, string>({
            query: (body) => ({
                url: '/repository/presigned-url',
                method: 'POST',
                data: body
            }),
        }),
        getRelevantDocuments: builder.query<Document[], RelevantDocRequest>({
            query: (request) => ({
                url: `repository/${request.repositoryId}/similaritySearch?query=${request.query}&modelName=${request.modelName}&repositoryType=${request.repositoryType}&topK=${request.topK}`,
            }),
        }),
        uploadToS3: builder.mutation<void, S3UploadRequest>({
            query: (request) => ({
                url: request.url,
                method: 'POST',
                data: request.body,
            }),
            transformErrorResponse: (baseQueryReturnValue) => {
                // transform into SerializedError
                return {
                    name: 'Upload to S3 failed',
                    message: baseQueryReturnValue.data?.type === 'RequestValidationError' ? baseQueryReturnValue.data.detail.map((error) => error.msg).join(', ') : baseQueryReturnValue.data.message
                };
            },
        }),
        ingestDocuments: builder.mutation<IngestDocumentResponse, IngestDocumentRequest>({
            query: (request) => {
                let url = `repository/${request.repositoryId}/bulk?chunkSize=${request.chunkSize}&chunkOverlap=${request.chunkOverlap}`;

                // Add collectionId parameter if provided
                if (request.collectionId) {
                    url += `&collectionId=${request.collectionId}`;
                }

                return {
                    url,
                    method: 'POST',
                    data: {
                        keys: request.documents
                    }
                };
            },
            transformErrorResponse: (baseQueryReturnValue) => {
                // transform into SerializedError
                return {
                    name: 'Upload to S3 failed',
                    message: baseQueryReturnValue.data?.type === 'RequestValidationError' ? baseQueryReturnValue.data.detail.map((error) => error.msg).join(', ') : baseQueryReturnValue.data.message
                };
            },
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
            transformErrorResponse: (baseQueryReturnValue) => {
                // transform into SerializedError
                return {
                    name: 'Delete RAG Document Error',
                    message: baseQueryReturnValue.data?.type === 'RequestValidationError' ? baseQueryReturnValue.data.detail.map((error) => error.msg).join(', ') : baseQueryReturnValue.data.message,
                };
            },
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
            providesTags: ['collections'],
        }),
        listAllCollections: builder.query<RagCollectionConfig[], void>({
            query: () => ({
                url: '/repository/collections',
            }),
            transformResponse: (response: ListCollectionsResponse) => response.collections,
            providesTags: ['collections'],
        }),
        getCollection: builder.query<RagCollectionConfig, GetCollectionRequest>({
            query: (request) => ({
                url: `/repository/${request.repositoryId}/collection/${request.collectionId}`,
            }),
            providesTags: ['collections'],
        }),
        createCollection: builder.mutation<RagCollectionConfig, CreateCollectionRequest>({
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
                    private: request.private,
                    pipelines: request.pipelines,
                },
            }),
            transformErrorResponse: (baseQueryReturnValue) => {
                return {
                    name: 'Create Collection Error',
                    message: baseQueryReturnValue.data?.type === 'RequestValidationError'
                        ? baseQueryReturnValue.data.detail.map((error) => error.msg).join(', ')
                        : baseQueryReturnValue.data.message
                };
            },
            invalidatesTags: ['collections'],
        }),
        deleteCollection: builder.mutation<void, DeleteCollectionRequest>({
            query: (request) => ({
                url: `/repository/${request.repositoryId}/collection/${request.collectionId}`,
                method: 'DELETE',
            }),
            transformErrorResponse: (baseQueryReturnValue) => {
                return {
                    name: 'Delete Collection Error',
                    message: baseQueryReturnValue.data?.type === 'RequestValidationError'
                        ? baseQueryReturnValue.data.detail.map((error) => error.msg).join(', ')
                        : baseQueryReturnValue.data.message
                };
            },
            invalidatesTags: ['collections'],
        }),
        updateCollection: builder.mutation<RagCollectionConfig, UpdateCollectionRequest>({
            query: (request) => ({
                url: `/repository/${request.repositoryId}/collection/${request.collectionId}`,
                method: 'PUT',
                data: {
                    name: request.name,
                    description: request.description,
                    chunkingStrategy: request.chunkingStrategy,
                    allowedGroups: request.allowedGroups,
                    metadata: request.metadata,
                    private: request.private,
                    allowChunkingOverride: request.allowChunkingOverride,
                    pipelines: request.pipelines,
                    status: request.status,
                },
            }),
            transformErrorResponse: (baseQueryReturnValue) => {
                return {
                    name: 'Update Collection Error',
                    message: baseQueryReturnValue.data?.type === 'RequestValidationError'
                        ? baseQueryReturnValue.data.detail.map((error) => error.msg).join(', ')
                        : baseQueryReturnValue.data.message
                };
            },
            invalidatesTags: ['collections'],
        }),
    }),
});

export const {
    useListRagRepositoriesQuery,
    useCreateRagRepositoryMutation,
    useDeleteRagRepositoryMutation,
    useGetRagStatusQuery,
    useLazyGetRagStatusQuery,
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
} = ragApi;

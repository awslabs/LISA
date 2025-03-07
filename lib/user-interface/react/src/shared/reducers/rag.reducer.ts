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
import { Model, RagDocument } from '../../components/types';
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
    embeddingModel: Model,
    repostiroyType: string,
    chunkSize: number,
    chunkOverlap: number
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
    lastEvaluatedKey?: string
};

type DeleteRagDocumentRequest = {
    repositoryId: string,
    documentIds: string[]
};

type CreateRepositoryRequest = {
    ragConfig: RagRepositoryConfig
};

export const ragApi = createApi({
    reducerPath: 'rag',
    baseQuery: lisaBaseQuery(),
    tagTypes: ['repositories', 'docs', 'repository-status'],
    refetchOnFocus: true,
    refetchOnReconnect: true,
    endpoints: (builder) => ({
        listRagRepositories: builder.query<RagRepositoryConfig[], void>({
            query: () => ({
                url: '/repository'
            }),
            providesTags:['repositories'],
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
        getRagStatus: builder.query<RagStatus[], void>({
            query: () => ({
                url: '/repository/status',
            }),
            providesTags: ['repository-status'],
        }),
        getPresignedUrl: builder.query<any, String>({
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
        ingestDocuments: builder.mutation<void, IngestDocumentRequest>({
            query: (request) => ({
                url: `repository/${request.repositoryId}/bulk?repositoryType=${request.repostiroyType}&chunkSize=${request.chunkSize}&chunkOverlap=${request.chunkOverlap}`,
                method: 'POST',
                data: {
                    embeddingModel: {
                        modelName: request.embeddingModel.id
                    },
                    keys: request.documents
                }
            }),
            transformErrorResponse: (baseQueryReturnValue) => {
                // transform into SerializedError
                return {
                    name: 'Upload to S3 failed',
                    message: baseQueryReturnValue.data?.type === 'RequestValidationError' ? baseQueryReturnValue.data.detail.map((error) => error.msg).join(', ') : baseQueryReturnValue.data.message
                };
            },
        }),
        listRagDocuments: builder.query<RagDocument[], ListRagDocumentRequest>({
            query: (request) => ({
                url: `/repository/${request.repositoryId}/document`,
                params: { collectionId: request.collectionId, lastEvaluatedKey: request.lastEvaluatedKey },
            }),
            transformResponse: (response) => response.documents,
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
} = ragApi;

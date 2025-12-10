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
import { IModel, IModelListResponse, IModelRequest, IModelUpdateRequest } from '../model/model-management.model';

export const modelManagementApi = createApi({
    reducerPath: 'models',
    baseQuery: lisaBaseQuery(),
    tagTypes: ['models'],
    refetchOnFocus: true,
    refetchOnMountOrArgChange: true,
    endpoints: (builder) => ({
        getAllModels: builder.query<IModelListResponse['models'], void>({
            query: () => ({
                url: '/models',
            }),
            transformResponse: (response: IModelListResponse) => response.models,
            providesTags:['models'],
        }),
        deleteModel: builder.mutation<IModel, string>({
            query: (modelId) => ({
                url: `/models/${modelId}`,
                method: 'DELETE',
            }),
            invalidatesTags: ['models'],
        }),
        createModel: builder.mutation<IModel, IModelRequest>({
            query: (modelRequest) => ({
                url: '/models',
                method: 'POST',
                data: modelRequest
            }),
            transformErrorResponse: (baseQueryReturnValue) => {
                // transform into SerializedError
                return {
                    name: 'Create Model Error',
                    message: baseQueryReturnValue.data?.type === 'RequestValidationError' ? baseQueryReturnValue.data.detail.map((error) => error.msg).join(', ') : baseQueryReturnValue.data.message
                };
            },
            invalidatesTags: ['models'],
        }),
        updateModel: builder.mutation<IModel, IModelUpdateRequest>({
            query: (modelRequest) => ({
                url: `/models/${modelRequest.modelId}`,
                method: 'PUT',
                data: modelRequest
            }),
            transformErrorResponse: (baseQueryReturnValue) => {
                // transform into SerializedError
                return {
                    name: 'Update Model Error',
                    message: baseQueryReturnValue.data?.type === 'RequestValidationError' ? baseQueryReturnValue.data.detail.map((error) => error.msg).join(', ') : baseQueryReturnValue.data.message
                };
            },
            invalidatesTags: ['models'],
        }),
        getInstances: builder.query<string[], void>({
            query: () => ({
                url: '/models/metadata/instances'
            })
        })
    }),
});

export const {
    useGetAllModelsQuery,
    useDeleteModelMutation,
    useCreateModelMutation,
    useUpdateModelMutation,
    useGetInstancesQuery
} = modelManagementApi;

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
import { IModel, IModelRequest } from '../model/model-management.model';

export const modelManagementApi = createApi({
    reducerPath: 'models',
    baseQuery: lisaBaseQuery(),
    endpoints: (builder) => ({
        getAllModels: builder.query<IModel[], void>({
            query: () => ({
                url: '/models',
            }),
            providesTags: ['models'],
        }),
        deleteModel: builder.mutation<IModel, string>({
            query: (modelId) => ({
                url: `/models/${modelId}`,
                method: 'DELETE',
            }),
            invalidatesTags: ['models'],
        }),
        startModel: builder.mutation<IModel, string>({
            query: (modelId) => ({
                url: `/models/${modelId}/start`,
                method: 'PUT',
            }),
            invalidatesTags: ['models'],
        }),
        stopModel: builder.mutation<IModel, string>({
            query: (modelId) => ({
                url: `/models/${modelId}/stop`,
                method: 'PUT',
            }),
            invalidatesTags: ['models'],
        }),
        createModel: builder.mutation<IModel, IModelRequest>({
            query: (modelRequest) => ({
                url: '/models',
                method: 'POST',
                data: modelRequest
            }),
            invalidatesTags: ['models'],
        }),
        updateModel: builder.mutation<IModel, IModelRequest>({
            query: (modelRequest) => ({
                url: `/models/${modelRequest.ModelId}`,
                method: 'PUT',
                data: modelRequest
            }),
            invalidatesTags: ['models'],
        }),
    }),
});

export const { useGetAllModelsQuery, useDeleteModelMutation, useStopModelMutation, useStartModelMutation, useCreateModelMutation, useUpdateModelMutation } =
  modelManagementApi;

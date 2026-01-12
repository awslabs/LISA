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
import { IConfiguration } from '../model/configuration.model';

export const configurationApi = createApi({
    reducerPath: 'configuration',
    baseQuery: lisaBaseQuery(),
    tagTypes: ['configuration'],
    refetchOnFocus: true,
    refetchOnMountOrArgChange: true,
    keepUnusedDataFor: 60, // Keep cache for 60s to prevent cancellation during rapid navigation
    endpoints: (builder) => ({
        getConfiguration: builder.query<IConfiguration[], string>({
            query: (configScope) => ({
                url: `/configuration?configScope=${configScope}`
            }),
            providesTags:['configuration'],
        }),
        updateConfiguration: builder.mutation<IConfiguration, IConfiguration>({
            query: (updatedConfig) => ({
                url: `/configuration/${updatedConfig.configScope}`,
                method: 'PUT',
                data: updatedConfig
            }),
            transformErrorResponse: (baseQueryReturnValue) => {
                // transform into SerializedError
                return {
                    name: 'Update Configuration Error',
                    message: baseQueryReturnValue.data?.type === 'RequestValidationError' ? baseQueryReturnValue.data.detail.map((error) => error.msg).join(', ') : baseQueryReturnValue.data.message
                };
            },
            invalidatesTags: ['configuration'],
        }),
    }),
});

export const {
    useGetConfigurationQuery,
    useUpdateConfigurationMutation,
    useLazyGetConfigurationQuery
} = configurationApi;

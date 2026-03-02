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
import {
    ITokenInfo,
    IListTokensResponse,
    ICreateTokenRequest,
    ICreateTokenResponse,
    IDeleteTokenResponse,
} from '../model/api-token.model';

export const apiTokenApi = createApi({
    reducerPath: 'apiTokens',
    baseQuery: lisaBaseQuery(),
    tagTypes: ['apiTokens'],
    refetchOnFocus: true,
    refetchOnReconnect: true,
    keepUnusedDataFor: 60, // Keep cache for 60s to prevent cancellation during rapid navigation
    endpoints: (builder) => ({
        listTokens: builder.query<ITokenInfo[], void>({
            query: () => ({
                url: '/api-tokens',
            }),
            transformResponse: (response: IListTokensResponse) => response.tokens,
            providesTags: ['apiTokens'],
        }),
        createTokenForUser: builder.mutation<ICreateTokenResponse, { username: string; request: ICreateTokenRequest }>({
            query: ({ username, request }) => ({
                url: `/api-tokens/${username}`,
                method: 'POST',
                data: request,
            }),
            transformErrorResponse: (baseQueryReturnValue) => {
                return {
                    name: 'Create Token Error',
                    message: baseQueryReturnValue.data?.type === 'RequestValidationError'
                        ? baseQueryReturnValue.data.detail.map((error: any) => error.msg).join(', ')
                        : baseQueryReturnValue.data?.message || 'Failed to create token',
                };
            },
            invalidatesTags: ['apiTokens'],
        }),
        createOwnToken: builder.mutation<ICreateTokenResponse, { name: string; tokenExpiration?: number }>({
            query: (request) => ({
                url: '/api-tokens/',
                method: 'POST',
                data: request,
            }),
            transformErrorResponse: (baseQueryReturnValue) => {
                return {
                    name: 'Create Token Error',
                    message: baseQueryReturnValue.data?.type === 'RequestValidationError'
                        ? baseQueryReturnValue.data.detail.map((error: any) => error.msg).join(', ')
                        : baseQueryReturnValue.data?.message || 'Failed to create token',
                };
            },
            invalidatesTags: ['apiTokens'],
        }),
        deleteToken: builder.mutation<IDeleteTokenResponse, string>({
            query: (tokenUUID) => ({
                url: `/api-tokens/${tokenUUID}`,
                method: 'DELETE',
            }),
            transformErrorResponse: (baseQueryReturnValue) => {
                return {
                    name: 'Delete Token Error',
                    message: baseQueryReturnValue.data?.message || 'Failed to delete token',
                };
            },
            invalidatesTags: ['apiTokens'],
        }),
    }),
});

export const {
    useListTokensQuery,
    useCreateTokenForUserMutation,
    useCreateOwnTokenMutation,
    useDeleteTokenMutation,
} = apiTokenApi;

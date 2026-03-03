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
import { normalizeError } from '../util/validationUtils';
import { IChatAssistantStack, IChatAssistantStackRequest } from '../model/chat-assistant-stack.model';

export type ChatAssistantStackListResponse = {
    Items: IChatAssistantStack[];
};

export const chatAssistantStacksApi = createApi({
    reducerPath: 'chatAssistantStacks',
    baseQuery: lisaBaseQuery(),
    tagTypes: ['chatAssistantStacks'],
    refetchOnFocus: true,
    refetchOnMountOrArgChange: true,
    keepUnusedDataFor: 60,
    endpoints: (builder) => ({
        listStacks: builder.query<IChatAssistantStack[], void>({
            query: () => ({
                url: '/chat-assistant-stacks',
                method: 'GET',
            }),
            transformResponse: (response: ChatAssistantStackListResponse) => response?.Items ?? [],
            providesTags: ['chatAssistantStacks'],
        }),
        getStack: builder.query<IChatAssistantStack, string>({
            query: (stackId) => ({
                url: `/chat-assistant-stacks/${stackId}`,
                method: 'GET',
            }),
            providesTags: (_result, _err, stackId) => [{ type: 'chatAssistantStacks', id: stackId }],
        }),
        createStack: builder.mutation<IChatAssistantStack, IChatAssistantStackRequest>({
            query: (body) => ({
                url: '/chat-assistant-stacks',
                method: 'POST',
                data: body,
            }),
            transformErrorResponse: (baseQueryReturnValue) => normalizeError('Create Chat Assistant Stack', baseQueryReturnValue),
            invalidatesTags: ['chatAssistantStacks'],
        }),
        updateStack: builder.mutation<IChatAssistantStack, { stackId: string; body: IChatAssistantStackRequest }>({
            query: ({ stackId, body }) => ({
                url: `/chat-assistant-stacks/${stackId}`,
                method: 'PUT',
                data: body,
            }),
            transformErrorResponse: (baseQueryReturnValue) => normalizeError('Update Chat Assistant Stack', baseQueryReturnValue),
            invalidatesTags: ['chatAssistantStacks'],
        }),
        deleteStack: builder.mutation<void, string>({
            query: (stackId) => ({
                url: `/chat-assistant-stacks/${stackId}`,
                method: 'DELETE',
            }),
            transformErrorResponse: (baseQueryReturnValue) => normalizeError('Delete Chat Assistant Stack', baseQueryReturnValue),
            invalidatesTags: ['chatAssistantStacks'],
        }),
        updateStackStatus: builder.mutation<IChatAssistantStack, { stackId: string; isActive: boolean }>({
            query: ({ stackId, isActive }) => ({
                url: `/chat-assistant-stacks/${stackId}/status`,
                method: 'PUT',
                data: { isActive },
            }),
            transformErrorResponse: (baseQueryReturnValue) => normalizeError('Update Stack Status', baseQueryReturnValue),
            invalidatesTags: ['chatAssistantStacks'],
        }),
    }),
});

export const {
    useListStacksQuery,
    useGetStackQuery,
    useCreateStackMutation,
    useUpdateStackMutation,
    useDeleteStackMutation,
    useUpdateStackStatusMutation,
} = chatAssistantStacksApi;

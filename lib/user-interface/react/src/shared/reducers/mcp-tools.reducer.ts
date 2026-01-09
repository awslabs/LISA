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
import {
    IMcpTool,
    IMcpToolListResponse,
    IMcpToolRequest,
    IMcpToolUpdateRequest,
    IMcpToolDeleteResponse,
    IMcpToolValidationResponse
} from '../model/mcp-tools.model';

export const mcpToolsApi = createApi({
    reducerPath: 'mcpTools',
    baseQuery: lisaBaseQuery(),
    tagTypes: ['mcpTools'],
    refetchOnFocus: true,
    refetchOnMountOrArgChange: true,
    keepUnusedDataFor: 60, // Keep cache for 60s to prevent cancellation during rapid navigation
    endpoints: (builder) => ({
        listMcpTools: builder.query<IMcpTool[], void>({
            query: () => ({
                url: '/mcp-workbench',
                method: 'GET'
            }),
            transformResponse: (response: IMcpToolListResponse) => response.tools,
            providesTags: ['mcpTools'],
        }),
        getMcpTool: builder.query<IMcpTool, string>({
            query: (toolId) => ({
                url: `/mcp-workbench/${toolId}`,
                method: 'GET'
            }),
            providesTags: ['mcpTools'],
        }),
        createMcpTool: builder.mutation<IMcpTool, IMcpToolRequest>({
            query: (mcpTool) => ({
                url: '/mcp-workbench',
                method: 'POST',
                data: mcpTool
            }),
            transformErrorResponse: (baseQueryReturnValue) => normalizeError('Create MCP Tool', baseQueryReturnValue),
            invalidatesTags: ['mcpTools'],
        }),
        updateMcpTool: builder.mutation<IMcpTool, { toolId: string; tool: IMcpToolUpdateRequest }>({
            query: ({ toolId, tool }) => ({
                url: `/mcp-workbench/${toolId}`,
                method: 'PUT',
                data: tool
            }),
            transformErrorResponse: (baseQueryReturnValue) => normalizeError('Update MCP Tool', baseQueryReturnValue),
            invalidatesTags: ['mcpTools'],
        }),
        deleteMcpTool: builder.mutation<IMcpToolDeleteResponse, string>({
            query: (toolId) => ({
                url: `/mcp-workbench/${toolId}`,
                method: 'DELETE'
            }),
            transformErrorResponse: (baseQueryReturnValue) => normalizeError('Delete MCP Tool', baseQueryReturnValue),
            invalidatesTags: ['mcpTools'],
        }),
        validateMcpTool: builder.mutation<IMcpToolValidationResponse, string>({
            query: (code) => ({
                url: '/mcp-workbench/validate-syntax',
                method: 'POST',
                data: {code}
            })
        })
    }),
});

export const {
    useListMcpToolsQuery,
    useGetMcpToolQuery,
    useLazyGetMcpToolQuery,
    useCreateMcpToolMutation,
    useUpdateMcpToolMutation,
    useDeleteMcpToolMutation,
    useValidateMcpToolMutation,
} = mcpToolsApi;

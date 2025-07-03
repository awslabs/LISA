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

export enum McpServerStatus {
    Active = 'active',
    Inactive = 'inactive'
}

export type McpClientConfig = {
    name?: string,
    version?: string
};
export type McpServer = {
    id: string;
    created: string;
    owner: string;
    url: string;
    name: string;
    description?: string;
    isOwner?: true;
    customHeaders?: Record<string, string>;
    clientConfig?: McpClientConfig;
    status?:McpServerStatus;
};

export type NewMcpServer = Partial<McpServer> & Pick<McpServer, | 'name' | 'url'>;

export const DefaultMcpServer: NewMcpServer = {
    name: '',
    url: '',
    description: '',
    clientConfig: {},
    status: McpServerStatus.Active
};

export type McpServerListResponse = {
    Items: McpServer[],
};

export const mcpServerApi = createApi({
    reducerPath: 'mcpServers',
    baseQuery: lisaBaseQuery(),
    tagTypes: ['mcpServers'],
    refetchOnFocus: true,
    refetchOnReconnect: true,
    endpoints: (builder) => ({
        createMcpServer: builder.mutation<McpServer, NewMcpServer>({
            query: (mcpServer) => ({
                url: '/mcp-server',
                method: 'POST',
                data: mcpServer
            }),
            transformErrorResponse: (baseQueryReturnValue) => normalizeError('Create MCP Server', baseQueryReturnValue),
            invalidatesTags: ['mcpServers'],
        }),
        getMcpServer: builder.query<McpServer, string>({
            query (serverId) {
                return {
                    url: `/mcp-server/${serverId}`,
                    method: 'GET'
                };
            },
            providesTags: ['mcpServers']
        }),
        listMcpServers: builder.query<McpServerListResponse, {showPublic: boolean}>({
            query () {
                return {
                    url: '/mcp-server',
                    method: 'GET'
                };
            },
            providesTags: ['mcpServers']
        }),
        updateMcpServer: builder.mutation<McpServer, McpServer>({
            query: (mcpServer) => ({
                url: `/mcp-server/${mcpServer.id}`,
                method: 'PUT',
                data: mcpServer
            }),
            transformErrorResponse: (baseQueryReturnValue) => normalizeError('Update MCP Server', baseQueryReturnValue),
            invalidatesTags: ['mcpServers'],
        }),
        deleteMcpServer: builder.mutation<any, string>({
            query: (serverId) => ({
                url: `/mcp-server/${serverId}`,
                method: 'DELETE',
            }),
            invalidatesTags: ['mcpServers']
        })
    })

});

export const {
    useCreateMcpServerMutation,
    useLazyGetMcpServerQuery,
    useListMcpServersQuery,
    useUpdateMcpServerMutation,
    useDeleteMcpServerMutation,
} = mcpServerApi;

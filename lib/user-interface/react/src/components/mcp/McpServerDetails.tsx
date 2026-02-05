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

import {
    Button,
    Grid,
    Header,
    Pagination,
    SpaceBetween,
    Spinner,
    Table,
    TextContent, Toggle
} from '@cloudscape-design/components';
import 'react';
import React, { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useCollection } from '@cloudscape-design/collection-hooks';
import { useLazyGetMcpServerQuery } from '@/shared/reducers/mcp-server.reducer';
import { useMcp } from 'use-mcp/react';
import StatusIndicator from '@cloudscape-design/components/status-indicator';
import Box from '@cloudscape-design/components/box';
import { setBreadcrumbs } from '@/shared/reducers/breadcrumbs.reducer';
import { useAppDispatch, useAppSelector } from '@/config/store';
import {
    DefaultUserPreferences,
    useGetUserPreferencesQuery, UserPreferences
} from '@/shared/reducers/user-preferences.reducer';
import { selectCurrentUsername } from '@/shared/reducers/user.reducer';
import { useMcpPreferencesUpdate } from './hooks/useMcpPreferencesUpdate';

export function McpServerDetails () {
    const { mcpServerId } = useParams();
    const dispatch = useAppDispatch();
    const [getMcpServerQuery, {isUninitialized, data, isFetching, isSuccess}] = useLazyGetMcpServerQuery();
    const {data: userPreferences} = useGetUserPreferencesQuery();
    const userName = useAppSelector(selectCurrentUsername);

    const { updatingItemId: updatingToolName, isUpdating, updateMcpPreferences } = useMcpPreferencesUpdate({
        successMessage: 'Successfully updated tool preferences',
        errorMessage: 'Error updating tool preferences'
    });

    // Derive preferences from userPreferences or defaults
    const preferences = userPreferences || {...DefaultUserPreferences, user: userName};
    const [localPreferences, setLocalPreferences] = useState<UserPreferences>(preferences);

    const toggleTool = (toolName: string, enabled: boolean) => {
        updateMcpPreferences(
            toolName,
            localPreferences,
            (existingMcpPrefs) => {
                const originalServer = existingMcpPrefs.enabledServers.find((server) => server.id === mcpServerId);
                if (!originalServer) {
                    return existingMcpPrefs; // Return unchanged if server not found
                }

                // Create a deep copy of the server with updated disabled tools
                const serverToUpdate = {
                    ...originalServer,
                    disabledTools: enabled
                        ? originalServer.disabledTools.filter((item) => item !== toolName)
                        : [...originalServer.disabledTools, toolName]
                };

                return {
                    ...existingMcpPrefs,
                    enabledServers: [
                        ...existingMcpPrefs.enabledServers.filter((server) => server.id !== mcpServerId),
                        serverToUpdate
                    ]
                };
            },
            setLocalPreferences
        );
    };

    if (isSuccess) {
        dispatch(setBreadcrumbs([
            { text: 'MCP Connections', href: '/mcp-connections' },
            { text: data?.name, href: '' }
        ]));
    }

    if (isUninitialized && mcpServerId) {
        getMcpServerQuery({mcpServerId});
    }

    const {
        state,          // Connection state: 'discovering' | 'authenticating' | 'connecting' | 'loading' | 'ready' | 'failed'
        tools,          // Available tools from MCP server
        clearStorage,   // Clear stored tokens and credentials
    } = useMcp({
        url: data?.url ?? ' ',
        clientName: data?.name,
        clientConfig: data?.clientConfig ?? undefined,
        customHeaders: data?.customHeaders ?? undefined,
        autoReconnect: true,
        autoRetry: true,
        debug: false,
        callbackUrl: `${window.location.origin}${window.env.API_BASE_URL.includes('.') ? '/' : window.env.API_BASE_URL}oauth/callback`,
    });

    const { paginationProps, items, collectionProps } = useCollection(tools, {
        selection: {
            defaultSelectedItems: [],
            trackBy: 'name',
            keepSelection: false
        },
        pagination: {
            defaultPage: 1,
            pageSize: 20
        }
    });

    return (
        <Table
            {...collectionProps}
            header={
                <Grid gridDefinition={[{ colspan:6 }, { colspan:6 }]}>
                    <Header counter={`(${tools.length.toString() ?? undefined})`}>
                        {data?.name} Tool Details
                    </Header>
                    <Box float='right' variant='div'>
                        <SpaceBetween direction='horizontal' size='s' alignItems='center'>
                            <Button onClick={() => clearStorage() }>Reset Connection</Button>
                            <StatusIndicator type={state === 'ready' ? 'success' : state.endsWith('ing') ? 'pending' : 'error'}>
                                {state === 'ready' ? 'Connected' : state.endsWith('ing') ? 'Pending' : 'Error'}
                            </StatusIndicator>
                        </SpaceBetween>
                    </Box>
                </Grid>
            }
            sortingDisabled={false}
            selectedItems={collectionProps.selectedItems}
            loading={isFetching || state === 'connecting'}
            loadingText='Loading Server Tools'
            empty={(
                <SpaceBetween direction='vertical' size='s' alignItems='center'>
                    <TextContent><small>Tools not found.</small></TextContent>
                </SpaceBetween>
            )}
            variant='full-page'
            pagination={<Pagination {...paginationProps} />}
            items={items}
            columnDefinitions={[
                { header: 'Use tool', cell: (item) => (
                    updatingToolName === item.name ? (
                        <Spinner size='normal' />
                    ) : (
                        <Toggle
                            checked={!localPreferences?.preferences?.mcp?.enabledServers.find((server) => server.id === mcpServerId)?.disabledTools.includes(item.name)}
                            onChange={({detail}) => toggleTool(item.name, detail.checked)}
                            disabled={isUpdating}
                        />
                    )
                )},
                { header: 'Name', cell: (item) => item.name},
                { header: 'Description', cell: (item) => item.description},
            ]}
        />
    );
}

export default McpServerDetails;

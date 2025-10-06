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
    Grid,
    Header,
    Pagination,
    SpaceBetween,
    Table,
    TextContent, Toggle
} from '@cloudscape-design/components';
import 'react';
import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useCollection } from '@cloudscape-design/collection-hooks';
import { useLazyGetMcpServerQuery } from '@/shared/reducers/mcp-server.reducer';
import { useMcp } from 'use-mcp/react';
import StatusIndicator from '@cloudscape-design/components/status-indicator';
import Box from '@cloudscape-design/components/box';
import { setBreadcrumbs } from '@/shared/reducers/breadcrumbs.reducer';
import { useAppDispatch, useAppSelector } from '@/config/store';
import {
    DefaultUserPreferences, McpPreferences,
    useGetUserPreferencesQuery, UserPreferences,
    useUpdateUserPreferencesMutation
} from '@/shared/reducers/user-preferences.reducer';
import { useNotificationService } from '@/shared/util/hooks';
import { selectCurrentUsername } from '@/shared/reducers/user.reducer';

export function McpServerDetails () {
    const { mcpServerId } = useParams();
    const dispatch = useAppDispatch();
    const [getMcpServerQuery, {isUninitialized, data, isFetching, isSuccess}] = useLazyGetMcpServerQuery();
    const {data: userPreferences} = useGetUserPreferencesQuery();
    const [preferences, setPreferences] = useState<UserPreferences>(undefined);
    const userName = useAppSelector(selectCurrentUsername);
    const [updatePreferences, {isSuccess: isUpdatingSuccess, isError: isUpdatingError, error: updateError}] = useUpdateUserPreferencesMutation();
    const notificationService = useNotificationService(dispatch);

    // create success notification
    useEffect(() => {
        if (isUpdatingSuccess) {
            notificationService.generateNotification('Successfully updated tool preferences', 'success');
        }
    }, [isUpdatingSuccess, notificationService]);

    // create failure notification
    useEffect(() => {
        if (isUpdatingError) {
            const errorMessage = 'data' in updateError ? (updateError.data?.message ?? updateError.data) : updateError.message;
            notificationService.generateNotification(`Error updating tool preferences: ${errorMessage}`, 'error');
        }
    }, [isUpdatingError, updateError, notificationService]);

    useEffect(() => {
        if (userPreferences) {
            setPreferences(userPreferences);
        } else {
            setPreferences({...DefaultUserPreferences, user: userName});
        }
    }, [userPreferences, userName]);

    const toggleTool = (toolName: string, enabled: boolean) => {
        const existingMcpPrefs = preferences.preferences.mcp ?? {enabledServers: [], overrideAllApprovals: false};
        const mcpPrefs: McpPreferences = {
            ...existingMcpPrefs,
            enabledServers: [...existingMcpPrefs.enabledServers]
        };

        const originalServer = mcpPrefs.enabledServers.find((server) => server.id === mcpServerId);
        if (!originalServer) return; // Early return if server not found

        // Create a deep copy of the server object with its nested arrays
        const serverToUpdate = {
            ...originalServer,
            disabledTools: [...originalServer.disabledTools],
        };

        if (enabled) {
            serverToUpdate.disabledTools = serverToUpdate.disabledTools.filter((item) => item !== toolName);
        } else {
            serverToUpdate.disabledTools = [...serverToUpdate.disabledTools, toolName];
        }

        mcpPrefs.enabledServers = [
            ...mcpPrefs.enabledServers.filter((server) => server.id !== mcpServerId),
            serverToUpdate
        ];
        updatePrefs(mcpPrefs);
    };

    const updatePrefs = (mcpPrefs: McpPreferences) => {
        const updated = {...preferences,
            preferences: {...preferences.preferences,
                mcp: {
                    ...preferences.preferences.mcp,
                    ...mcpPrefs
                }
            }
        };
        setPreferences(updated);
        updatePreferences(updated);
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
    } = useMcp({
        url: data?.url ?? ' ',
        callbackUrl: `${window.location.origin}/#/oauth/callback`,
        clientName: data?.name,
        clientConfig: data?.clientConfig ?? undefined,
        customHeaders: data?.customHeaders ?? undefined,
        autoReconnect: true,
        autoRetry: true,
        debug: false,
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
                        <StatusIndicator type={state === 'ready' ? 'success' : state.endsWith('ing') ? 'pending' : 'error'}>
                            {state === 'ready' ? 'Connected' : state.endsWith('ing') ? 'Pending' : 'Error'}
                        </StatusIndicator>
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
                { header: 'Use Tool', cell: (item) => <Toggle checked={!preferences?.preferences?.mcp?.enabledServers.find((server) => server.id === mcpServerId)?.disabledTools.includes(item.name)} onChange={({detail}) => toggleTool(item.name, detail.checked)}/>},
                { header: 'Name', cell: (item) => item.name},
                { header: 'Description', cell: (item) => item.description},
            ]}
        />
    );
}

export default McpServerDetails;

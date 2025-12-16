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
    Header,
    Link,
    Pagination,
    SpaceBetween,
    Table,
    TextContent,
    Toggle
} from '@cloudscape-design/components';
import 'react';
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCollection } from '@cloudscape-design/collection-hooks';
import {McpServerActions} from './McpServerActions';
import {
    McpServerStatus,
    useListMcpServersQuery,
} from '@/shared/reducers/mcp-server.reducer';
import { useAppDispatch, useAppSelector } from '@/config/store';
import { selectCurrentUserIsAdmin } from '@/shared/reducers/user.reducer';
import {
    DefaultUserPreferences, McpPreferences,
    useGetUserPreferencesQuery,
    UserPreferences, useUpdateUserPreferencesMutation
} from '@/shared/reducers/user-preferences.reducer';
import { useNotificationService } from '@/shared/util/hooks';
import { setBreadcrumbs } from '@/shared/reducers/breadcrumbs.reducer';

export function McpServerManagementComponent () {
    const navigate = useNavigate();
    const dispatch = useAppDispatch();
    const isUserAdmin = useAppSelector(selectCurrentUserIsAdmin);
    const {data: userPreferences} = useGetUserPreferencesQuery();
    const { data: {Items: allItems} = {Items: []}, isFetching } = useListMcpServersQuery(undefined, {});
    const [preferences, setPreferences] = useState<UserPreferences>(undefined);
    const [updatePreferences, {isSuccess: isUpdatingSuccess, isError: isUpdatingError, error: updateError}] = useUpdateUserPreferencesMutation();
    const notificationService = useNotificationService(dispatch);

    useEffect(() => {
        if (userPreferences) {
            setPreferences(userPreferences);
        } else {
            setPreferences({...DefaultUserPreferences});
        }
    }, [userPreferences]);

    // create success notification
    useEffect(() => {
        if (isUpdatingSuccess) {
            notificationService.generateNotification('Successfully updated server preferences', 'success');
        }
    }, [isUpdatingSuccess, notificationService]);

    // create failure notification
    useEffect(() => {
        if (isUpdatingError) {
            const errorMessage = 'data' in updateError ? (updateError.data?.message ?? updateError.data) : updateError.message;
            notificationService.generateNotification(`Error updating server preferences: ${errorMessage}`, 'error');
        }
    }, [isUpdatingError, updateError, notificationService]);

    const toggleServer = (serverId: string, serverName: string, enabled: boolean) => {
        const existingMcpPrefs = preferences.preferences.mcp ?? {enabledServers: [], overrideAllApprovals: false};
        const mcpPrefs: McpPreferences = {
            ...existingMcpPrefs,
            enabledServers: [...existingMcpPrefs.enabledServers]
        };
        if (enabled){
            mcpPrefs.enabledServers.push({id: serverId, name: serverName, enabled: true, disabledTools: [], autoApprovedTools: []});
        } else {
            mcpPrefs.enabledServers = mcpPrefs.enabledServers.filter((server) => server.id !== serverId);
        }
        updatePrefs(mcpPrefs);
    };

    const toggleAutopilotMode = () => {
        const existingMcpPrefs = preferences.preferences.mcp ?? {enabledServers: [], overrideAllApprovals: false};
        const mcpPrefs: McpPreferences = {
            ...existingMcpPrefs,
            overrideAllApprovals: !existingMcpPrefs.overrideAllApprovals
        };
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

    useEffect(() => {
        dispatch(setBreadcrumbs([
            { text: 'MCP Connections', href: '/mcp-connections' }
        ]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const { paginationProps, items, collectionProps, filteredItemsCount, actions } = useCollection(allItems, {
        selection: {
            defaultSelectedItems: [],
            trackBy: 'id',
            keepSelection: false
        },
        sorting: {
            defaultState: {
                isDescending: true,
                sortingColumn: {
                    sortingField: 'created'
                }
            }
        },
        filtering: {
            fields: ['name', 'owner'],
        },
        pagination: {
            defaultPage: 1,
            pageSize: 10
        }
    });

    return (
        <Table
            {...collectionProps}
            header={
                <Header counter={filteredItemsCount ? `(${filteredItemsCount})` : undefined} actions={<McpServerActions
                    selectedItems={collectionProps.selectedItems || []}
                    setSelectedItems={actions.setSelectedItems}
                    preferences={preferences?.preferences?.mcp}
                    toggleAutopilotMode={toggleAutopilotMode}
                />}
                description='Activate available MCP servers and tools to use in the AI Assistant. All tools will operate in Safe Mode by default.'
                >
                    MCP Connections
                </Header>
            }
            sortingDisabled={false}
            selectionType='single'
            selectedItems={collectionProps.selectedItems}
            loading={isFetching}
            loadingText='Loading MCP Connections'
            empty={(
                <SpaceBetween direction='vertical' size='s' alignItems='center'>
                    <TextContent><small>No MCP Connections found.</small></TextContent>
                    <Button variant='inline-link' onClick={() => navigate('./new')}>Create MCP Connection</Button>
                </SpaceBetween>
            )}
            variant='full-page'
            pagination={<Pagination {...paginationProps} />}
            items={items}
            columnDefinitions={[
                { header: 'Use server', cell: (item) => item.canUse ? <Toggle checked={preferences?.preferences?.mcp?.enabledServers.find((server) => server.id === item.id)?.enabled ?? false} onChange={({detail}) => toggleServer(item.id, item.name, detail.checked)}/> : <></>},
                { header: 'Name', cell: (item) => <Link onClick={() => navigate(`./${item.id}`)}>{item.name}</Link>},
                { header: 'Description', cell: (item) => item.description, id: 'description', sortingField: 'description'},
                { header: 'URL', cell: (item) => item.url, id: 'url', sortingField: 'url'},
                { header: 'Owner', cell: (item) => item.owner === 'lisa:public' ? <em>(public)</em> : item.owner, id: 'owner', sortingField: 'owner'},
                { header: 'Groups', cell: (item) => {
                    return item.groups?.length ? item.groups?.map((group) => group.replace(/^\w+?:/, '')).join(', ') : '-';
                }},
                { header: 'Updated', cell: (item) => item.created, id: 'created', sortingField: 'created'},
                ...(isUserAdmin ? [{ header: 'Status', cell: (item) => item.status ?? McpServerStatus.Inactive}] : [])
            ]}
        />
    );
}

export default McpServerManagementComponent;

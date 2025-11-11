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

import { ReactElement, useEffect, useMemo, useState } from 'react';
import {
    Box,
    Button,
    CollectionPreferences,
    Header,
    Pagination,
    SpaceBetween,
    Table,
    TextFilter,
} from '@cloudscape-design/components';
import { useCollection } from '@cloudscape-design/collection-hooks';
import { useLocalStorage } from '@/shared/hooks/use-local-storage';
import {
    HostedMcpServer,
    HostedMcpServerStatus,
    useListHostedMcpServersQuery,
} from '@/shared/reducers/mcp-server.reducer';
import { CreateHostedMcpServerModal } from './create-hosted/CreateHostedMcpServerModal';
import { McpManagementActions } from './McpManagementActions';
import {
    getDefaultPreferences,
    getTableDefinition,
    getTablePreference,
    PAGE_SIZE_OPTIONS,
} from './McpManagementTableConfig';

type Preferences = ReturnType<typeof getDefaultPreferences>;

const FINAL_STATUSES = new Set<HostedMcpServerStatus | undefined>([
    HostedMcpServerStatus.InService,
    HostedMcpServerStatus.Stopped,
    HostedMcpServerStatus.Failed,
]);

const EMPTY_STATE = (
    <Box margin={{ vertical: 'xs' }} textAlign='center'>
        <SpaceBetween size='m'>
            <b>No hosted MCP servers</b>
            <span>Create a hosted MCP server to see it listed here.</span>
        </SpaceBetween>
    </Box>
);

const NO_MATCH_STATE = (onClear: () => void) => (
    <Box margin={{ vertical: 'xs' }} textAlign='center'>
        <SpaceBetween size='m'>
            <b>No matches</b>
            <span>Try adjusting your search to find a hosted MCP server.</span>
            <Button onClick={onClear}>Clear filter</Button>
        </SpaceBetween>
    </Box>
);

export function McpManagementComponent (): ReactElement {
    const tableDefinition = useMemo(() => getTableDefinition(), []);
    const [preferences, setPreferences] = useLocalStorage<Preferences>(
        'HostedMcpServerPreferences',
        getDefaultPreferences(tableDefinition),
    );
    const [shouldPoll, setShouldPoll] = useState(true);
    const [createModalVisible, setCreateModalVisible] = useState(false);

    const {
        data: hostedServers = [],
        isFetching,
        refetch,
    } = useListHostedMcpServersQuery(undefined, {
        pollingInterval: shouldPoll ? 30000 : undefined,
        refetchOnMountOrArgChange: true,
        refetchOnFocus: false,
    });

    useEffect(() => {
        if (hostedServers.length) {
            const shouldContinuePolling = hostedServers.some(
                (server) => !FINAL_STATUSES.has(server.status),
            );
            setShouldPoll(shouldContinuePolling);
        }
    }, [hostedServers]);

    const {
        items,
        actions,
        filteredItemsCount,
        collectionProps,
        filterProps,
        paginationProps,
    } = useCollection(hostedServers, {
        filtering: {
            empty: EMPTY_STATE,
            noMatch: NO_MATCH_STATE(() => actions.setFiltering('')),
        },
        pagination: { pageSize: preferences.pageSize as number },
        sorting: {
            defaultState: {
                sortingColumn: {
                    sortingField: 'created',
                },
                isDescending: true,
            },
        },
        selection: { trackBy: 'id' },
    });

    const selectedItems = (collectionProps.selectedItems as HostedMcpServer[]) ?? [];

    return (
        <>
            <CreateHostedMcpServerModal
                visible={createModalVisible}
                setVisible={setCreateModalVisible}
            />
            <Table
                {...collectionProps}
                onSelectionChange={({ detail }) => actions.setSelectedItems(detail.selectedItems as HostedMcpServer[])}
                selectedItems={selectedItems}
                columnDefinitions={tableDefinition}
                columnDisplay={preferences.contentDisplay}
                stickyColumns={{ first: 1, last: 0 }}
                enableKeyboardNavigation
                resizableColumns
                variant='full-page'
                items={items}
                loading={isFetching}
                loadingText='Loading hosted MCP servers'
                selectionType='single'
                header={
                    <Header
                        counter={filteredItemsCount ? `(${filteredItemsCount})` : undefined}
                        actions={
                            <McpManagementActions
                                selectedItems={selectedItems}
                                setSelectedItems={(selected) => actions.setSelectedItems(selected)}
                                refetch={refetch}
                                onCreate={() => setCreateModalVisible(true)}
                            />
                        }
                    >
                        MCP servers
                    </Header>
                }
                filter={
                    <TextFilter
                        {...filterProps}
                        countText={filteredItemsCount === 1
                            ? '1 match'
                            : `${filteredItemsCount} matches`}
                        filteringPlaceholder='Search hosted MCP servers'
                    />
                }
                empty={EMPTY_STATE}
                pagination={<Pagination {...paginationProps} />}
                preferences={
                    <CollectionPreferences
                        title='Preferences'
                        confirmLabel='Confirm'
                        cancelLabel='Cancel'
                        preferences={preferences}
                        onConfirm={({ detail }) => setPreferences(detail as Preferences)}
                        pageSizePreference={{
                            title: 'Page size',
                            options: PAGE_SIZE_OPTIONS,
                        }}
                        contentDisplayPreference={{
                            title: 'Select visible columns',
                            options: getTablePreference(tableDefinition),
                        }}
                    />
                }
            />
        </>
    );
}

export default McpManagementComponent;

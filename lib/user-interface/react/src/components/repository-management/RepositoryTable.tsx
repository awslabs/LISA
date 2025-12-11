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

import { ReactElement, useState } from 'react';
import { CollectionPreferences, Header, Pagination, TextFilter } from '@cloudscape-design/components';
import SpaceBetween from '@cloudscape-design/components/space-between';
import { useListRagRepositoriesQuery } from '@/shared/reducers/rag.reducer';
import Table from '@cloudscape-design/components/table';
import {
    getDefaultPreferences,
    getTableDefinition,
    getTablePreference,
    PAGE_SIZE_OPTIONS,
    TableRow,
} from './RepositoryTableConfig';
import { useCollection } from '@cloudscape-design/collection-hooks';
import Box from '@cloudscape-design/components/box';
import { useLocalStorage } from '@/shared/hooks/use-local-storage';
import { RepositoryActions } from './RepositoryActions';
import CreateRepositoryModal from './createRepository/CreateRepositoryModal';

export function getMatchesCountText (count: number) {
    return count === 1 ? '1 match' : `${count} matches`;
}

export function RepositoryTable (): ReactElement {
    // Use a separate query instance for polling to avoid affecting other components
    const { data: allRepos, isLoading, refetch } = useListRagRepositoriesQuery(undefined, {
        refetchOnMountOrArgChange: 30
    });
    const tableDefinition: ReadonlyArray<TableRow> = getTableDefinition();
    const [preferences, setPreferences] = useLocalStorage('RepositoryPreferences', getDefaultPreferences(tableDefinition));
    const [newRepositoryModalVisible, setNewRepositoryModalVisible] = useState(false);
    const [isEdit, setEdit] = useState(false);

    const { items, actions, filteredItemsCount, collectionProps, filterProps, paginationProps } = useCollection(
        allRepos ?? [], {
            filtering: {
                empty: (
                    <Box margin={{ vertical: 'xs' }} textAlign='center'>
                        <SpaceBetween size='m'>
                            <b>No repositories</b>
                        </SpaceBetween>
                    </Box>
                ),
            },
            pagination: { pageSize: preferences.pageSize },
            sorting: {
                defaultState: {
                    sortingColumn: {
                        sortingField: 'repositoryName',
                    },
                },
            },
            selection: { trackBy: 'repositoryId' },
        },
    );

    return (
        <>
            <CreateRepositoryModal visible={newRepositoryModalVisible} setVisible={setNewRepositoryModalVisible}
                isEdit={isEdit}
                setIsEdit={setEdit} selectedItems={collectionProps.selectedItems}
                setSelectedItems={actions.setSelectedItems} />
            <Table
                {...collectionProps}
                selectedItems={collectionProps.selectedItems.length > 0 ? [collectionProps.selectedItems[0]] : []}
                onSelectionChange={({ detail }) => actions.setSelectedItems(detail.selectedItems)}
                columnDefinitions={tableDefinition}
                columnDisplay={preferences.contentDisplay}
                stickyColumns={{ first: 1, last: 0 }}
                resizableColumns
                enableKeyboardNavigation
                items={items}
                loading={isLoading && !allRepos}
                loadingText='Loading repositories'
                selectionType='single'
                filter={<TextFilter
                    {...filterProps}
                    countText={getMatchesCountText(filteredItemsCount)} />}
                header={<Header
                    counter={collectionProps.selectedItems.length
                        ? `(${collectionProps.selectedItems.length}/${allRepos.length})`
                        : `${allRepos?.length || 0}`}
                    actions={<SpaceBetween
                        direction='horizontal'
                        size='xs'
                    >
                        <RepositoryActions selectedItems={collectionProps.selectedItems}
                            setSelectedItems={actions.setSelectedItems}
                            setNewRepositoryModalVisible={setNewRepositoryModalVisible}
                            setEdit={setEdit}
                            refetchRepositories={refetch}></RepositoryActions>
                    </SpaceBetween>}
                >Repositories
                </Header>}
                pagination={<Pagination {...paginationProps} />}
                preferences={<CollectionPreferences
                    title='Preferences'
                    preferences={preferences}
                    confirmLabel='Confirm'
                    cancelLabel='Cancel'
                    onConfirm={({ detail }) => setPreferences(detail)}
                    contentDisplayPreference={{
                        title: 'Select visible columns',
                        options: getTablePreference(tableDefinition),
                    }}
                    pageSizePreference={{ title: 'Page size', options: PAGE_SIZE_OPTIONS }} />} />
        </>
    );
}

export default RepositoryTable;

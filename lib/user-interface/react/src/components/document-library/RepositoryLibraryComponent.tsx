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

import { ReactElement } from 'react';
import { Box, CollectionPreferences, Header, Pagination, Table, TextFilter } from '@cloudscape-design/components';
import SpaceBetween from '@cloudscape-design/components/space-between';
import {
    COLLECTION_COLUMN_DEFINITIONS,
    getCollectionTablePreference,
    getDefaultCollectionPreferences,
    PAGE_SIZE_OPTIONS,
} from './CollectionTableConfig';
import { useListAllCollectionsQuery } from '../../shared/reducers/rag.reducer';
import { useLocalStorage } from '../../shared/hooks/use-local-storage';
import { useNavigate } from 'react-router-dom';
import { useCollection } from '@cloudscape-design/collection-hooks';

export function RepositoryLibraryComponent(): ReactElement {
    const {
        data: allCollections,
        isLoading: fetchingCollections,
    } = useListAllCollectionsQuery(undefined, { refetchOnMountOrArgChange: 5 });

    const [preferences, setPreferences] = useLocalStorage(
        'CollectionLibraryPreferences',
        getDefaultCollectionPreferences()
    );

    const navigate = useNavigate();

    const { items, actions, filteredItemsCount, collectionProps, filterProps, paginationProps } = useCollection(
        allCollections ?? [],
        {
            filtering: {
                empty: (
                    <Box margin={{ vertical: 'xs' }} textAlign='center'>
                        <SpaceBetween size='m'>
                            <b>No collections</b>
                        </SpaceBetween>
                    </Box>
                ),
            },
            pagination: { pageSize: preferences.pageSize },
            sorting: {
                defaultState: {
                    sortingColumn: {
                        sortingField: 'name',
                    },
                },
            },
            selection: { trackBy: 'collectionId' },
        }
    );

    const handleSelectionChange = ({ detail }) => {
        actions.setSelectedItems(detail.selectedItems);
        if (detail.selectedItems.length > 0) {
            const selectedCollection = detail.selectedItems[0];
            navigate(`/document-library/${selectedCollection.repositoryId}/${selectedCollection.collectionId}`);
        }
    };

    return (
        <Table
            {...collectionProps}
            selectedItems={collectionProps.selectedItems}
            onSelectionChange={handleSelectionChange}
            columnDefinitions={COLLECTION_COLUMN_DEFINITIONS}
            columnDisplay={preferences.contentDisplay}
            stickyColumns={{ first: 1, last: 0 }}
            resizableColumns
            enableKeyboardNavigation
            items={items}
            loading={fetchingCollections && !allCollections}
            loadingText='Loading collections'
            selectionType='single'
            filter={
                <TextFilter
                    {...filterProps}
                    countText={`${filteredItemsCount} ${filteredItemsCount === 1 ? 'match' : 'matches'}`}
                    filteringPlaceholder='Find collections'
                />
            }
            header={
                <Header
                    counter={
                        collectionProps.selectedItems.length
                            ? `(${collectionProps.selectedItems.length}/${allCollections?.length || 0})`
                            : `${allCollections?.length || 0}`
                    }
                >
                    Collections
                </Header>
            }
            pagination={<Pagination {...paginationProps} />}
            preferences={
                <CollectionPreferences
                    title='Preferences'
                    preferences={preferences}
                    confirmLabel='Confirm'
                    cancelLabel='Cancel'
                    onConfirm={({ detail }) => setPreferences(detail)}
                    contentDisplayPreference={{
                        title: 'Select visible columns',
                        options: getCollectionTablePreference(),
                    }}
                    pageSizePreference={{ title: 'Page size', options: PAGE_SIZE_OPTIONS }}
                />
            }
        />
    );
}

export default RepositoryLibraryComponent;

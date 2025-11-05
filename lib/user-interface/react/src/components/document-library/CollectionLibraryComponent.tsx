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
import { Box, Button, ButtonDropdown, CollectionPreferences, Header, Icon, Pagination, Table, TextFilter } from '@cloudscape-design/components';
import SpaceBetween from '@cloudscape-design/components/space-between';
import {
    COLLECTION_COLUMN_DEFINITIONS,
    getCollectionTablePreference,
    getDefaultCollectionPreferences,
    PAGE_SIZE_OPTIONS,
} from '@/components/document-library/CollectionTableConfig';
import { ragApi, useDeleteCollectionMutation, useListAllCollectionsQuery } from '@/shared/reducers/rag.reducer';
import { useLocalStorage } from '@/shared/hooks/use-local-storage';
import { useCollection } from '@cloudscape-design/collection-hooks';
import { useAppDispatch } from '@/config/store';
import { setConfirmationModal } from '@/shared/reducers/modal.reducer';
import { CreateCollectionModal } from '@/components/document-library/createCollection/CreateCollectionModal';

interface CollectionLibraryComponentProps {
    admin?: boolean;
}

export function CollectionLibraryComponent ({ admin = false }: CollectionLibraryComponentProps): ReactElement {
    const {
        data: allCollections,
        isLoading: fetchingCollections,
    } = useListAllCollectionsQuery(undefined, { refetchOnMountOrArgChange: 5 });

    const [deleteCollection, { isLoading: isDeleteLoading }] = useDeleteCollectionMutation();
    const dispatch = useAppDispatch();

    const [preferences, setPreferences] = useLocalStorage(
        'CollectionLibraryPreferences',
        getDefaultCollectionPreferences()
    );

    // Modal state
    const [createCollectionModalVisible, setCreateCollectionModalVisible] = useState(false);
    const [isEdit, setIsEdit] = useState(false);

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
            selection: {
                trackBy: (item) => `${item.repositoryId}#${item.collectionId}`,
            },
        }
    );

    const handleSelectionChange = ({ detail }) => {
        if (admin) {
            actions.setSelectedItems(detail.selectedItems);
        }
        // Navigation is now handled by onRowClick to separate selection from navigation
    };

    const handleAction = async (e: any) => {
        switch (e.detail.id) {
            case 'edit': {
                setIsEdit(true);
                setCreateCollectionModalVisible(true);
                break;
            }
            case 'delete': {
                const selectedCollection = collectionProps.selectedItems[0];
                dispatch(
                    setConfirmationModal({
                        action: 'Delete',
                        resourceName: 'Collection',
                        onConfirm: () =>
                            deleteCollection({
                                repositoryId: selectedCollection.repositoryId,
                                collectionId: selectedCollection.collectionId,
                            }),
                        description: (
                            <div>
                                Are you sure you want to delete the collection{' '}
                                <strong>{selectedCollection.name || selectedCollection.collectionId}</strong>?
                                <br />
                                <br />
                                This action cannot be undone.
                            </div>
                        ),
                    }),
                );
                break;
            }
            default:
                console.error('Action not implemented', e.detail.id);
        }
    };

    return (
        <>
            {admin && (
                <CreateCollectionModal
                    visible={createCollectionModalVisible}
                    setVisible={setCreateCollectionModalVisible}
                    isEdit={isEdit}
                    setIsEdit={setIsEdit}
                    selectedItems={collectionProps.selectedItems}
                    setSelectedItems={actions.setSelectedItems}
                />
            )}
            <Table
                {...collectionProps}
                selectedItems={admin ? collectionProps.selectedItems: []}
                onSelectionChange={admin ? handleSelectionChange: undefined}
                columnDefinitions={COLLECTION_COLUMN_DEFINITIONS}
                columnDisplay={preferences.contentDisplay}
                stickyColumns={{ first: 1, last: 0 }}
                resizableColumns
                enableKeyboardNavigation
                items={items}
                loading={fetchingCollections && !allCollections}
                loadingText='Loading collections'
                selectionType={admin ? 'single': undefined}
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
                            admin && collectionProps.selectedItems.length
                                ? `(${collectionProps.selectedItems.length}/${allCollections?.length || 0})`
                                : `${allCollections?.length || 0}`
                        }
                        actions={
                            <SpaceBetween direction='horizontal' size='xs'>
                                <Button
                                    onClick={() => {
                                        if (admin) {
                                            actions.setSelectedItems([]);
                                        }
                                        dispatch(ragApi.util.invalidateTags(['collections']));
                                    }}
                                    ariaLabel='Refresh collections'
                                >
                                    <Icon name='refresh' />
                                </Button>
                                {admin && (
                                    <>
                                        <ButtonDropdown
                                            items={[
                                                {
                                                    id: 'edit',
                                                    text: 'Edit',
                                                    disabled: collectionProps.selectedItems.length === 0,
                                                },
                                                {
                                                    id: 'delete',
                                                    text: 'Delete',
                                                    disabled: collectionProps.selectedItems.length === 0,
                                                },
                                            ]}
                                            loading={isDeleteLoading}
                                            disabled={collectionProps.selectedItems.length === 0}
                                            onItemClick={handleAction}
                                        >
                                            Actions
                                        </ButtonDropdown>
                                        <Button
                                            variant='primary'
                                            onClick={() => {
                                                setIsEdit(false);
                                                setCreateCollectionModalVisible(true);
                                            }}
                                        >
                                            Create Collection
                                        </Button>
                                    </>
                                )}
                            </SpaceBetween>
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
        </>
    );
}

export default CollectionLibraryComponent;

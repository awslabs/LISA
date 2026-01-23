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
import { Box, Button, ButtonDropdown, CollectionPreferences, Header, Pagination, Table, TextFilter } from '@cloudscape-design/components';
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
import { CollectionStatus } from '#root/lib/schema/collectionSchema';
import { RefreshButton } from '@/components/common/RefreshButton';

type CollectionLibraryComponentProps = {
    admin?: boolean;
};

export function CollectionLibraryComponent ({ admin = false }: CollectionLibraryComponentProps): ReactElement {
    const {
        data: allCollections,
        isLoading: fetchingCollections,
        isFetching: isFetchingCollections,
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

    const selectedCollection = collectionProps.selectedItems.length === 1 ? collectionProps.selectedItems[0] : null;
    const isDefaultCollection = (selectedCollection as any)?.default === true;
    const collectionStatus = selectedCollection?.status;

    // Determine which actions should be disabled based on status
    const isEditDisabled = !selectedCollection ||
                          isDefaultCollection ||
                          collectionStatus === CollectionStatus.ARCHIVED ||
                          collectionStatus === CollectionStatus.DELETED ||
                          collectionStatus === CollectionStatus.DELETE_IN_PROGRESS;

    const isDeleteDisabled = !selectedCollection ||
                            collectionStatus === CollectionStatus.DELETED ||
                            collectionStatus === CollectionStatus.DELETE_IN_PROGRESS;

    const getEditDisabledReason = () => {
        if (!selectedCollection) return 'Please select a collection';
        if (isDefaultCollection) return 'Cannot edit default collection';
        if (collectionStatus === CollectionStatus.ARCHIVED) return 'Cannot edit archived collection';
        if (collectionStatus === CollectionStatus.DELETED) return 'Cannot edit deleted collection';
        if (collectionStatus === CollectionStatus.DELETE_IN_PROGRESS) return 'Cannot edit collection being deleted';
        return undefined;
    };

    const getDeleteDisabledReason = () => {
        if (!selectedCollection) return 'Please select a collection';
        if (collectionStatus === CollectionStatus.DELETED) return 'Collection already deleted';
        if (collectionStatus === CollectionStatus.DELETE_IN_PROGRESS) return 'Collection deletion in progress';
        return undefined;
    };

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
                if (!selectedCollection) return;

                dispatch(
                    setConfirmationModal({
                        action: 'Delete',
                        resourceName: 'Collection',
                        onConfirm: () =>
                            deleteCollection({
                                repositoryId: selectedCollection.repositoryId,
                                collectionId: selectedCollection.collectionId,
                                embeddingModel: selectedCollection.embeddingModel,
                                default: (selectedCollection as any).default,
                            }),
                        description: (
                            <div>
                                Are you sure you want to delete the collection{' '}
                                <strong>{selectedCollection.name || selectedCollection.collectionId}</strong>?
                                <br />
                                <br />
                                {isDefaultCollection ? (
                                    <>
                                        <strong>Note:</strong> This will remove all documents in the default collection,
                                        but the collection will remain visible in the Collection Library. This is a clean up operation.
                                        <br />
                                        <br />
                                    </>
                                ) : (
                                    <>This action cannot be undone.</>
                                )}
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
                selectedItems={admin ? collectionProps.selectedItems : []}
                onSelectionChange={admin ? handleSelectionChange : undefined}
                columnDefinitions={COLLECTION_COLUMN_DEFINITIONS}
                columnDisplay={preferences.contentDisplay}
                stickyColumns={{ first: 1, last: 0 }}
                resizableColumns
                enableKeyboardNavigation
                items={items}
                loading={fetchingCollections && !allCollections}
                loadingText='Loading collections'
                selectionType={admin ? 'single' : undefined}
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
                                <RefreshButton
                                    isLoading={isFetchingCollections}
                                    onClick={() => {
                                        if (admin) {
                                            actions.setSelectedItems([]);
                                        }
                                        dispatch(ragApi.util.invalidateTags(['collections']));
                                    }}
                                    ariaLabel='Refresh collections'
                                />
                                {admin && (
                                    <>
                                        <ButtonDropdown
                                            data-testid='collection-actions-button'
                                            items={[
                                                {
                                                    id: 'edit',
                                                    text: 'Edit',
                                                    disabled: isEditDisabled,
                                                    disabledReason: getEditDisabledReason(),
                                                },
                                                {
                                                    id: 'delete',
                                                    text: 'Delete',
                                                    disabled: isDeleteDisabled,
                                                    disabledReason: getDeleteDisabledReason(),
                                                },
                                            ]}
                                            loading={isDeleteLoading}
                                            disabled={!selectedCollection}
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

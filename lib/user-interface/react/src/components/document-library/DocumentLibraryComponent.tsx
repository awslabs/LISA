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

import * as React from 'react';
import { ReactElement, useState } from 'react';
import {
    ButtonDropdownProps,
    CollectionPreferences,
    Header,
    Pagination,
    TextFilter,
} from '@cloudscape-design/components';
import SpaceBetween from '@cloudscape-design/components/space-between';
import { useDeleteRagDocumentsMutation, useListRagDocumentsQuery } from '../../shared/reducers/rag.reducer';
import Table from '@cloudscape-design/components/table';
import ButtonDropdown from '@cloudscape-design/components/button-dropdown';
import { PAGE_SIZE_OPTIONS, TABLE_COLUMN_DISPLAY, TABLE_DEFINITION, TABLE_PREFERENCES } from './DocumentLibraryConfig';
import { useCollection } from '@cloudscape-design/collection-hooks';
import Box from '@cloudscape-design/components/box';
import { useAppDispatch, useAppSelector } from '../../config/store';
import { selectCurrentUserIsAdmin, selectCurrentUsername } from '../../shared/reducers/user.reducer';
import { RagDocument } from '../types';
import { setConfirmationModal } from '../../shared/reducers/modal.reducer';

interface DocumentLibraryComponentProps {
    repositoryId?: string;
}

export function getMatchesCountText (count) {
    return count === 1 ? `1 match` : `${count} matches`;
}

function canDeleteAll (selectedItems: ReadonlyArray<RagDocument>, username: string, isAdmin: boolean) {
    return selectedItems.length > 0 && (isAdmin || selectedItems.every(doc => doc.username === username));
}

export function DocumentLibraryComponent ({ repositoryId }: DocumentLibraryComponentProps): ReactElement {
    const { data: allDocs, isFetching } = useListRagDocumentsQuery({ repositoryId }, { refetchOnMountOrArgChange: 5 });
    const [deleteMutation, {
        isSuccess: isDeleteSuccess,
        isError: isDeleteError,
        error: deleteError,
        isLoading: isDeleteLoading,
    }] = useDeleteRagDocumentsMutation();
    const currentUser = useAppSelector(selectCurrentUsername);
    const isAdmin = useAppSelector(selectCurrentUserIsAdmin);
    const [preferences, setPreferences] = useState({ pageSize: 10, contentDisplay: TABLE_COLUMN_DISPLAY });
    const dispatch = useAppDispatch();

    const { items, actions, filteredItemsCount, collectionProps, filterProps, paginationProps } = useCollection(
        allDocs ?? [], {
            filtering: {
                empty: (
                    <Box margin={{ vertical: 'xs' }} textAlign="center">
                        <SpaceBetween size="m">
                            <b>No documents</b>
                        </SpaceBetween>
                    </Box>
                ),
            },
            pagination: { pageSize: preferences.pageSize },
            sorting: {
                defaultState: {
                    sortingColumn: {
                        sortingField: 'update_date',
                    },
                },
            },
            selection: { trackBy: 'document_id' },
        },
    );

    const actionItems: ButtonDropdownProps.Item[] = [
        {
            id: 'rm',
            text: 'Delete',
            disabled: !canDeleteAll(collectionProps.selectedItems, currentUser, isAdmin),
        },
    ];
    const handleAction = async (e: any) => {
        switch (e.detail.id) {
            case 'rm':
                const documentIds = collectionProps.selectedItems.map(doc => doc.document_id);
                const documentView = collectionProps.selectedItems.map(doc =>
                    <li>{doc.collection_id}/{doc.document_name}</li>);
                dispatch(
                    setConfirmationModal({
                        action: 'Delete',
                        resourceName: 'Documents',
                        onConfirm: () => deleteMutation({ repositoryId, documentIds }),
                        description: <div>This will delete the following documents: <ul>{documentView}</ul></div>,
                    }),
                );
                break;
            default:
                console.error('Action not implemented', e.detail.id);
        }
    };

    return (
        <Table
            {...collectionProps}
            selectedItems={collectionProps.selectedItems}
            onSelectionChange={({ detail }) =>
                actions.setSelectedItems(detail.selectedItems)
            }
            columnDefinitions={TABLE_DEFINITION}
            columnDisplay={preferences.contentDisplay}
            stickyColumns={{ first: 1, last: 0 }}
            resizableColumns
            enableKeyboardNavigation
            items={items}
            loading={isFetching}
            loadingText="Loading documents"
            selectionType="multi"
            filter={
                <TextFilter
                    {...filterProps}
                    countText={getMatchesCountText(filteredItemsCount)}
                />
            }
            header={
                <Header
                    counter={
                        collectionProps.selectedItems.length
                            ? `(${collectionProps.selectedItems.length}/${allDocs.length})`
                            : `${allDocs?.length || 0}`
                    }
                    actions={
                        <SpaceBetween
                            direction="horizontal"
                            size="xs"
                        >
                            <ButtonDropdown
                                items={actionItems}
                                loading={isDeleteLoading}
                                onItemClick={(e) => handleAction(e)}
                            >
                                Actions
                            </ButtonDropdown>
                        </SpaceBetween>
                    }
                >
                    {repositoryId} Documents
                </Header>
            }
            pagination={
                <Pagination {...paginationProps} />
            }
            preferences={
                <CollectionPreferences
                    title="Preferences"
                    preferences={preferences}
                    confirmLabel="Confirm"
                    cancelLabel="Cancel"
                    onConfirm={({ detail }) => setPreferences(detail)}
                    contentDisplayPreference={{ title: 'Select visible columns', options: TABLE_PREFERENCES }}
                    pageSizePreference={{ title: 'Page size', options: PAGE_SIZE_OPTIONS }}
                />
            }
        />
    );
}

export default DocumentLibraryComponent;

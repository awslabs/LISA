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
import { ReactElement } from 'react';
import {
    Button,
    ButtonDropdownProps,
    CollectionPreferences,
    Header,
    Icon,
    Pagination,
    TextFilter,
} from '@cloudscape-design/components';
import SpaceBetween from '@cloudscape-design/components/space-between';
import {
    ragApi,
    useDeleteRagDocumentsMutation,
    useLazyDownloadRagDocumentQuery,
    useListRagDocumentsQuery,
} from '../../shared/reducers/rag.reducer';
import Table from '@cloudscape-design/components/table';
import ButtonDropdown from '@cloudscape-design/components/button-dropdown';
import { DEFAULT_PREFERENCES, PAGE_SIZE_OPTIONS, TABLE_DEFINITION, TABLE_PREFERENCES } from './DocumentLibraryConfig';
import { useCollection } from '@cloudscape-design/collection-hooks';
import Box from '@cloudscape-design/components/box';
import { useAppDispatch, useAppSelector } from '../../config/store';
import { selectCurrentUserIsAdmin, selectCurrentUsername } from '../../shared/reducers/user.reducer';
import { RagDocument } from '../types';
import { setConfirmationModal } from '../../shared/reducers/modal.reducer';
import { useLocalStorage } from '../../shared/hooks/use-local-storage';
import { downloadFile } from '../../shared/util/downloader';

type DocumentLibraryComponentProps = {
    repositoryId?: string;
};

export function getMatchesCountText (count) {
    return count === 1 ? '1 match' : `${count} matches`;
}

function canDeleteAll (selectedItems: ReadonlyArray<RagDocument>, username: string, isAdmin: boolean) {
    return selectedItems.length > 0 && (isAdmin || selectedItems.every((doc) => doc.username === username));
}

function disabledDeleteReason (selectedItems: ReadonlyArray<RagDocument>) {
    return selectedItems.length === 0 ? 'Please select an item' : 'You are not an owner of all selected items';
}

export function DocumentLibraryComponent ({ repositoryId }: DocumentLibraryComponentProps): ReactElement {
    const { data: allDocs, isFetching } = useListRagDocumentsQuery({ repositoryId }, { refetchOnMountOrArgChange: 5 });
    const [deleteMutation, { isLoading: isDeleteLoading }] = useDeleteRagDocumentsMutation();

    const currentUser = useAppSelector(selectCurrentUsername);
    const isAdmin = useAppSelector(selectCurrentUserIsAdmin);
    const [preferences, setPreferences] = useLocalStorage('DocumentRagPreferences', DEFAULT_PREFERENCES);
    const dispatch = useAppDispatch();

    const { items, actions, filteredItemsCount, collectionProps, filterProps, paginationProps } = useCollection(
        allDocs ?? [], {
            filtering: {
                empty: (
                    <Box margin={{ vertical: 'xs' }} textAlign='center'>
                        <SpaceBetween size='m'>
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
    const [getDownloadUrl, { isFetching: isDownloading }] = useLazyDownloadRagDocumentQuery();
    const actionItems: ButtonDropdownProps.Item[] = [
        {
            id: 'rm',
            text: 'Delete',
            disabled: !canDeleteAll(collectionProps.selectedItems, currentUser, isAdmin),
            disabledReason: disabledDeleteReason(collectionProps.selectedItems),
        }, {
            id: 'download',
            text: 'Download',
            disabled: collectionProps.selectedItems.length > 1,
            disabledReason: 'Only one file can be downloaded at a time',
        },
    ];
    const handleAction = async (e: any) => {
        switch (e.detail.id) {
            case 'rm': {
                const documentIds = collectionProps.selectedItems.map((doc) => doc.document_id);
                const documentView = collectionProps.selectedItems.map((doc) =>
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
            }
            case 'download': {
                const { document_id, document_name } = collectionProps.selectedItems[0];
                const resp = await getDownloadUrl({ documentId: document_id, repositoryId });
                downloadFile(resp.data, document_name);
                break;
            }
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
            loadingText='Loading documents'
            selectionType='multi'
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
                            direction='horizontal'
                            size='xs'
                        >
                            <Button
                                onClick={() => {
                                    actions.setSelectedItems([]);
                                    dispatch(ragApi.util.invalidateTags(['docs']));
                                }}
                                ariaLabel={'Refresh models cards'}
                            >
                                <Icon name='refresh' />
                            </Button>
                            <ButtonDropdown
                                items={actionItems}
                                loading={isDeleteLoading || isDownloading}
                                disabled={collectionProps.selectedItems.length === 0}
                                onItemClick={async (e) => handleAction(e)}
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
                    title='Preferences'
                    preferences={preferences}
                    confirmLabel='Confirm'
                    cancelLabel='Cancel'
                    onConfirm={({ detail }) => setPreferences(detail)}
                    contentDisplayPreference={{ title: 'Select visible columns', options: TABLE_PREFERENCES }}
                    pageSizePreference={{ title: 'Page size', options: PAGE_SIZE_OPTIONS }}
                />
            }
        />
    );
}

export default DocumentLibraryComponent;

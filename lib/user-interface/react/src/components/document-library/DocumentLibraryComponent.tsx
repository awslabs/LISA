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
import {
    ragApi,
    useDeleteRagDocumentsMutation,
    useGetCollectionQuery,
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
import { RefreshButton } from '@/components/common/RefreshButton';
import DocumentSidePanel from '../chatbot/components/DocumentSidePanel';
import { useDocumentSidePanel } from '@/shared/hooks/useDocumentSidePanel';

type DocumentLibraryComponentProps = {
    repositoryId?: string;
    collectionId?: string;
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

function disabledViewReason (selectedItems: ReadonlyArray<RagDocument>) {
    return selectedItems.length === 0 ? 'Please select an item' : 'You can only view one item at a time';
}

export function DocumentLibraryComponent ({ repositoryId, collectionId }: DocumentLibraryComponentProps): ReactElement {
    const [deleteMutation, { isLoading: isDeleteLoading }] = useDeleteRagDocumentsMutation();

    const [currentPage, setCurrentPage] = useState(1);
    const [lastEvaluatedKey, setLastEvaluatedKey] = useState<{
        pk: string;
        document_id: string;
        repository_id: string;
    } | null>(null);
    const [pageHistory, setPageHistory] = useState<Array<{
        pk: string;
        document_id: string;
        repository_id: string;
    } | null>>([]);

    const currentUser = useAppSelector(selectCurrentUsername);
    const isAdmin = useAppSelector(selectCurrentUserIsAdmin);
    const [preferences, setPreferences] = useLocalStorage('DocumentRagPreferences', DEFAULT_PREFERENCES);
    const dispatch = useAppDispatch();
    
    // Document side panel management
    const { showDocSidePanel, selectedDocumentForPanel, handleOpenDocument, handleCloseDocPanel } = useDocumentSidePanel();

    // Fetch collection data if collectionId is provided
    const { data: collectionData } = useGetCollectionQuery(
        { repositoryId, collectionId },
        { skip: !repositoryId || !collectionId }
    );

    const { data: paginatedDocs, isLoading, isFetching } = useListRagDocumentsQuery(
        {
            repositoryId,
            collectionId,
            lastEvaluatedKey: lastEvaluatedKey || undefined,
            pageSize: preferences.pageSize
        },
        {
            refetchOnMountOrArgChange: 5,
            skip: !repositoryId // Skip the query if repositoryId is not available
        }
    );

    const allDocs = React.useMemo(() => paginatedDocs?.documents || [], [paginatedDocs?.documents]);
    const totalDocuments = paginatedDocs?.totalDocuments || 0;
    const hasNextPage = paginatedDocs?.hasNextPage || false;

    const { items, actions, filteredItemsCount, collectionProps, filterProps } = useCollection(
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
        },
        {
            id: 'download',
            text: 'Download',
            disabled: collectionProps.selectedItems.length > 1,
            disabledReason: 'Only one file can be downloaded at a time',
        },
        {
            id: 'view',
            text: 'View',
            disabled: collectionProps.selectedItems.length > 1,
            disabledReason: disabledViewReason(collectionProps.selectedItems),
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
                        description: <div>
                            This will delete the following documents: <ul>{documentView}</ul>
                            <span>
                                ⚠️ Batch delete will be processed in the background. Changes will not be reflected immediately and may take several minutes to complete.
                            </span>
                        </div>,
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
            case 'view': {
                const selectedDoc = collectionProps.selectedItems[0];
                handleOpenDocument({
                    documentId: selectedDoc.document_id,
                    repositoryId: selectedDoc.repository_id,
                    name: selectedDoc.document_name,
                    source: selectedDoc.collection_id || selectedDoc.repository_id,
                });
                break;
            }
            default:
                console.error('Action not implemented', e.detail.id);
                break;
        }
    };

    return (
        <div
            style={{
                overflow: 'scroll'
            }}
        >
            <div style={{ overflow: 'auto' }}>
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
                    variant='full-page'
                    loading={isLoading && !paginatedDocs}
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
                            counter={`(${totalDocuments})`}
                            actions={
                                <SpaceBetween
                                    direction='horizontal'
                                    size='xs'
                                >
                                    <RefreshButton
                                        isLoading={isFetching}
                                        onClick={() => {
                                            actions.setSelectedItems([]);
                                            dispatch(ragApi.util.invalidateTags(['docs']));
                                        }}
                                        ariaLabel='Refresh documents'
                                    />
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
                            {collectionId && collectionData
                                ? `${collectionData.name || collectionId} Documents`
                                : `${repositoryId} Documents`}
                        </Header>
                    }
                    pagination={
                        <Pagination
                            currentPageIndex={currentPage}
                            pagesCount={Math.ceil(totalDocuments / (preferences.pageSize || 10))}
                            onNextPageClick={() => {
                                if (hasNextPage && paginatedDocs?.lastEvaluated) {
                                    // Add current key to history before moving to next page
                                    setPageHistory([...pageHistory, lastEvaluatedKey]);
                                    setLastEvaluatedKey(paginatedDocs.lastEvaluated);
                                    // Update current page to reflect the navigation
                                    setCurrentPage((prev) => prev + 1);
                                }
                            }}
                            onPreviousPageClick={() => {
                                if (pageHistory.length > 0) {
                                    // Go back one page by popping from history
                                    const previousKey = pageHistory[pageHistory.length - 1];
                                    setPageHistory(pageHistory.slice(0, -1));
                                    setLastEvaluatedKey(previousKey);
                                    // Update current page to reflect the navigation
                                    setCurrentPage((prev) => prev - 1);
                                } else {
                                    // If no history, go to first page
                                    setLastEvaluatedKey(null);
                                    setCurrentPage(1);
                                }
                            }}
                            ariaLabels={{
                                nextPageLabel: 'Next page',
                                previousPageLabel: 'Previous page',
                                pageLabel: (pageNumber) => `Page ${pageNumber} of ${Math.ceil(totalDocuments / (preferences.pageSize || 10))}`,
                            }}
                        />
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
            </div>
            {/* Document side panel */}
            {showDocSidePanel && (
                <DocumentSidePanel
                    visible={showDocSidePanel}
                    onClose={handleCloseDocPanel}
                    document={selectedDocumentForPanel}
                />
            )}
        </div>
    );
}

export default DocumentLibraryComponent;

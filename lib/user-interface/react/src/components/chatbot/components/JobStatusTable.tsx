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

import React, { useState } from 'react';
import {
    Box,
    SpaceBetween,
    StatusIndicator,
    Table,
    Header,
    Icon,
    Pagination,
    TextFilter,
    CollectionPreferences,
    ButtonDropdown,
} from '@cloudscape-design/components';
import { RagConfig } from './RagOptions';
import { useGetIngestionJobsQuery, IngestionJob, ragApi } from '@/shared/reducers/rag.reducer';
import { faFileImport } from '@fortawesome/free-solid-svg-icons';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { useCollection } from '@cloudscape-design/collection-hooks';
import { useLocalStorage } from '../../../shared/hooks/use-local-storage';
import { useAppDispatch } from '../../../config/store';
import {
    DEFAULT_PREFERENCES,
    PAGE_SIZE_OPTIONS,
    TABLE_DEFINITION,
    TABLE_PREFERENCES,
    JobStatusItem,
    getMatchesCountText,
} from './JobStatusTableConfig';
import { RefreshButton } from '@/components/common/RefreshButton';

export type JobStatusTableProps = {
    ragConfig: RagConfig;
    autoLoad?: boolean;
    title?: string;
};

// Time filter options
const TIME_FILTER_OPTIONS = [
    { id: '1', text: '1 hour' },
    { id: '3', text: '3 hours' },
    { id: '6', text: '6 hours' },
    { id: '12', text: '12 hours' },
    { id: '24', text: '24 hours' },
    { id: '48', text: '48 hours' },
    { id: '72', text: '72 hours' },
    { id: '168', text: '1 week' }, // 7 days * 24 hours
];

export function JobStatusTable ({
    ragConfig,
    autoLoad = true,
    title = 'Recent Jobs'
}: JobStatusTableProps) {
    const [shouldFetch, setShouldFetch] = React.useState(autoLoad);
    const [currentPage, setCurrentPage] = useState(1);
    const [lastEvaluatedKey, setLastEvaluatedKey] = useState<any | null>(null);
    const [pageHistory, setPageHistory] = useState<Array<any | null>>([]);
    const [preferences, setPreferences] = useLocalStorage('JobStatusTablePreferences', DEFAULT_PREFERENCES);
    const [timeFilter, setTimeFilter] = useState({ id: '1', text: '1 hour' });
    const dispatch = useAppDispatch();

    // Create a unique query key that includes pagination state
    const queryParams = React.useMemo(() => ({
        repositoryId: ragConfig.repositoryId || '',
        pageSize: preferences.pageSize,
        lastEvaluatedKey: lastEvaluatedKey || undefined,
        timeLimit: parseInt(timeFilter.id, 10),
    }), [ragConfig.repositoryId, preferences.pageSize, lastEvaluatedKey, timeFilter.id]);

    const { data: paginatedJobs, isLoading: isLoadingJobs, error: jobsError, refetch } = useGetIngestionJobsQuery(
        queryParams,
        {
            skip: !ragConfig.repositoryId || !shouldFetch,
            refetchOnMountOrArgChange: true,
        }
    );

    // Refetch when pagination parameters change
    React.useEffect(() => {
        if (ragConfig.repositoryId && shouldFetch) {
            refetch();
        }
    }, [lastEvaluatedKey, refetch, ragConfig.repositoryId, shouldFetch]);

    // Auto-load jobs when component mounts or ragConfig changes
    React.useEffect(() => {
        if (autoLoad && ragConfig.repositoryId) {
            setShouldFetch(true);
        }
    }, [autoLoad, ragConfig.repositoryId, timeFilter.id]);

    // Reset pagination when page size or time filter changes
    React.useEffect(() => {
        setCurrentPage(1);
        setLastEvaluatedKey(null);
        setPageHistory([]);
    }, [preferences.pageSize, timeFilter.id]);

    const handleRefreshJobs = React.useCallback(() => {
        if (ragConfig.repositoryId) {
            console.log('JobStatusTable: Refreshing jobs for repository:', ragConfig.repositoryId);
            // Reset pagination state
            setCurrentPage(1);
            setLastEvaluatedKey(null);
            setPageHistory([]);
            // Enable fetching if it was disabled
            setShouldFetch(true);
            // Force a refetch and invalidate cache
            dispatch(ragApi.util.invalidateTags(['docs']));
            refetch();
        }
    }, [ragConfig.repositoryId, refetch, dispatch]);

    const handleTimeFilterChange = React.useCallback((event: any) => {
        const selectedId = event.detail.id;
        const selectedOption = TIME_FILTER_OPTIONS.find((option) => option.id === selectedId);
        if (selectedOption) {
            setTimeFilter(selectedOption);
            // Reset pagination when changing time filter
            setCurrentPage(1);
            setLastEvaluatedKey(null);
            setPageHistory([]);
        }
    }, []);

    const allJobs = React.useMemo(() => {
        // Handle both old format (Dict[str, IngestionJob]) and new format (PaginatedIngestionJobsResponse)
        let jobsArray: IngestionJob[] = [];

        if (paginatedJobs?.jobs && Array.isArray(paginatedJobs.jobs)) {
            // New paginated format
            jobsArray = paginatedJobs.jobs;
        } else if (paginatedJobs && typeof paginatedJobs === 'object' && !Array.isArray(paginatedJobs) && !('jobs' in paginatedJobs)) {
            // Old format - convert object values to array
            jobsArray = Object.values(paginatedJobs as unknown as Record<string, IngestionJob>);
        }

        return jobsArray.map((job: IngestionJob): JobStatusItem => ({
            id: job.id,
            document_name: job.document_name,
            status: job.status,
            auto: job.auto,
            created_date: job.created_date,
            username: job.username,
            collection_id: job.collection_id,
        }));
    }, [paginatedJobs]);

    const currentPageJobs = allJobs.length;
    const hasNextPage = paginatedJobs?.hasNextPage || false;
    const hasPreviousPage = currentPage > 1;

    // For server-side pagination, we only use useCollection for filtering
    // Disable both pagination and sorting since they're handled server-side
    const { items, filteredItemsCount, filterProps } = useCollection(
        allJobs, {
            filtering: {
                empty: (
                    <Box margin={{ vertical: 'xs' }} textAlign='center'>
                        <SpaceBetween size='m'>
                            <b>No jobs found</b>
                        </SpaceBetween>
                    </Box>
                ),
            },
            // Disable client-side pagination entirely for server-side pagination
            pagination: { pageSize: allJobs.length || 1 },
            // Disable client-side sorting since it's handled server-side
            sorting: {},
        },
    );

    // For server-side pagination, we need to create our own collection props
    const collectionProps = {
        items,
        trackBy: 'id',
        empty: (
            <Box margin={{ vertical: 'xs' }} textAlign='center'>
                <SpaceBetween size='m'>
                    <b>No jobs found</b>
                </SpaceBetween>
            </Box>
        ),
    };

    if (!ragConfig.repositoryId) {
        return null;
    }

    return (
        <SpaceBetween direction='vertical' size='s'>
            {jobsError && (
                <StatusIndicator type='error'>
                    Failed to load job status{currentPage > 1 ? ` for page ${currentPage}` : ''}
                </StatusIndicator>
            )}

            <Table
                {...collectionProps}
                variant='embedded'
                columnDefinitions={TABLE_DEFINITION}
                columnDisplay={preferences.contentDisplay}
                stickyColumns={{ first: 1, last: 0 }}
                resizableColumns
                enableKeyboardNavigation
                items={items}
                loading={isLoadingJobs}
                loadingText={currentPage > 1 ? `Loading page ${currentPage}...` : 'Loading job status...'}
                filter={
                    <TextFilter
                        {...filterProps}
                        countText={getMatchesCountText(filteredItemsCount)}
                    />
                }
                header={
                    <Header
                        counter={`(${currentPageJobs})`}
                        actions={
                            <SpaceBetween direction='horizontal' size='xs' >
                                <ButtonDropdown
                                    items={TIME_FILTER_OPTIONS}
                                    onItemClick={handleTimeFilterChange}
                                    ariaLabel='Time filter'
                                >
                                    <Icon name='calendar' />
                                </ButtonDropdown>
                                <RefreshButton
                                    isLoading={isLoadingJobs}
                                    onClick={handleRefreshJobs}
                                    ariaLabel='Refresh jobs'
                                />
                            </SpaceBetween>
                        }
                    >
                        {title}
                    </Header>
                }
                pagination={
                    <Pagination
                        currentPageIndex={currentPage}
                        pagesCount={hasNextPage ? currentPage + 1 : currentPage}
                        disabled={isLoadingJobs}
                        onNextPageClick={() => {
                            if (hasNextPage && paginatedJobs?.lastEvaluatedKey) {
                                // Add current key to history before moving to next page
                                setPageHistory([...pageHistory, lastEvaluatedKey]);
                                setLastEvaluatedKey(paginatedJobs.lastEvaluatedKey);
                                setCurrentPage((prev) => prev + 1);
                            }
                        }}
                        onPreviousPageClick={() => {
                            if (hasPreviousPage) {
                                if (pageHistory.length > 0) {
                                    // Go back one page by popping from history
                                    const previousKey = pageHistory[pageHistory.length - 1];
                                    setPageHistory(pageHistory.slice(0, -1));
                                    setLastEvaluatedKey(previousKey);
                                    setCurrentPage((prev) => prev - 1);
                                    console.log('Previous page state updated', {
                                        previousKey,
                                        newPage: currentPage - 1
                                    });
                                } else {
                                    // If no history, go to first page
                                    setLastEvaluatedKey(null);
                                    setCurrentPage(1);
                                    console.log('Reset to first page');
                                }
                            }
                        }}
                        ariaLabels={{
                            nextPageLabel: hasNextPage ? 'Next page' : 'Next page (disabled)',
                            previousPageLabel: hasPreviousPage ? 'Previous page' : 'Previous page (disabled)',
                            pageLabel: (pageNumber) => `Page ${pageNumber}${hasNextPage ? ' of many' : ''}`,
                        }}
                    />
                }
                preferences={
                    <CollectionPreferences
                        title='Preferences'
                        preferences={preferences}
                        confirmLabel='Confirm'
                        cancelLabel='Cancel'
                        onConfirm={({ detail }) => {
                            setPreferences(detail);
                        }}
                        contentDisplayPreference={{ title: 'Select visible columns', options: TABLE_PREFERENCES }}
                        pageSizePreference={{ title: 'Page size', options: PAGE_SIZE_OPTIONS }}
                    />
                }
                footer={
                    <small>
                        * Automated ingestion via pipeline are marked with <FontAwesomeIcon icon={faFileImport} />
                    </small>
                }
            />
        </SpaceBetween>
    );
}

export default JobStatusTable;

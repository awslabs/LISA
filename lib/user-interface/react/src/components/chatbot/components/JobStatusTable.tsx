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

import React from 'react';
import {
    Box,
    Button,
    SpaceBetween,
    StatusIndicator,
    TextContent,
    Table,
    Header,
    Icon,
} from '@cloudscape-design/components';
import { RagConfig } from './RagOptions';
import { useGetIngestionJobsQuery, IngestionJob } from '@/shared/reducers/rag.reducer';
import { faFileImport } from '@fortawesome/free-solid-svg-icons';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';

export type JobStatusTableProps = {
    ragConfig: RagConfig;
    autoLoad?: boolean;
    showDescription?: boolean;
    title?: string;
};

// Helper function to get status type and display info for job states
const getJobStatusInfo = (status: string) => {
    const upperStatus = status.toUpperCase();

    // Determine operation type
    const displayName = upperStatus.includes('INGESTION') ? 'Ingesting' :
        upperStatus.includes('DELETE') ? 'Deleting' : 'Unknown';

    // Determine status state and type
    let statusType: 'pending' | 'loading' | 'success' | 'error' = 'pending';
    let statusText = 'Unknown';

    if (upperStatus.includes('PENDING')) {
        statusType = 'pending';
        statusText = 'Pending';
    } else if (upperStatus.includes('IN_PROGRESS') || upperStatus.includes('IN-PROGRESS')) {
        statusType = 'loading';
        statusText = 'In Progress';
    } else if (upperStatus.includes('COMPLETED')) {
        statusType = 'success';
        statusText = 'Completed';
    } else if (upperStatus.includes('FAILED')) {
        statusType = 'error';
        statusText = 'Failed';
    }

    return {
        type: statusType,
        displayName,
        text: statusText
    };
};

export function JobStatusTable ({
    ragConfig,
    autoLoad = true,
    showDescription = true,
    title = 'Recent Jobs'
}: JobStatusTableProps) {
    const [shouldFetch, setShouldFetch] = React.useState(autoLoad);

    const { data: jobsData, isLoading: isLoadingJobs, error: jobsError, refetch } = useGetIngestionJobsQuery(
        ragConfig.repositoryId || '',
        {
            skip: !ragConfig.repositoryId || !shouldFetch,
            refetchOnMountOrArgChange: true,
        }
    );

    // Auto-load jobs when component mounts or ragConfig changes
    React.useEffect(() => {
        if (autoLoad && ragConfig.repositoryId) {
            setShouldFetch(true);
        }
    }, [autoLoad, ragConfig.repositoryId]);

    const handleRefreshJobs = React.useCallback(() => {
        if (ragConfig.repositoryId) {
            console.log('JobStatusTable: Refreshing jobs for repository:', ragConfig.repositoryId);
            // Enable fetching if it was disabled
            setShouldFetch(true);
            // Force a refetch
            refetch();
        }
    }, [ragConfig.repositoryId, refetch]);

    const jobItems = jobsData ? Object.entries(jobsData)
        .filter(([, jobInfo]) => jobInfo !== null)
        .map(([jobId, jobInfo]: [string, IngestionJob]) => ({
            jobId,
            document: jobInfo.document,
            status: jobInfo.status,
            auto: jobInfo.auto,
            lastUpdate: jobInfo.lastUpdate,
        })) : [];

    if (!ragConfig.repositoryId) {
        return null;
    }

    return (
        <SpaceBetween direction='vertical' size='s'>
            {showDescription && (
                <TextContent>
                    <h4>{title}</h4>
                    <p>
                        <small>
                            View the status of recent RAG document ingestion and deletion jobs.
                        </small>
                    </p>
                </TextContent>
            )}

            {jobsError && (
                <StatusIndicator type='error'>
                    Failed to load job status
                </StatusIndicator>
            )}

            <Table
                resizableColumns
                columnDefinitions={[
                    {
                        id: 'document',
                        header: 'Document',
                        cell: (item) => (
                            <SpaceBetween direction='horizontal' size='xs'>
                                {item.auto && (<FontAwesomeIcon icon={faFileImport} />)}
                                <span
                                    title={item.document}
                                    className='truncate max-w-[30ch] block'
                                >
                                    {item.document}
                                </span>
                            </SpaceBetween>
                        ),
                    },
                    {
                        id: 'jobId',
                        header: 'Job ID',
                        cell: (item) => (
                            <span className='font-mono text-sm text-gray-500'>
                                {item.jobId}
                            </span>
                        ),
                    },
                    {
                        id: 'status',
                        header: 'Status',
                        cell: (item) => {
                            const statusInfo = getJobStatusInfo(item.status);
                            return (
                                <StatusIndicator type={statusInfo.type}>
                                    {statusInfo.displayName}: {statusInfo.text}
                                </StatusIndicator>
                            );
                        },
                    },
                    {
                        id: 'lastUpdate',
                        header: 'Created Date',
                        cell: (item) => {
                            if (!item.createdDate) {
                                return <span className='text-gray-500'>-</span>;
                            }

                            // Format the date - assuming it's a timestamp or ISO string
                            const date = new Date(item.lastUpdate);
                            if (isNaN(date.getTime())) {
                                return <span className='text-gray-500'>-</span>;
                            }

                            return (
                                <span className='text-sm'>
                                    {date.toLocaleDateString()} {date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                </span>
                            );
                        },
                    },
                ]}
                items={jobItems}
                loading={isLoadingJobs}
                loadingText='Loading job status...'
                empty={
                    <Box textAlign='center' color='inherit'>
                        <b>No recent jobs found</b>
                        <Box padding={{ bottom: 's' }} variant='p' color='inherit'>
                            No recent jobs found for this repository.
                        </Box>
                    </Box>
                }
                header={
                    <Header
                        counter={jobItems.length ? `(${jobItems.length})` : ''}
                        actions={
                            <Button
                                onClick={handleRefreshJobs}
                                disabled={isLoadingJobs}
                                ariaLabel={'Refresh documents'}
                            >
                                <Icon name='refresh' />
                            </Button>
                        }
                    >
                        {title}
                    </Header>
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

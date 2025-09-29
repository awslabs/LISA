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
    Modal,
    SpaceBetween,
    StatusIndicator,
    TextContent,
    Table,
    Header,
    Icon,
} from '@cloudscape-design/components';
import { RagConfig } from './RagOptions';
import { useLazyGetIngestionJobsQuery } from '@/shared/reducers/rag.reducer';

export type JobStatusProps = {
    showJobStatusModal: boolean;
    setShowJobStatusModal: React.Dispatch<React.SetStateAction<boolean>>;
    ragConfig: RagConfig;
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

export function JobStatusModal ({
    showJobStatusModal,
    setShowJobStatusModal,
    ragConfig,
}: JobStatusProps) {
    const [getIngestionJobs, { data: jobsData, isLoading, error }] = useLazyGetIngestionJobsQuery();

    const handleRefresh = React.useCallback(() => {
        if (ragConfig.repositoryId) {
            getIngestionJobs(ragConfig.repositoryId);
        }
    }, [ragConfig.repositoryId, getIngestionJobs]);

    // Load jobs when modal opens
    React.useEffect(() => {
        if (showJobStatusModal && ragConfig.repositoryId) {
            handleRefresh();
        }
    }, [showJobStatusModal, ragConfig.repositoryId, handleRefresh]);

    const jobItems = jobsData ? Object.entries(jobsData).map(([jobId, jobInfo]) => ({
        jobId,
        document: typeof jobInfo === 'object' ? jobInfo.document : 'Unknown',
        status: typeof jobInfo === 'string' ? jobInfo : jobInfo.status,
        auto: typeof jobInfo === 'object' ? jobInfo.auto : false,
    })) : [];

    return (
        <Modal
            onDismiss={() => setShowJobStatusModal(false)}
            visible={showJobStatusModal}
            header='RAG Job Status'
            size='large'
            footer={
                <Box float='right'>
                    <SpaceBetween direction='horizontal' size='xs'>
                        <Button onClick={handleRefresh} disabled={isLoading}>
                            Refresh
                        </Button>
                        <Button onClick={() => setShowJobStatusModal(false)}>
                            Close
                        </Button>
                    </SpaceBetween>
                </Box>
            }
        >
            <SpaceBetween direction='vertical' size='s'>
                <TextContent>
                    <h4>RAG Job Status</h4>
                    <p>
                        <small>
                            View the status of RAG document ingestion and deletion jobs. Jobs are created when documents are uploaded to or removed from the RAG repository. Pipeline jobs (marked with <Icon name='workflow' variant='subtle' size='small' />) are automated processes.
                        </small>
                    </p>
                </TextContent>

                {error && (
                    <StatusIndicator type='error'>
                        Failed to load job status
                    </StatusIndicator>
                )}

                <Table
                    columnDefinitions={[
                        {
                            id: 'document',
                            header: 'Document',
                            cell: (item) => (
                                <SpaceBetween direction='horizontal' size='xs'>
                                    {item.auto && (
                                        <Icon
                                            name='workflow'
                                            variant='normal'
                                            size='small'
                                        />
                                    )}
                                    <span>{item.document}</span>
                                </SpaceBetween>
                            ),
                        },
                        {
                            id: 'jobId',
                            header: 'Job ID',
                            cell: (item) => (
                                <span style={{ fontFamily: 'monospace', fontSize: '0.85em', color: '#5f6b7a' }}>
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
                    ]}
                    items={jobItems}
                    loading={isLoading}
                    loadingText='Loading job status...'
                    empty={
                        <Box textAlign='center' color='inherit'>
                            <b>No jobs found</b>
                            <Box padding={{ bottom: 's' }} variant='p' color='inherit'>
                                No jobs found for this repository.
                            </Box>
                        </Box>
                    }
                    header={
                        <Header
                            counter={jobItems.length ? `(${jobItems.length})` : ''}
                        >
                            RAG Jobs
                        </Header>
                    }
                />
            </SpaceBetween>
        </Modal>
    );
}

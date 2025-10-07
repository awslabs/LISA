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
import { SpaceBetween, StatusIndicator } from '@cloudscape-design/components';
import { CollectionPreferencesProps } from '@cloudscape-design/components';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faFileImport } from '@fortawesome/free-solid-svg-icons';
import { DEFAULT_PAGE_SIZE_OPTIONS } from '../../../shared/preferences/common-preferences';

export type JobStatusItem = {
    id: string;
    document_name: string;
    status: string;
    auto: boolean;
    created_date: string;
    username: string;
    collection_id: string;
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

export const PAGE_SIZE_OPTIONS = DEFAULT_PAGE_SIZE_OPTIONS('Jobs');

export const TABLE_DEFINITION: {
    id: string,
    header: string,
    cell: (item: JobStatusItem) => React.ReactNode,
    sortingField?: string,
    isRowHeader?: boolean,
    visible: boolean
}[] = [
    {
        id: 'document_name',
        header: 'Document',
        cell: (item) => (
            <SpaceBetween direction='horizontal' size='xs'>
                {item.auto && (<FontAwesomeIcon icon={faFileImport} />)}
                <span
                    title={item.document_name.replace(/^\d+?_/, '')}
                    className='truncate max-w-[30ch] block'
                >
                    {item.document_name.replace(/^\d+?_/, '')}
                </span>
            </SpaceBetween>
        ),
        sortingField: 'document_name',
        visible: true,
    },
    {
        id: 'id',
        header: 'Job ID',
        cell: (item) => (
            <span className='font-mono text-sm text-gray-500'>
                {item.id}
            </span>
        ),
        sortingField: 'id',
        isRowHeader: true,
        visible: false,
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
        sortingField: 'status',
        visible: true,
    },
    {
        id: 'username',
        header: 'User',
        cell: (item) => (
            <span className='text-sm'>
                {item.username}
            </span>
        ),
        sortingField: 'username',
        visible: false,
    },
    {
        id: 'collection_id',
        header: 'Collection',
        cell: (item) => (
            <span className='text-sm text-gray-600'>
                {item.collection_id}
            </span>
        ),
        sortingField: 'collection_id',
        visible: false,
    },
    {
        id: 'created_date',
        header: 'Created Date',
        cell: (item) => {
            if (!item.created_date) {
                return <span className='text-gray-500'>-</span>;
            }

            // Format the date - assuming it's a timestamp or ISO string
            const date = new Date(item.created_date);
            if (isNaN(date.getTime())) {
                return <span className='text-gray-500'>-</span>;
            }

            return (
                <span className='text-sm'>
                    {date.toLocaleDateString()} {date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
            );
        },
        sortingField: 'created_date',
        visible: true
    }
];

export const TABLE_PREFERENCES = (() => TABLE_DEFINITION.map((c) => ({ id: c.id, label: c.header })))();

export const TABLE_COLUMN_DISPLAY: CollectionPreferencesProps.ContentDisplayItem[] = (() => TABLE_DEFINITION.map((c) => ({
    id: c.id,
    visible: c.visible,
})))();

export const DEFAULT_PREFERENCES: CollectionPreferencesProps.Preferences = {
    pageSize: PAGE_SIZE_OPTIONS[0].value,
    contentDisplay: TABLE_COLUMN_DISPLAY,
};

export function getMatchesCountText (count: number): string {
    return count === 1 ? '1 match' : `${count} matches`;
}

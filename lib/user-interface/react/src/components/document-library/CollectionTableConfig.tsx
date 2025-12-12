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

import { CollectionPreferencesProps, TableProps } from '@cloudscape-design/components';
import { DEFAULT_PAGE_SIZE_OPTIONS } from '@/shared/preferences/common-preferences';
import Badge from '@cloudscape-design/components/badge';
import Link from '@cloudscape-design/components/link';
import StatusIndicator, { StatusIndicatorProps } from '@cloudscape-design/components/status-indicator';
import { ReactNode } from 'react';
import { RagCollectionConfig } from '@/shared/reducers/rag.reducer';
import { CollectionStatus } from '#root/lib/schema';
import { formatDate, formatObject } from '@/shared/util/formats';

export const PAGE_SIZE_OPTIONS = DEFAULT_PAGE_SIZE_OPTIONS('Collections');

export type CollectionTableRow = TableProps.ColumnDefinition<RagCollectionConfig> & {
    visible: boolean;
    header: string;
};

export const COLLECTION_COLUMN_DEFINITIONS: ReadonlyArray<CollectionTableRow> = [
    {
        id: 'name',
        header: 'Collection Name',
        cell: (collection) => (
            <>
                <Link href={`#/document-library/${collection.repositoryId}/${collection.collectionId}`}>
                    {collection.name || collection.collectionId}
                </Link>
                {(collection as any).default === true && (
                    <> <Badge color='blue'>Global</Badge></>
                )}
            </>
        ),
        sortingField: 'name',
        visible: true,
        isRowHeader: true,
    },
    {
        id: 'collectionId',
        header: 'Collection ID',
        cell: (collection) => collection.collectionId,
        sortingField: 'collectionId',
        visible: false,
    },
    {
        id: 'repositoryId',
        header: 'Repository',
        cell: (collection) => (
            <Link href={`#/document-library/${collection.repositoryId}`}>
                {collection.repositoryId}
            </Link>
        ),
        sortingField: 'repositoryId',
        visible: true,
    },
    {
        id: 'description',
        header: 'Description',
        cell: (collection) => collection.description || '-',
        sortingField: 'description',
        visible: true,
    },
    {
        id: 'embeddingModel',
        header: 'Embedding Model',
        cell: (collection) => collection.embeddingModel || '-',
        visible: true,
        sortingField: 'embeddingModel',
    },
    {
        id: 'status',
        header: 'Status',
        cell: (collection) => getStatusIndicator(collection.status),
        visible: true,
        sortingField: 'status',
    },
    {
        id: 'allowedGroups',
        header: 'Allowed Groups',
        cell: (collection) => {
            if (!collection.allowedGroups || collection.allowedGroups.length === 0) {
                return <em>(public)</em>;
            }
            return collection.allowedGroups.join(', ');
        },
        visible: false,
    },
    {
        id: 'createdBy',
        header: 'Created By',
        cell: (collection) => collection.createdBy,
        visible: true,
        sortingField: 'createdBy',
    },
    {
        id: 'createdAt',
        header: 'Created At',
        cell: (collection) => formatDate(collection.createdAt),
        visible: false,
    },
    {
        id: 'updatedAt',
        header: 'Updated At',
        cell: (collection) => formatDate(collection.updatedAt),
        visible: false,
    },
    {
        id: 'chunkingStrategy',
        header: 'Chunking Strategy',
        cell: (collection) => formatObject(collection.chunkingStrategy),
        visible: false,
    },
    {
        id: 'metadata',
        header: 'Metadata',
        cell: (collection) => formatObject(collection.metadata),
        visible: false,
    }
];

function getStatusIndicator (status: CollectionStatus): ReactNode {
    let type: StatusIndicatorProps.Type;
    switch (status) {
        case 'ACTIVE':
            type = 'success';
            break;
        case 'DELETE_IN_PROGRESS':
            type = 'pending';
            break;
        case 'ARCHIVED':
        case 'DELETED':
            type = 'stopped';
            break;
        case 'DELETE_FAILED':
            type = 'error';
            break;
    }
    return <StatusIndicator type={type}>{status}</StatusIndicator>;
}

export function getCollectionTablePreference (): ReadonlyArray<CollectionPreferencesProps.ContentDisplayOption> {
    return COLLECTION_COLUMN_DEFINITIONS.map((c) => ({
        id: c.id!,
        label: c.header,
    }));
}

export function getCollectionTableColumnDisplay (): CollectionPreferencesProps.ContentDisplayItem[] {
    return COLLECTION_COLUMN_DEFINITIONS.map((c) => ({
        id: c.id!,
        visible: c.visible,
    }));
}

export function getDefaultCollectionPreferences (): CollectionPreferencesProps.Preferences {
    return {
        pageSize: PAGE_SIZE_OPTIONS[0].value,
        contentDisplay: getCollectionTableColumnDisplay(),
    };
}

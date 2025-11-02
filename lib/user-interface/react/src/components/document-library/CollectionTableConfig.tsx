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
import { DEFAULT_PAGE_SIZE_OPTIONS } from '../../shared/preferences/common-preferences';
import Badge from '@cloudscape-design/components/badge';
import { ReactNode } from 'react';
import { RagCollectionConfig } from '../../shared/reducers/rag.reducer';

export const PAGE_SIZE_OPTIONS = DEFAULT_PAGE_SIZE_OPTIONS('Collections');

export type CollectionTableRow = TableProps.ColumnDefinition<RagCollectionConfig> & {
    visible: boolean;
    header: string;
};

export const COLLECTION_COLUMN_DEFINITIONS: ReadonlyArray<CollectionTableRow> = [
    {
        id: 'name',
        header: 'Collection Name',
        cell: (collection) => collection.name || collection.collectionId,
        sortingField: 'name',
        visible: true,
        isRowHeader: true,
    },
    {
        id: 'collectionId',
        header: 'Collection ID',
        cell: (collection) => collection.collectionId,
        sortingField: 'collectionId',
        visible: true,
    },
    {
        id: 'repositoryId',
        header: 'Repository',
        cell: (collection) => collection.repositoryId,
        sortingField: 'repositoryId',
        visible: true,
    },
    {
        id: 'embeddingModel',
        header: 'Embedding Model',
        cell: (collection) => collection.embeddingModel || '-',
        visible: true,
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
        visible: true,
    },
    {
        id: 'status',
        header: 'Status',
        cell: (collection) => getStatusBadge(collection.status),
        visible: true,
    },
];

function getStatusBadge(status: 'ACTIVE' | 'ARCHIVED' | 'DELETED'): ReactNode {
    let color: 'green' | 'grey' | 'red' = 'grey';
    switch (status) {
        case 'ACTIVE':
            color = 'green';
            break;
        case 'ARCHIVED':
            color = 'grey';
            break;
        case 'DELETED':
            color = 'red';
            break;
    }
    return <Badge color={color}>{status}</Badge>;
}

export function getCollectionTablePreference(): ReadonlyArray<CollectionPreferencesProps.ContentDisplayOption> {
    return COLLECTION_COLUMN_DEFINITIONS.map((c) => ({
        id: c.id!,
        label: c.header,
    }));
}

export function getCollectionTableColumnDisplay(): CollectionPreferencesProps.ContentDisplayItem[] {
    return COLLECTION_COLUMN_DEFINITIONS.map((c) => ({
        id: c.id!,
        visible: c.visible,
    }));
}

export function getDefaultCollectionPreferences(): CollectionPreferencesProps.Preferences {
    return {
        pageSize: PAGE_SIZE_OPTIONS[0].value,
        contentDisplay: getCollectionTableColumnDisplay(),
    };
}

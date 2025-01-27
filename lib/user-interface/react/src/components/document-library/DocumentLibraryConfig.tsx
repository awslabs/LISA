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
import Link from '@cloudscape-design/components/link';
import { RagDocument, Repository } from '../types';
import { PropertyFilterOperator } from '@cloudscape-design/collection-hooks';
import { formatDate, formatObject } from '../../shared/util/formats';
import { ContentDisplayItem } from '@cloudscape-design/components/collection-preferences/interfaces';

export const stringOperators: PropertyFilterOperator[] = [':', '!:', '=', '!='];

export const CARD_DEFINITIONS = {
    header: (repo: Repository) => <Link
        // href={`${getBaseURI()}#/library/${repo.repositoryId}`}
        href={`/#/library/${repo.repositoryId}`}
        fontSize='heading-m'>{repo.repositoryId}</Link>,
    sections: [
        {
            id: 'repositoryName',
            header: 'Name',
            content: (repo: Repository) => repo.repositoryName,
        },
        {
            id: 'repoType',
            header: 'Type',
            content: (repo: Repository) => repo.type.toString(),
        },
        {
            id: 'allowedGroups',
            header: 'Allowed Groups',
            content: (repo: Repository) => `[${repo.allowedGroups.join(', ')}]`,
        },
    ],
};

export const PAGE_SIZE_OPTIONS = [
    { value: 6, label: '6 Documents' },
    { value: 12, label: '12 Documents' },
    { value: 24, label: '24 Documents' },
    { value: 48, label: '48 Documents' },
];

export const DEFAULT_PREFERENCES = {
    pageSize: 12,
    visibleContent: ['repositoryName', 'repoType', 'allowedGroups'],
};

export const VISIBLE_CONTENT_OPTIONS = [
    {
        label: 'Displayed Properties',
        options: [
            { id: 'repositoryName', label: 'Name' },
            { id: 'repoType', label: 'Type' },
            { id: 'allowedGroups', label: 'Allowed Groups' },
        ],
    },
];

export const TABLE_DEFINITION: {
    id: string,
    header: string,
    cell: (e: RagDocument) => string,
    sortingField?: string,
    isRowHeader?: boolean,
    visible: boolean
}[] = [
    { id: 'document_name', header: 'Name', cell: (e) => e.document_name, sortingField: 'document_name', visible: true },
    {
        id: 'document_id',
        header: 'Document ID',
        cell: (e) => e.document_id,
        sortingField: 'document_id',
        isRowHeader: true,
        visible: true,
    },
    {
        id: 'collection_id',
        header: 'Collection ID',
        cell: (e) => e.collection_id,
        sortingField: 'collection_id',
        visible: true,
    },
    { id: 'repository_id', header: 'Repository ID', cell: (e) => e.repository_id, visible: false },
    { id: 'source', header: 'Source', cell: (e) => e.source, visible: true },
    { id: 'username', header: 'Username', cell: (e) => e.username, sortingField: 'username', visible: true },
    {
        id: 'ingestion_type',
        header: 'Ingestion',
        cell: (e) => e.ingestion_type,
        sortingField: 'ingestion_type',
        visible: true,
    },
    { id: 'upload_date', header: 'Upload Date', cell: (e) => formatDate(e.upload_date), visible: true },
    { id: 'chunks', header: 'Document Chunks', cell: (e) => String(e.chunks), visible: true },
    { id: 'chunk_strategy', header: 'Chunk Strategy', cell: (e) => formatObject(e.chunk_strategy), visible: true },
];

export const TABLE_PREFERENCES = (() => TABLE_DEFINITION.map((c) => ({ id: c.id, label: c.header })))();

export const TABLE_COLUMN_DISPLAY: ContentDisplayItem[] = (() => TABLE_DEFINITION.map((c) => ({
    id: c.id,
    visible: c.visible,
})))();

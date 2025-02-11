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
import { CollectionPreferencesProps } from '@cloudscape-design/components';
import { DEFAULT_PAGE_SIZE_OPTIONS } from '../../shared/preferences/common-preferences';
import { RagRepositoryConfig } from '../../../../../configSchema';

export const PAGE_SIZE_OPTIONS = DEFAULT_PAGE_SIZE_OPTIONS('Repositories');

export const TABLE_DEFINITION: {
    id: string,
    header: string,
    cell: (e: RagRepositoryConfig) => string,
    sortingField?: string,
    isRowHeader?: boolean,
    visible: boolean
}[] = [
    {
        id: 'repositoryName',
        header: 'Name',
        cell: (e) => e.repositoryName,
        sortingField: 'repositoryName',
        visible: true,
    },
    {
        id: 'repositoryId',
        header: 'Repository ID',
        cell: (e) => e.repositoryId,
        sortingField: 'repositoryId',
        isRowHeader: true,
        visible: true,
    },
    {
        id: 'type',
        header: 'Type',
        cell: (e) => e.type,
        sortingField: 'type',
        visible: true,
    },
    { id: 'allowedGroups', header: 'Allowed Groups', cell: (e) => `[${e.allowedGroups.join(', ')}]`, visible: true },
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

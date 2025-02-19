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
import { UseQueryHookResult } from '@reduxjs/toolkit/dist/query/react/buildHooks';
import Spinner from '@cloudscape-design/components/spinner';
import StatusIndicator from '@cloudscape-design/components/status-indicator';
import { ReactNode } from 'react';
import ContentDisplayOption = CollectionPreferencesProps.ContentDisplayOption;

export const PAGE_SIZE_OPTIONS = DEFAULT_PAGE_SIZE_OPTIONS('Repositories');

export type TableRow = TableProps.ColumnDefinition<any> & {
    visible: boolean,
    header: string
};

export type TablePref = { id: string, label: ReactNode };

export function getTableDefinition ({
    data: ragStatus,
    isFetching,
}: UseQueryHookResult<any>): ReadonlyArray<TableRow> {
    return [
        {
            id: 'repositoryName',
            header: 'Name',
            cell: (e) => e.repositoryName?.length > 0 ? e.repositoryName : e.repositoryId,
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
        {
            id: 'allowedGroups',
            header: 'Allowed Groups',
            cell: (e) => e?.allowedGroups?.length > 0 ? `[${e.allowedGroups.join(', ')}]` : 'GLOBAL',
            visible: true,
        },
        {
            id: 'status',
            header: 'Status',
            cell: (e) => isFetching ? <Spinner /> : getStatusIcon(ragStatus?.[e.repositoryId]),
            visible: true,
        },
    ];
}

function getStatusIcon (status: string): ReactNode {
    let type: 'success' | 'error' | 'warning' | 'in-progress' = 'warning';
    switch (status) {
        case 'CREATE_COMPLETE':
        case 'UPDATE_COMPLETE':
        case 'DELETE_COMPLETE':
            type = 'success';
            break;
        case 'CREATE_FAILED':
        case 'DELETE_FAILED':
            type = 'error';
            break;
        case 'CREATE_IN_PROGRESS':
        case 'DELETE_IN_PROGRESS':
            type = 'in-progress';
            break;
    }
    return <StatusIndicator type={type}>{status}</StatusIndicator>;
}

export function getTablePreference (tableDefinition: ReadonlyArray<TableRow>): ReadonlyArray<ContentDisplayOption> {
    return tableDefinition.map((c) => ({
        id: c.id,
        label: c.header,
    }));
}

export function getTableColumnDisplay (tableDefinition: ReadonlyArray<TableRow>): CollectionPreferencesProps.ContentDisplayItem[] {
    return tableDefinition.map((c) => ({
        id: c.id,
        visible: c.visible,
    }));
}

export function getDefaultPreferences (tableDefinition: ReadonlyArray<TableRow>): CollectionPreferencesProps.Preferences {
    return {
        pageSize: PAGE_SIZE_OPTIONS[0].value,
        contentDisplay: getTableColumnDisplay(tableDefinition),
    };
}

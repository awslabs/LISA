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

import { CollectionPreferencesProps, StatusIndicator, TableProps } from '@cloudscape-design/components';
import { DEFAULT_PAGE_SIZE_OPTIONS } from '../../shared/preferences/common-preferences';
import { HostedMcpServer, HostedMcpServerStatus } from '@/shared/reducers/mcp-server.reducer';
import { formatDate } from '@/shared/util/formats';

export type TableRow = TableProps.ColumnDefinition<HostedMcpServer> & {
    visible: boolean;
    header: string;
};

export const PAGE_SIZE_OPTIONS = DEFAULT_PAGE_SIZE_OPTIONS('MCP servers');

const statusToIndicatorType: Record<HostedMcpServerStatus, 'success' | 'in-progress' | 'error' | 'stopped'> = {
    [HostedMcpServerStatus.Creating]: 'in-progress',
    [HostedMcpServerStatus.InService]: 'success',
    [HostedMcpServerStatus.Starting]: 'in-progress',
    [HostedMcpServerStatus.Stopping]: 'in-progress',
    [HostedMcpServerStatus.Stopped]: 'stopped',
    [HostedMcpServerStatus.Updating]: 'in-progress',
    [HostedMcpServerStatus.Deleting]: 'in-progress',
    [HostedMcpServerStatus.Failed]: 'error',
};

const mapStatusToIndicator = (status?: HostedMcpServerStatus) => {
    if (!status) {
        return <StatusIndicator type='stopped'>Unknown</StatusIndicator>;
    }

    const indicatorType = statusToIndicatorType[status] ?? 'in-progress';
    return <StatusIndicator type={indicatorType}>{status}</StatusIndicator>;
};

export function getTableDefinition (): ReadonlyArray<TableRow> {
    return [
        {
            id: 'name',
            header: 'Name',
            cell: (item) => item.name,
            sortingField: 'name',
            isRowHeader: true,
            visible: true,
        },
        {
            id: 'status',
            header: 'Status',
            cell: (item) => mapStatusToIndicator(item.status),
            sortingField: 'status',
            visible: true,
        },
        {
            id: 'serverType',
            header: 'Server type',
            cell: (item) => item.serverType?.toUpperCase(),
            sortingField: 'serverType',
            visible: true,
        },
        {
            id: 'owner',
            header: 'Owner',
            cell: (item) => item.owner === 'lisa:public' ? <em>(public)</em> : item.owner,
            sortingField: 'owner',
            visible: true,
        },
        {
            id: 'cpu',
            header: 'CPU (units)',
            cell: (item) => item.cpu ?? 256,
            sortingField: 'cpu',
            visible: true,
        },
        {
            id: 'memory',
            header: 'Memory (MiB)',
            cell: (item) => item.memoryLimitMiB ?? 512,
            sortingField: 'memoryLimitMiB',
            visible: true,
        },
        {
            id: 'scaling',
            header: 'Scaling (min / max)',
            cell: (item) => `${item.autoScalingConfig?.minCapacity ?? '-'} / ${item.autoScalingConfig?.maxCapacity ?? '-'}`,
            sortingField: 'autoScalingConfig.minCapacity',
            visible: true,
        },
        {
            id: 'created',
            header: 'Created',
            cell: (item) => formatDate(item.created),
            sortingField: 'created',
            visible: true,
        },
        {
            id: 'image',
            header: 'Image',
            cell: (item) => item.image ?? '-',
            sortingField: 'image',
            visible: false,
        },
        {
            id: 's3Path',
            header: 'S3 path',
            cell: (item) => item.s3Path ?? '-',
            sortingField: 's3Path',
            visible: false,
        },
        {
            id: 'startCommand',
            header: 'Start command',
            cell: (item) => <code style={{ wordBreak: 'break-word' }}>{item.startCommand}</code>,
            sortingField: 'startCommand',
            visible: false,
        },
        {
            id: 'groups',
            header: 'Groups',
            cell: (item) => item.groups?.length ? item.groups.join(', ') : '-',
            sortingField: 'groups',
            visible: false,
        },
    ];
}

export function getTablePreference (tableDefinition: ReadonlyArray<TableRow>): ReadonlyArray<CollectionPreferencesProps.ContentDisplayOption> {
    return tableDefinition.map((column) => ({
        id: column.id,
        label: column.header,
    }));
}

export function getTableColumnDisplay (tableDefinition: ReadonlyArray<TableRow>): CollectionPreferencesProps.ContentDisplayItem[] {
    return tableDefinition.map((column) => ({
        id: column.id,
        visible: column.visible,
    }));
}

export function getDefaultPreferences (tableDefinition: ReadonlyArray<TableRow>): CollectionPreferencesProps.Preferences {
    return {
        pageSize: PAGE_SIZE_OPTIONS[0].value,
        contentDisplay: getTableColumnDisplay(tableDefinition),
    };
}

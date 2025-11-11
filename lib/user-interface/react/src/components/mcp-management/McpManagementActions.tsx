/**
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License").
 * You may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import { ReactElement, useEffect } from 'react';
import { Button, ButtonDropdown, Icon, SpaceBetween } from '@cloudscape-design/components';
import { useAppDispatch } from '@/config/store';
import {
    HostedMcpServer,
    HostedMcpServerStatus,
    useDeleteHostedMcpServerMutation,
} from '@/shared/reducers/mcp-server.reducer';
import { useNotificationService } from '@/shared/util/hooks';
import { setConfirmationModal } from '@/shared/reducers/modal.reducer';

type McpManagementActionsProps = {
    selectedItems: HostedMcpServer[];
    setSelectedItems: (items: HostedMcpServer[]) => void;
    onCreate: () => void;
    refetch: () => void;
};

const DELETABLE_STATUSES = new Set<HostedMcpServerStatus | undefined>([
    HostedMcpServerStatus.InService,
    HostedMcpServerStatus.Stopped,
    HostedMcpServerStatus.Failed,
]);

export function McpManagementActions ({ selectedItems, setSelectedItems, refetch, onCreate }: McpManagementActionsProps): ReactElement {
    const dispatch = useAppDispatch();
    const notificationService = useNotificationService(dispatch);

    const selectedServer = selectedItems?.[0];

    const [
        deleteHostedServer,
        { isLoading: isDeleting, isSuccess: isDeleteSuccess, isError: isDeleteError, error: deleteError }
    ] = useDeleteHostedMcpServerMutation();

    useEffect(() => {
        if (!isDeleting && isDeleteSuccess && selectedServer) {
            notificationService.generateNotification(`Deleted MCP server ${selectedServer.name}`, 'success');
            setSelectedItems([]);
        } else if (!isDeleting && isDeleteError) {
            const message = deleteError && 'data' in deleteError
                ? deleteError.data?.message ?? deleteError.data
                : 'Unknown error deleting MCP server';
            notificationService.generateNotification(`Failed to delete MCP server: ${message}`, 'error');
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isDeleting, isDeleteSuccess, isDeleteError, deleteError]);

    const items = [
        {
            id: 'delete',
            text: 'Delete',
            disabled: !selectedServer || !DELETABLE_STATUSES.has(selectedServer?.status),
            disabledReason: !selectedServer
                ? 'Select an MCP server to delete'
                : 'Server must be InService, Stopped, or Failed to delete',
        },
        {
            id: 'start',
            text: 'Start',
            disabled: true,
            disabledReason: 'Start is not yet available',
        },
        {
            id: 'stop',
            text: 'Stop',
            disabled: true,
            disabledReason: 'Stop is not yet available',
        },
        {
            id: 'update',
            text: 'Update',
            disabled: true,
            disabledReason: 'Update is not yet available',
        },
    ];

    return (
        <SpaceBetween direction='horizontal' size='xs'>
            <Button
                ariaLabel='Refresh MCP servers'
                onClick={() => {
                    setSelectedItems([]);
                    refetch();
                }}
            >
                <Icon name='refresh' />
            </Button>
            <ButtonDropdown
                items={items}
                disabled={items.every((item) => item.disabled)}
                onItemClick={({ detail }) => {
                    if (detail.id === 'delete' && selectedServer) {
                        dispatch(setConfirmationModal({
                            action: 'Delete',
                            resourceName: 'MCP server',
                            onConfirm: () => deleteHostedServer(selectedServer.id),
                            description: `This will delete the hosted MCP server "${selectedServer.name}".`,
                        }));
                    }
                }}
                loading={isDeleting}
            >
                Actions
            </ButtonDropdown>
            <Button variant='primary' onClick={onCreate}>
                Create MCP server
            </Button>
        </SpaceBetween>
    );
}


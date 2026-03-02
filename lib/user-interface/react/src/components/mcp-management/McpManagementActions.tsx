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

import { ReactElement, useEffect } from 'react';
import { Button, ButtonDropdown, SpaceBetween } from '@cloudscape-design/components';
import { RefreshButton } from '@/components/common/RefreshButton';
import { useAppDispatch } from '@/config/store';
import {
    HostedMcpServer,
    HostedMcpServerStatus,
    useDeleteHostedMcpServerMutation,
    useUpdateHostedMcpServerMutation,
} from '@/shared/reducers/mcp-server.reducer';
import { useNotificationService } from '@/shared/util/hooks';
import { setConfirmationModal } from '@/shared/reducers/modal.reducer';

type McpManagementActionsProps = {
    selectedItems: HostedMcpServer[];
    setSelectedItems: (items: HostedMcpServer[]) => void;
    onCreate: () => void;
    onEdit: (server: HostedMcpServer) => void;
    refetch: () => void;
    isFetching: boolean;
};

const DELETABLE_STATUSES = new Set<HostedMcpServerStatus | undefined>([
    HostedMcpServerStatus.InService,
    HostedMcpServerStatus.Stopped,
    HostedMcpServerStatus.Failed,
]);

export function McpManagementActions ({ selectedItems, setSelectedItems, refetch, onCreate, onEdit, isFetching }: McpManagementActionsProps): ReactElement {
    const dispatch = useAppDispatch();
    const notificationService = useNotificationService(dispatch);

    const selectedServer = selectedItems?.[0];

    const [
        deleteHostedServer,
        { isLoading: isDeleting, isSuccess: isDeleteSuccess, isError: isDeleteError, error: deleteError }
    ] = useDeleteHostedMcpServerMutation();

    const [
        updateHostedServer,
        { isLoading: isUpdating, isSuccess: isUpdateSuccess, isError: isUpdateError, error: updateError }
    ] = useUpdateHostedMcpServerMutation();

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

    useEffect(() => {
        if (!isUpdating && isUpdateSuccess && selectedServer) {
            notificationService.generateNotification(`Updated MCP server ${selectedServer.name}`, 'success');
            refetch();
        } else if (!isUpdating && isUpdateError) {
            const message = updateError && 'data' in updateError
                ? updateError.data?.message ?? updateError.data
                : 'Unknown error updating MCP server';
            notificationService.generateNotification(`Failed to update MCP server: ${message}`, 'error');
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isUpdating, isUpdateSuccess, isUpdateError, updateError]);

    const canStart = selectedServer?.status === HostedMcpServerStatus.Stopped;
    const canStop = selectedServer?.status === HostedMcpServerStatus.InService;
    const canUpdate = selectedServer?.status === HostedMcpServerStatus.InService || selectedServer?.status === HostedMcpServerStatus.Stopped;

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
            disabled: !canStart,
            disabledReason: !selectedServer
                ? 'Select an MCP server to start'
                : 'Server must be Stopped to start',
        },
        {
            id: 'stop',
            text: 'Stop',
            disabled: !canStop,
            disabledReason: !selectedServer
                ? 'Select an MCP server to stop'
                : 'Server must be InService to stop',
        },
        {
            id: 'update',
            text: 'Update',
            disabled: !canUpdate,
            disabledReason: !selectedServer
                ? 'Select an MCP server to update'
                : 'Server must be InService or Stopped to update',
        },
    ];

    return (
        <>
            <SpaceBetween direction='horizontal' size='xs'>
                <RefreshButton
                    isLoading={isFetching}
                    onClick={() => {
                        setSelectedItems([]);
                        refetch();
                    }}
                    ariaLabel='Refresh MCP servers'
                />
                <ButtonDropdown
                    items={items}
                    disabled={items.every((item) => item.disabled)}
                    onItemClick={({ detail }) => {
                        if (!selectedServer) return;

                        if (detail.id === 'delete') {
                            dispatch(setConfirmationModal({
                                action: 'Delete',
                                resourceName: 'MCP server',
                                onConfirm: () => deleteHostedServer(selectedServer.id),
                                description: `This will delete the hosted MCP server "${selectedServer.name}".`,
                            }));
                        } else if (detail.id === 'start') {
                            dispatch(setConfirmationModal({
                                action: 'Start',
                                resourceName: 'MCP server',
                                onConfirm: () => updateHostedServer({ serverId: selectedServer.id, payload: { enabled: true } }),
                                description: `This will start the hosted MCP server "${selectedServer.name}".`,
                            }));
                        } else if (detail.id === 'stop') {
                            dispatch(setConfirmationModal({
                                action: 'Stop',
                                resourceName: 'MCP server',
                                onConfirm: () => updateHostedServer({ serverId: selectedServer.id, payload: { enabled: false } }),
                                description: `This will stop the hosted MCP server "${selectedServer.name}".`,
                            }));
                        } else if (detail.id === 'update') {
                            onEdit(selectedServer);
                        }
                    }}
                    loading={isDeleting || isUpdating}
                >
                    Actions
                </ButtonDropdown>
                <Button variant='primary' onClick={onCreate}>
                    Create MCP Server
                </Button>
            </SpaceBetween>
        </>
    );
}

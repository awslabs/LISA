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

import React, { ReactElement, useEffect } from 'react';
import { Button, ButtonDropdown, SpaceBetween } from '@cloudscape-design/components';
import { useAppDispatch, useAppSelector } from '../../config/store';
import { useNotificationService } from '../../shared/util/hooks';
import { INotificationService } from '../../shared/notification/notification.service';
import { MutationTrigger } from '@reduxjs/toolkit/dist/query/react/buildHooks';
import { Action, ThunkDispatch } from '@reduxjs/toolkit';
import { setConfirmationModal } from '../../shared/reducers/modal.reducer';
import { NavigateFunction, useNavigate } from 'react-router-dom';
import { selectCurrentUserIsAdmin, selectCurrentUsername } from '../../shared/reducers/user.reducer';
import { McpServer, mcpServerApi, useDeleteMcpServerMutation, useListMcpServersQuery } from '@/shared/reducers/mcp-server.reducer';
import { McpPreferences } from '@/shared/reducers/user-preferences.reducer';
import { RefreshButton } from '@/components/common/RefreshButton';

export type McpServerActionsProps = {
    selectedItems: readonly McpServer[];
    setSelectedItems: (items: McpServer[]) => void;
    preferences: McpPreferences;
    toggleAutopilotMode: () => void;
};

export function McpServerActions (props: McpServerActionsProps): ReactElement {
    const dispatch = useAppDispatch();
    const notificationService = useNotificationService(dispatch);
    const navigate = useNavigate();
    const isUserAdmin = useAppSelector(selectCurrentUserIsAdmin);
    const username = useAppSelector(selectCurrentUsername);
    const preferences = props.preferences;
    const { isFetching } = useListMcpServersQuery();

    return (
        <SpaceBetween direction='horizontal' size='xs'>
            <RefreshButton
                isLoading={isFetching}
                onClick={() => {
                    props.setSelectedItems([]);
                    dispatch(mcpServerApi.util.invalidateTags(['mcpServers']));
                }}
                ariaLabel='Refresh MCP Connections'
            />
            {McpServerActionButton(dispatch, notificationService, props, {isUserAdmin, username, preferences})}
            <Button variant='primary' onClick={() => {
                navigate('./new');
            }}>
                Create MCP Connection
            </Button>
        </SpaceBetween>
    );
}

function McpServerActionButton (dispatch: ThunkDispatch<any, any, Action>, notificationService: INotificationService, props: McpServerActionsProps, user: {isUserAdmin: boolean, username: string, preferences: McpPreferences}): ReactElement {
    const selectedMcpServer: McpServer = props?.selectedItems[0];
    const navigate = useNavigate();
    const [
        deleteMutation,
        { isSuccess: isDeleteSuccess, isError: isDeleteError, error: deleteError, isLoading: isDeleteLoading },
    ] = useDeleteMcpServerMutation();

    useEffect(() => {
        if (!isDeleteLoading && isDeleteSuccess && selectedMcpServer) {
            notificationService.generateNotification(`Successfully deleted MCP Connection: ${selectedMcpServer.name}`, 'success');
            props.setSelectedItems([]);
        } else if (!isDeleteLoading && isDeleteError && selectedMcpServer) {
            notificationService.generateNotification(`Error deleting MCP Connection: ${deleteError.data?.message ?? deleteError.data}`, 'error');
            props.setSelectedItems([]);
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isDeleteSuccess, isDeleteError, deleteError, isDeleteLoading]);

    const items = [];
    if (selectedMcpServer) {
        items.push({
            text: 'Edit',
            id: 'editMcpServer',
            disabled: !user.isUserAdmin && !(selectedMcpServer.owner === user.username),
            disabledReason: 'You cannot edit a MCP Connection you don\'t own.',
        });

        items.push({
            text: 'Delete',
            id: 'deleteMcpServer',
            disabled: !user.isUserAdmin && !(selectedMcpServer.owner === user.username),
            disabledReason: 'You cannot delete a MCP Connection you don\'t own.',
        });
    }

    items.push({
        text: `${user.preferences?.overrideAllApprovals === true ? 'Activate Safe Mode' : 'Activate Autopilot Mode'}`,
        id: 'toggleAutopilotMode',
    });

    return (
        <ButtonDropdown
            items={items}
            variant='primary'
            disabled={!items}
            loading={isDeleteLoading}
            onItemClick={(e) =>
                ModelActionHandler(e, selectedMcpServer, dispatch, deleteMutation, navigate, props.toggleAutopilotMode)
            }
        >
            Actions
        </ButtonDropdown>
    );
}

const ModelActionHandler = (
    e: any,
    selectedItem: McpServer,
    dispatch: ThunkDispatch<any, any, Action>,
    deleteMutation: MutationTrigger<any>,
    navigate: NavigateFunction,
    toggleAutopilotMode: () => void,
) => {
    switch (e.detail.id) {
        case 'editMcpServer':
            navigate(`./edit/${selectedItem.id}`);
            break;
        case 'deleteMcpServer':
            dispatch(
                setConfirmationModal({
                    action: 'Delete',
                    resourceName: 'MCP Connection',
                    onConfirm: () => deleteMutation(selectedItem.id),
                    description: `This will delete the following MCP Connection: ${selectedItem.name}.`
                })
            );
            break;
        case 'toggleAutopilotMode':
            toggleAutopilotMode();
            break;
        default:
            return;
    }
};

export default McpServerActions;

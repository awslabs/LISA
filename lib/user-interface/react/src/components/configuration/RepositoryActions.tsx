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
import { Button, ButtonDropdown, ButtonDropdownProps, Icon, SpaceBetween } from '@cloudscape-design/components';
import { useAppDispatch } from '../../config/store';
import { useNotificationService } from '../../shared/util/hooks';
import { INotificationService } from '../../shared/notification/notification.service';
import { MutationTrigger } from '@reduxjs/toolkit/dist/query/react/buildHooks';
import { Action, ThunkDispatch } from '@reduxjs/toolkit';
import { setConfirmationModal } from '../../shared/reducers/modal.reducer';
import {
    ragApi,
    useCreateRagRepositoryMutation,
    useDeleteRagRepositoryMutation,
} from '../../shared/reducers/rag.reducer';
import { RagRepositoryConfig } from '../../../../../configSchema';

export type RepositoryActionProps = {
    selectedItems: ReadonlyArray<RagRepositoryConfig>;
    setSelectedItems: (items: RagRepositoryConfig[]) => void;
    setNewRepositoryModalVisible: (state: boolean) => void;
    setEdit: (state: boolean) => void;
};

function RepositoryActions (props: RepositoryActionProps): ReactElement {
    const dispatch = useAppDispatch();
    const notificationService = useNotificationService(dispatch);
    const { setEdit, setNewRepositoryModalVisible, setSelectedItems } = props;
    return (
        <SpaceBetween direction='horizontal' size='xs'>
            {RepositoryActionButton(dispatch, notificationService, props)}
            <Button iconName='add-plus' variant='primary' onClick={() => {
                setEdit(false);
                setNewRepositoryModalVisible(true);
            }}>
                New Repository
            </Button>
            <Button
                onClick={() => {
                    setSelectedItems([]);
                    dispatch(ragApi.util.invalidateTags(['repositories', 'repository-status']));
                }}
                ariaLabel={'Refresh repository table'}
            >
                <Icon name='refresh' />
            </Button>
        </SpaceBetween>
    );
}

type RagRepository = RagRepositoryConfig & {
    editable?: boolean
};

function RepositoryActionButton (dispatch: ThunkDispatch<any, any, Action>, notificationService: INotificationService, props: RepositoryActionProps): ReactElement {
    const { setEdit, selectedItems, setSelectedItems, setNewRepositoryModalVisible } = props;

    const selectedRepo: RagRepository = selectedItems[0];
    const [
        deleteMutation,
        { isSuccess: isDeleteSuccess, isError: isDeleteError, error: deleteError, isLoading: isDeleteLoading },
    ] = useDeleteRagRepositoryMutation();

    const [, { isSuccess: isUpdateSuccess, isError: isUpdateError, error: updateError, isLoading: isUpdating }]
        = useCreateRagRepositoryMutation();

    useEffect(() => {
        if (!isDeleteLoading && isDeleteSuccess && selectedRepo) {
            notificationService.generateNotification(`Successfully deleted repository: ${selectedRepo.repositoryId}`, 'success');
            setSelectedItems([]);
        } else if (!isDeleteLoading && isDeleteError && selectedRepo) {
            notificationService.generateNotification(`Error deleting repository: ${deleteError.data?.message ?? deleteError.data}`, 'error');
            setSelectedItems([]);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isDeleteSuccess, isDeleteError, deleteError, isDeleteLoading]);

    useEffect(() => {
        if (!isUpdating && isUpdateSuccess && selectedRepo) {
            notificationService.generateNotification(`Successfully updated repository: ${selectedRepo.repositoryId}`, 'success');
            setSelectedItems([]);
        } else if (!isUpdating && isUpdateError && selectedRepo) {
            notificationService.generateNotification(`Error updating repository: ${updateError.data?.message ?? updateError.data}`, 'error');
            setSelectedItems([]);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isUpdateSuccess, isUpdateError, updateError, isUpdating]);

    const items: ButtonDropdownProps.Item[] = [
        {
            id: 'edit',
            text: 'Edit',
            disabled: selectedItems.length !== 1 || !selectedRepo?.editable,
            disabledReason: selectedItems.length !== 1 ? '' : !selectedRepo?.editable ? 'Legacy repositories created through YAML cannot be edited.' : undefined
        },
        {
            id: 'rm',
            text: 'Delete',
            disabled: selectedItems.length !== 1,
        }];

    return (
        <ButtonDropdown
            items={items}
            variant='primary'
            disabled={!selectedRepo}
            loading={isDeleteLoading || isUpdating}
            onItemClick={(e) =>
                RepositoryActionHandler(e, selectedRepo, dispatch, deleteMutation, setNewRepositoryModalVisible, setEdit)
            }
        >
            Actions
        </ButtonDropdown>
    );
}

const RepositoryActionHandler = async (
    e: any,
    selectedRepo: RagRepositoryConfig,
    dispatch: ThunkDispatch<any, any, Action>,
    deleteMutation: MutationTrigger<any>,
    setNewRepositoryModalVisible: (boolean) => void,
    setEdit: (boolean) => void,
) => {
    switch (e.detail.id) {
        case 'edit':
            setEdit(true);
            setNewRepositoryModalVisible(true);
            break;
        case 'rm':
            dispatch(
                setConfirmationModal({
                    action: 'Delete',
                    resourceName: 'Repository',
                    onConfirm: () => deleteMutation(selectedRepo.repositoryId),
                    description: `This will delete the following repository: ${selectedRepo.repositoryId}.`,
                }),
            );
            break;
        default:
            return;
    }
};

export { RepositoryActions };

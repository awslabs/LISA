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

import { ReactElement, useEffect, useState } from 'react';
import {
    Alert,
    Button,
    ButtonDropdown,
    ButtonDropdownProps,
    Checkbox,
    Icon,
    SpaceBetween,
} from '@cloudscape-design/components';
import { useAppDispatch } from '@/config/store';
import { useNotificationService } from '@/shared/util/hooks';
import { INotificationService } from '@/shared/notification/notification.service';
import { Action, ThunkDispatch } from '@reduxjs/toolkit';
import { setConfirmationModal } from '@/shared/reducers/modal.reducer';
import {
    ragApi,
    useUpdateRagRepositoryMutation,
    useDeleteRagRepositoryMutation,
} from '@/shared/reducers/rag.reducer';
import { RagRepositoryConfig } from '#root/lib/schema';

export type RepositoryActionProps = {
    selectedItems: ReadonlyArray<RagRepositoryConfig>;
    setSelectedItems: (items: RagRepositoryConfig[]) => void;
    setNewRepositoryModalVisible: (state: boolean) => void;
    setEdit: (state: boolean) => void;
    refetchRepositories: () => void;
};

function RepositoryActions (props: RepositoryActionProps): ReactElement {
    const dispatch = useAppDispatch();
    const notificationService = useNotificationService(dispatch);
    const { setEdit, setNewRepositoryModalVisible, setSelectedItems, refetchRepositories } = props;
    return (
        <SpaceBetween direction='horizontal' size='xs'>
            <Button
                onClick={async () => {
                    setSelectedItems([]);
                    // Invalidate cache and trigger refetch
                    dispatch(ragApi.util.invalidateTags(['repositories']));
                    await refetchRepositories();
                }}
                ariaLabel={'Refresh repository table'}
            >
                <Icon name='refresh' />
            </Button>
            {RepositoryActionButton(dispatch, notificationService, props)}
            <Button variant='primary' onClick={() => {
                setEdit(false);
                setNewRepositoryModalVisible(true);
            }}>
                Create Repository
            </Button>
        </SpaceBetween>
    );
}

type RagRepository = RagRepositoryConfig & {
    legacy?: boolean
};

function RepositoryActionButton (dispatch: ThunkDispatch<any, any, Action>, notificationService: INotificationService, props: RepositoryActionProps): ReactElement {
    const { setEdit, selectedItems, setSelectedItems, setNewRepositoryModalVisible } = props;
    const [disabledModal, setDisabledModel] = useState(false);
    const [showModal, setShowModal] = useState(false);
    const selectedRepo: RagRepository = selectedItems[0];
    const [
        deleteMutation,
        { isSuccess: isDeleteSuccess, isError: isDeleteError, error: deleteError, isLoading: isDeleteLoading },
    ] = useDeleteRagRepositoryMutation();

    const [, { isSuccess: isUpdateSuccess, isError: isUpdateError, error: updateError, isLoading: isUpdating }]
        = useUpdateRagRepositoryMutation();

    useEffect(() => {
        if (!isDeleteLoading && isDeleteSuccess && selectedRepo) {
            notificationService.generateNotification(`Successfully deleted repository: ${selectedRepo?.repositoryId}`, 'success');
            setSelectedItems([]);
            setDisabledModel(false);
            setShowModal(false);
        } else if (!isDeleteLoading && isDeleteError && selectedRepo) {
            notificationService.generateNotification(`Error deleting repository: ${deleteError.data?.message ?? deleteError.data}`, 'error');
            setSelectedItems([]);
            setDisabledModel(false);
            setShowModal(false);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isDeleteSuccess, isDeleteError, deleteError, isDeleteLoading]);

    useEffect(() => {
        if (!isUpdating && isUpdateSuccess && selectedRepo) {
            notificationService.generateNotification(`Successfully updated repository: ${selectedRepo?.repositoryId}`, 'success');
            setSelectedItems([]);
        } else if (!isUpdating && isUpdateError && selectedRepo) {
            notificationService.generateNotification(`Error updating repository: ${updateError.data?.message ?? updateError.data}`, 'error');
            setSelectedItems([]);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isUpdateSuccess, isUpdateError, updateError, isUpdating]);

    useEffect(() => {
        if (showModal) {
            dispatch(setConfirmationModal({
                action: 'Delete',
                resourceName: 'Repository',
                onConfirm: () => deleteMutation(selectedRepo?.repositoryId),
                onDismiss: () => {
                    setDisabledModel(false);
                    setShowModal(false);
                },
                description: (
                    <SpaceBetween direction='vertical' size='s'>
                        <p key={'message'}>This will delete the following repository: {selectedRepo?.repositoryId}.</p>
                        {selectedRepo?.legacy &&
                            <Alert key={'alert'} type='warning'>
                                <Checkbox
                                    checked={disabledModal}
                                    onChange={({ detail }) => {
                                        setDisabledModel(detail.checked);
                                    }}>
                                    This is a legacy repository configured through YAML. Deleting it will only remove it from the UI, and you will need to redeploy the CDK to remove the associated AWS resources.
                                </Checkbox>
                            </Alert>
                        }
                    </SpaceBetween>
                ),
                disabled: selectedRepo?.legacy && !disabledModal
            }));
        }
    }, [showModal, selectedRepo, disabledModal, deleteMutation, dispatch]);

    const items: ButtonDropdownProps.Item[] = [
        {
            id: 'edit',
            text: 'Edit',
            disabled: selectedItems.length !== 1 || selectedRepo?.legacy,
            disabledReason: selectedItems.length !== 1 ? '' : selectedRepo?.legacy ? 'Legacy repositories created through YAML cannot be edited.' : undefined
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
                RepositoryActionHandler(e, setNewRepositoryModalVisible, setEdit, setShowModal)
            }
        >
            Actions
        </ButtonDropdown>
    );
}

const RepositoryActionHandler = (
    e: any,
    setNewRepositoryModalVisible: (boolean) => void,
    setEdit: (boolean) => void,
    setShowModal: (boolean) => void
) => {
    switch (e.detail.id) {
        case 'edit':
            setEdit(true);
            setNewRepositoryModalVisible(true);
            break;
        case 'rm':
            setShowModal(true);
            break;
        default:
            return;
    }
};

export { RepositoryActions };

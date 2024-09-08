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
import { Button, ButtonDropdown, Icon, SpaceBetween } from '@cloudscape-design/components';
import { useAppDispatch } from '../../config/store';
import { IModel } from '../../shared/model/model-management.model';
import { useNotificationService } from '../../shared/util/hooks';
import { INotificationService } from '../../shared/notification/notification.service';
import {
    modelManagementApi,
    useDeleteModelMutation,
    useStartModelMutation,
    useStopModelMutation,
} from '../../shared/reducers/model-management.reducer';
import { MutationTrigger } from '@reduxjs/toolkit/dist/query/react/buildHooks';
import { Action, ThunkDispatch } from '@reduxjs/toolkit';
import { setConfirmationModal } from '../../shared/reducers/modal.reducer';

export type ModelActionProps = {
    selectedItems: IModel[];
    setSelectedItems: (items: IModel[]) => void;
    setNewModelModelVisible: (boolean) => void;
    setEdit: (boolean) => void;
};

function ModelActions (props: ModelActionProps): ReactElement {
    const dispatch = useAppDispatch();
    const notificationService = useNotificationService(dispatch);

    return (
        <SpaceBetween direction='horizontal' size='xs'>
            {ModelActionButton(dispatch, notificationService, props)}
            <Button iconName='add-plus' variant='primary' onClick={() => {
                props.setEdit(false);
                props.setNewModelModelVisible(true);
            }}>
                New Model
            </Button>
            <Button
                onClick={() => dispatch(modelManagementApi.util.invalidateTags(['models']))}
                ariaLabel={'Refresh models cards'}
            >
                <Icon name='refresh' />
            </Button>
        </SpaceBetween>
    );
}

function ModelActionButton (dispatch: ThunkDispatch<any, any, Action>, notificationService: INotificationService, props?: any): ReactElement {
    const selectedModel: IModel = props?.selectedItems[0];
    const [
        deleteMutation,
        { isSuccess: isDeleteSuccess, isError: isDeleteError, error: deleteError, isLoading: isDeleteLoading },
    ] = useDeleteModelMutation();
    const [stopMutation, { isSuccess: isStopSuccess, isError: isStopError, error: stopError, isLoading: isStopLoading }] =
    useStopModelMutation();
    const [
        startMutation,
        { isSuccess: isStartSuccess, isError: isStartError, error: startError, isLoading: isStartLoading },
    ] = useStartModelMutation();

    useEffect(() => {
        if (!isDeleteLoading && isDeleteSuccess && selectedModel) {
            notificationService.generateNotification(`Successfully deleted model: ${selectedModel.modelId}`, 'success');
            props.setSelectedItems([]);
        } else if (!isDeleteLoading && isDeleteError && selectedModel) {
            notificationService.generateNotification(`Error deleting model: ${deleteError.data?.message ?? deleteError.data}`, 'error');
            props.setSelectedItems([]);
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isDeleteSuccess, isDeleteError, deleteError, isDeleteLoading]);

    useEffect(() => {
        if (!isStopLoading && isStopSuccess && selectedModel) {
            notificationService.generateNotification(`Successfully stopped model: ${selectedModel.modelId}`, 'success');
            props.setSelectedItems([]);
        } else if (!isStopLoading && isStopError && selectedModel) {
            notificationService.generateNotification(`Error stopping model: ${stopError.data?.message ?? stopError.data}`, 'error');
            props.setSelectedItems([]);
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isStopSuccess, isStopError, stopError, isStopLoading]);

    useEffect(() => {
        if (!isStartLoading && isStartSuccess && selectedModel) {
            notificationService.generateNotification(`Successfully started model: ${selectedModel.modelId}`, 'success');
            props.setSelectedItems([]);
        } else if (!isStartLoading && isStartError && selectedModel) {
            notificationService.generateNotification(`Error starting model: ${startError.data?.message ?? startError.data}`, 'error');
            props.setSelectedItems([]);
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isStartSuccess, isStartError, startError, isStartLoading]);

    const items = [];
    if (selectedModel) {
        items.push({
            text: 'Start',
            id: 'startModel',
        });
        items.push({
            text: 'Stop',
            id: 'stopModel',
        });
        items.push({
            text: 'Update',
            id: 'editModel',
        });
        items.push({
            text: 'Delete',
            id: 'deleteModel',
        });
    }

    return (
        <ButtonDropdown
            items={items}
            variant='primary'
            disabled={!selectedModel}
            loading={isDeleteLoading || isStopLoading || isStartLoading}
            onItemClick={(e) =>
                ModelActionHandler(e, selectedModel, dispatch, deleteMutation, stopMutation, startMutation, props.setNewModelModelVisible, props.setEdit)
            }
        >
            Actions
        </ButtonDropdown>
    );
}

const ModelActionHandler = async (
    e: any,
    selectedModel: IModel,
    dispatch: ThunkDispatch<any, any, Action>,
    deleteMutation: MutationTrigger<any>,
    stopMutation: MutationTrigger<any>,
    startMutation: MutationTrigger<any>,
    setNewModelModelVisible: (boolean) => void,
    setEdit: (boolean) => void
) => {
    switch (e.detail.id) {
        case 'startModel':
            dispatch(
                setConfirmationModal({
                    action: 'Start',
                    resourceName: 'Model',
                    onConfirm: () => startMutation(selectedModel.modelId),
                    description: `This will start the following model: ${selectedModel.modelId}.`
                })
            );
            break;
        case 'stopModel':
            dispatch(
                setConfirmationModal({
                    action: 'Stop',
                    resourceName: 'Model',
                    onConfirm: () => stopMutation(selectedModel.modelId),
                    description: `This will stop the following model: ${selectedModel.modelId}.`
                })
            );
            break;
        case 'editModel':
            setEdit(true);
            setNewModelModelVisible(true);
            break;
        case 'deleteModel':
            dispatch(
                setConfirmationModal({
                    action: 'Delete',
                    resourceName: 'Model',
                    onConfirm: () => deleteMutation(selectedModel.modelId),
                    description: `This will delete the following model: ${selectedModel.modelId}.`
                })
            );
            break;
        default:
            return;
    }
};

export { ModelActions };

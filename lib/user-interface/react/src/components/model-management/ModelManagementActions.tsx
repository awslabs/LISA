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
import { IModel, ModelStatus } from '../../shared/model/model-management.model';
import { useNotificationService } from '../../shared/util/hooks';
import { INotificationService } from '../../shared/notification/notification.service';
import {
    modelManagementApi,
    useDeleteModelMutation, useUpdateModelMutation,
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
                onClick={() => {
                    props.setSelectedItems([]);
                    dispatch(modelManagementApi.util.invalidateTags(['models']));
                }}
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

    const [
        updateModelMutation,
        { isSuccess: isUpdateSuccess, isError: isUpdateError, error: updateError, isLoading: isUpdating },
    ] = useUpdateModelMutation();

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
        if (!isUpdating && isUpdateSuccess && selectedModel) {
            notificationService.generateNotification(`Successfully updated model: ${selectedModel.modelId}`, 'success');
            props.setSelectedItems([]);
        } else if (!isUpdating && isUpdateError && selectedModel) {
            notificationService.generateNotification(`Error updating model: ${updateError.data?.message ?? updateError.data}`, 'error');
            props.setSelectedItems([]);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isUpdateSuccess, isUpdateError, updateError, isUpdating]);

    const items = [];
    if (selectedModel) {
        items.push({
            text: 'Delete',
            id: 'deleteModel',
            disabled: ![ModelStatus.InService, ModelStatus.Stopped, ModelStatus.Failed].includes(selectedModel.status),
            disabledReason: ![ModelStatus.InService, ModelStatus.Stopped, ModelStatus.Failed].includes(selectedModel.status) ? 'Unable to delete a model that is in a pending state' : '',
        });
        items.push({
            text: 'Start',
            id: 'startModel',
            disabled: (selectedModel.containerConfig === null && selectedModel.autoScalingConfig === null && selectedModel.loadBalancerConfig === null) || selectedModel.status !== ModelStatus.Stopped,
            disabledReason: selectedModel.containerConfig === null && selectedModel.autoScalingConfig === null && selectedModel.loadBalancerConfig === null ? 'Unable to start a model that is not hosted in LISA' : selectedModel.status !== ModelStatus.Stopped ? 'Unable to start a model that is not in Stopped state' : '',
        });
        items.push({
            text: 'Stop',
            id: 'stopModel',
            disabled: (selectedModel.containerConfig === null && selectedModel.autoScalingConfig === null && selectedModel.loadBalancerConfig === null) || selectedModel.status !== ModelStatus.InService,
            disabledReason: selectedModel.containerConfig === null && selectedModel.autoScalingConfig === null && selectedModel.loadBalancerConfig === null ? 'Unable to stop a model that is not hosted in LISA' : selectedModel.status !== ModelStatus.InService ? 'Unable to stop a model that is not in InService state' : '',
        });
        items.push({
            text: 'Update',
            id: 'editModel',
            disabled: ![ModelStatus.InService, ModelStatus.Stopped, ModelStatus.Failed].includes(selectedModel.status),
            disabledReason: ![ModelStatus.InService, ModelStatus.Stopped, ModelStatus.Failed].includes(selectedModel.status) ? 'Unable to delete a model that is in a pending state' : '',
        });
    }

    return (
        <ButtonDropdown
            items={items}
            variant='primary'
            disabled={!selectedModel}
            loading={isDeleteLoading || isUpdating}
            onItemClick={(e) =>
                ModelActionHandler(e, selectedModel, dispatch, deleteMutation, updateModelMutation, props.setNewModelModelVisible, props.setEdit)
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
    updateMutation: MutationTrigger<any>,
    setNewModelModelVisible: (boolean) => void,
    setEdit: (boolean) => void
) => {
    switch (e.detail.id) {
        case 'startModel':
            dispatch(
                setConfirmationModal({
                    action: 'Start',
                    resourceName: 'Model',
                    onConfirm: () => updateMutation({
                        modelId: selectedModel.modelId,
                        enabled: true
                    }),
                    description: `This will start the following model: ${selectedModel.modelId}.`
                })
            );
            break;
        case 'stopModel':
            dispatch(
                setConfirmationModal({
                    action: 'Stop',
                    resourceName: 'Model',
                    onConfirm: () => updateMutation({
                        modelId: selectedModel.modelId,
                        enabled: false
                    }),
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

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
import { Button, ButtonDropdown, Icon, SpaceBetween } from '@cloudscape-design/components';
import { useAppDispatch, useAppSelector } from '@/config/store';
import { IModel, ModelStatus } from '@/shared/model/model-management.model';
import { useNotificationService } from '@/shared/util/hooks';
import { INotificationService } from '@/shared/notification/notification.service';
import { useDeleteModelMutation, useUpdateModelMutation } from '@/shared/reducers/model-management.reducer';
import { MutationTrigger } from '@reduxjs/toolkit/dist/query/react/buildHooks';
import { Action, ThunkDispatch } from '@reduxjs/toolkit';
import { setConfirmationModal } from '@/shared/reducers/modal.reducer';
import { IConfiguration, SystemConfiguration } from '@/shared/model/configuration.model';
import { selectCurrentUsername } from '@/shared/reducers/user.reducer';

export type ModelActionProps = {
    selectedItems: IModel[];
    setSelectedItems: (items: IModel[]) => void;
    setNewModelModelVisible: (state: boolean) => void;
    setEdit: (state: boolean) => void;
    updateConfigMutation?: any;
    currentDefaultModel?: string;
    currentConfig?: any;
    refetch?: () => void;
};

function ModelActions (props: ModelActionProps): ReactElement {
    const dispatch = useAppDispatch();
    const notificationService = useNotificationService(dispatch);

    return (
        <SpaceBetween direction='horizontal' size='xs'>
            <Button
                onClick={() => {
                    props.setSelectedItems([]);
                    props.refetch?.();
                }}
                ariaLabel={'Refresh models cards'}
            >
                <Icon name='refresh' />
            </Button>

            {ModelActionButton(dispatch, notificationService, props)}
            <Button
                variant='primary'
                onClick={() => {
                    props.setEdit(false);
                    props.setNewModelModelVisible(true);
                }}
            >
                Create Model
            </Button>
        </SpaceBetween>
    );
}

function ModelActionButton (dispatch: ThunkDispatch<any, any, Action>, notificationService: INotificationService, props?: any): ReactElement {
    const selectedModel: IModel = props?.selectedItems[0];
    const currentUsername = useAppSelector(selectCurrentUsername);
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
            const errorMessage = deleteError && 'data' in deleteError ? deleteError.data?.message ?? deleteError.data?.detail ?? deleteError.data : 'Unknown error occurred';
            notificationService.generateNotification(`Error deleting model: ${errorMessage}`, 'error');
            props.setSelectedItems([]);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isDeleteSuccess, isDeleteError, deleteError, isDeleteLoading]);

    useEffect(() => {
        if (!isUpdating && isUpdateSuccess && selectedModel) {
            notificationService.generateNotification(`Successfully updated model: ${selectedModel.modelId}`, 'success');
            props.setSelectedItems([]);
        } else if (!isUpdating && isUpdateError && selectedModel) {
            const errorMessage = updateError && 'data' in updateError ? updateError.data?.message ?? updateError.data?.detail ?? updateError.data : 'Unknown error occurred';
            notificationService.generateNotification(`Error updating model: ${errorMessage}`, 'error');
            props.setSelectedItems([]);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isUpdateSuccess, isUpdateError, updateError, isUpdating]);

    const items = [];
    if (selectedModel) {
        const externalModel: boolean = selectedModel.containerConfig === null && selectedModel.autoScalingConfig === null && selectedModel.loadBalancerConfig === null;
        items.push({
            text: 'Delete',
            id: 'deleteModel',
            disabled: ![ModelStatus.InService, ModelStatus.Stopped, ModelStatus.Failed].includes(selectedModel.status),
            disabledReason: ![ModelStatus.InService, ModelStatus.Stopped, ModelStatus.Failed].includes(selectedModel.status) ? 'Unable to delete a model that is in a pending state' : '',
        });
        items.push({
            text: 'Start',
            id: 'startModel',
            disabled: externalModel || selectedModel.status !== ModelStatus.Stopped,
            disabledReason: externalModel ? 'Unable to start a model that is not hosted in LISA' : selectedModel.status !== ModelStatus.Stopped ? 'Unable to start a model that is not in Stopped state' : '',
        });
        items.push({
            text: 'Stop',
            id: 'stopModel',
            disabled: externalModel || selectedModel.status !== ModelStatus.InService,
            disabledReason: externalModel ? 'Unable to stop a model that is not hosted in LISA' : selectedModel.status !== ModelStatus.InService ? 'Unable to stop a model that is not in InService state' : '',
        });
        items.push({
            text: 'Update',
            id: 'editModel',
            disabled: ![ModelStatus.InService, ModelStatus.Stopped].includes(selectedModel.status),
            disabledReason: ![ModelStatus.InService, ModelStatus.Stopped].includes(selectedModel.status) ? 'Unable to update a model that is in a pending or failed state' : '',
        });
        items.push({
            text: 'Set Default',
            id: 'setDefault',
            disabled: selectedModel.modelId === props?.currentDefaultModel,
            disabledReason: selectedModel.modelId === props?.currentDefaultModel ? 'This model is already the default' : '',
        });
    }

    return (
        <ButtonDropdown
            data-testid='model-actions-dropdown'
            items={items}
            variant='primary'
            disabled={!selectedModel}
            loading={isDeleteLoading || isUpdating}
            onItemClick={(e) =>
                ModelActionHandler(e, selectedModel, dispatch, deleteMutation, updateModelMutation, props.setNewModelModelVisible, props.setEdit, props.updateConfigMutation, notificationService, props.currentConfig, currentUsername)
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
    setEdit: (boolean) => void,
    updateConfigMutation?: any,
    notificationService?: INotificationService,
    currentConfig?: any,
    currentUsername?: string
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
        case 'setDefault':
            if (updateConfigMutation && notificationService && currentConfig) {
                dispatch(
                    setConfirmationModal({
                        action: 'Set Default',
                        resourceName: 'Model',
                        onConfirm: async () => {
                            try {
                                const updatedConfiguration: SystemConfiguration = {
                                    ...currentConfig[0]?.configuration,
                                    global: { defaultModel: selectedModel.modelId }
                                };
                                const configUpdate: IConfiguration = {
                                    configuration: updatedConfiguration,
                                    configScope: 'global',
                                    versionId: Number(currentConfig[0]?.versionId) + 1,
                                    changedBy: currentUsername ?? 'Admin',
                                    changeReason: `Set default model to: ${selectedModel.modelId}`,
                                };

                                await updateConfigMutation(configUpdate).unwrap();
                                notificationService.generateNotification(`Successfully set ${selectedModel.modelId} as default model`, 'success');
                            } catch (error) {
                                notificationService.generateNotification(`Error setting default model: ${error}`, 'error');
                            }
                        },
                        description: `This will set ${selectedModel.modelId} as the default model.`
                    })
                );
            }
            break;
        default:
            return;
    }
};

export { ModelActions };

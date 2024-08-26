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

import SpaceBetween from '@cloudscape-design/components/space-between';
import { Modal, Wizard } from '@cloudscape-design/components';
import { IModel, IModelRequest, ModelRequestSchema } from '../../../shared/model/model-management.model';
import { ReactElement, useEffect } from 'react';
import { scrollToInvalid, useValidationReducer } from '../../../shared/validation';
import { BaseModelConfig } from './BaseModelConfig';
import { ContainerConfig } from './ContainerConfig';
import { AutoScalingConfig } from './AutoScalingConfig';
import { LoadBalancerConfig } from './LoadBalancerConfig';
import { useCreateModelMutation, useUpdateModelMutation } from '../../../shared/reducers/model-management.reducer';
import { useAppDispatch } from '../../../config/store';
import { useNotificationService } from '../../../shared/util/hooks';

export type CreateModelModalProps = {
    visible: boolean;
    isEdit: boolean;
    setIsEdit: (boolean) => void;
    setVisible: (boolean) => void;
    selectedItems: IModel[];
};

export type ModelCreateState = {
    validateAll: boolean;
    form: IModelRequest;
    touched: any;
    formSubmitting: boolean;
    activeStepIndex: number;
};

export function CreateModelModal (props: CreateModelModalProps) : ReactElement {
    const [
        createModelMutation,
        { isSuccess: isCreateSuccess, isError: isCreateError, error: createError, isLoading: isCreating },
    ] = useCreateModelMutation();
    const [
        updateModelMutation,
        { isSuccess: isUpdateSuccess, isError: isUpdateError, error: updateError, isLoading: isUpdating },
    ] = useUpdateModelMutation();
    const initialForm = ModelRequestSchema.parse({});
    const dispatch = useAppDispatch();
    const notificationService = useNotificationService(dispatch);

    const { state, setState, setFields, touchFields, errors, isValid } = useValidationReducer(ModelRequestSchema, {
        validateAll: false as boolean,
        touched: {},
        formSubmitting: false as boolean,
        form: {
            ...initialForm
        },
        activeStepIndex: 0,
    } as ModelCreateState);

    function resetState () {
        setState({
            validateAll: false as boolean,
            touched: {},
            formSubmitting: false as boolean,
            form: {
                ...initialForm
            },
            activeStepIndex: 0,
        });
    }

    function handleSubmit () {
        if (isValid && !props.isEdit) {
            createModelMutation(state.form);
        } else if (isValid && props.isEdit) {
            updateModelMutation(state.form);
        }
    }

    useEffect(() => {
        if (props.isEdit) {
            setState({
                ...state,
                form: {
                    ...props.selectedItems[0]
                }
            });
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [props.isEdit]);

    useEffect(() => {
        if (!isCreating && isCreateSuccess) {
            notificationService.generateNotification(`Successfully created model: ${state.form.ModelId}`, 'success');
            props.setVisible(false);
            props.setIsEdit(false);
            resetState();
        } else if (!isCreating && isCreateError) {
            notificationService.generateNotification(`Error creating model: ${createError.data.message ?? createError.data}`, 'error');
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isCreateError, createError, isCreating, isCreateSuccess]);

    useEffect(() => {
        if (!isUpdating && isUpdateSuccess) {
            notificationService.generateNotification(`Successfully updated model: ${state.form.ModelId}`, 'success');
            props.setVisible(false);
            props.setIsEdit(false);
            resetState();
        } else if (!isUpdating && isUpdateError) {
            notificationService.generateNotification(`Error updating model: ${updateError.data.message ?? updateError.data}`, 'error');
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isUpdateError, updateError, isUpdating, isUpdateSuccess]);

    return (
        <Modal size={'large'} onDismiss={() => {
            props.setVisible(false); props.setIsEdit(false); resetState();
        }} visible={props.visible} header={`${props.isEdit ? 'Update' : 'Create'} Model`}>
            <Wizard
                i18nStrings={{
                    stepNumberLabel: (stepNumber) => `Step ${stepNumber}`,
                    collapsedStepsLabel: (stepNumber, stepsCount) => `Step ${stepNumber} of ${stepsCount}`,
                    skipToButtonLabel: () => `Skip to ${props.isEdit ? 'Update' : 'Create'}`,
                    navigationAriaLabel: 'Steps',
                    cancelButton: 'Cancel',
                    previousButton: 'Previous',
                    nextButton: 'Next',
                    submitButton: props.isEdit ? 'Update Model' : 'Create Model',
                    optional: 'optional'
                }}
                onNavigate={(event) => {
                    switch (event.detail.reason) {
                        case 'step':
                        case 'previous':
                            setState({
                                ...state,
                                activeStepIndex: event.detail.requestedStepIndex,
                            });
                            break;
                        case 'next':
                        case 'skip':
                            {
                                if (isValid) {
                                    setState({
                                        ...state,
                                        activeStepIndex: event.detail.requestedStepIndex,
                                    });
                                    break;
                                }
                            }
                            break;
                    }

                    scrollToInvalid();
                }}
                onCancel={() => {
                    props.setVisible(false);
                    props.setIsEdit(false);
                    resetState();
                }}
                onSubmit={() => {
                    handleSubmit();
                }}
                activeStepIndex={state.activeStepIndex}
                isLoadingNextStep={isCreating || isUpdating}
                allowSkipTo
                steps={[
                    {
                        title: 'Base Model Configuration',
                        description: 'Place Holder Description Base Model Config',
                        content: (
                            <BaseModelConfig item={state.form} setFields={setFields} touchFields={touchFields} formErrors={errors} isEdit={props.isEdit} />
                        )
                    },
                    {
                        title: 'Container Configuration',
                        description: 'Place Holder Description Container Config',
                        content: (
                            <ContainerConfig item={state.form.ContainerConfig} setFields={setFields} touchFields={touchFields} formErrors={errors} />
                        ),
                        isOptional: true
                    },
                    {
                        title: 'Auto Scaling Configuration',
                        description: 'Place Holder Description Auto Scaling Config',
                        content: (
                            <AutoScalingConfig item={state.form.AutoScalingConfig} setFields={setFields} touchFields={touchFields} formErrors={errors} />
                        ),
                        isOptional: true
                    },
                    {
                        title: 'Load Balancer Configuration',
                        description: 'Place Holder Description Load Balancer Config',
                        content: (
                            <LoadBalancerConfig item={state.form.LoadBalancerConfig} setFields={setFields} touchFields={touchFields} formErrors={errors} />
                        ),
                        isOptional: true
                    },
                    {
                        title: `Review and ${props.isEdit ? 'Update' : 'Create'}`,
                        description: 'Place Holder Description Review Screen',
                        content: (
                            <SpaceBetween size={'s'}>
                            </SpaceBetween>
                        )
                    }
                ]}
            />
        </Modal>
    );
}

export default CreateModelModal;

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

import _ from 'lodash';
import { Modal, Wizard } from '@cloudscape-design/components';
import { IModel, IModelRequest, ModelRequestSchema } from '../../../shared/model/model-management.model';
import { ReactElement, useEffect, useMemo } from 'react';
import { scrollToInvalid, useValidationReducer } from '../../../shared/validation';
import { BaseModelConfig } from './BaseModelConfig';
import { ContainerConfig } from './ContainerConfig';
import { AutoScalingConfig } from './AutoScalingConfig';
import { LoadBalancerConfig } from './LoadBalancerConfig';
import { useCreateModelMutation, useUpdateModelMutation } from '../../../shared/reducers/model-management.reducer';
import { useAppDispatch } from '../../../config/store';
import { useNotificationService } from '../../../shared/util/hooks';
import { ReviewModelChanges } from './ReviewModelChanges';
import { ModifyMethod } from '../../../shared/validation/modify-method';

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
    const initialForm = {
        ...ModelRequestSchema.parse({}),
        modelId: '',
        modelName: '',
    };
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

    const toSubmit: IModelRequest = {
        ...state.form,
        containerConfig: (state.form.lisaHostedModel ? ({
            ...state.form.containerConfig,
            environment: state.form.containerConfig.environment?.reduce((r,{key,value}) => (r[key] = value,r), {})
        }) : null),
        loadBalancerConfig: (state.form.lisaHostedModel ? state.form.loadBalancerConfig : null),
        autoScalingConfig: (state.form.lisaHostedModel ? state.form.autoScalingConfig : null),
        inferenceContainer: state.form.inferenceContainer ?? null,
        instanceType: state.form.instanceType ? state.form.instanceType : null,
        modelUrl: state.form.modelUrl ? state.form.modelUrl : null
    };

    function resetState () {
        setState({
            validateAll: false as boolean,
            touched: {},
            formSubmitting: false as boolean,
            form: {
                ...initialForm
            },
            activeStepIndex: 0,
        }, ModifyMethod.Set);
    }

    /**
     * Computes the difference between two JSON objects, recursively.
     *
     * This function takes two JSON objects as input and returns a new object that
     * contains the differences between the two. Works with nested objects.
     *
     * @param {object} [obj1={}] - The first JSON object to compare.
     * @param {object} [obj2={}] - The second JSON object to compare.
     * @returns {object} - A new object containing the differences between the two input objects.
     */
    function getJsonDifference (obj1 = {}, obj2 = {}) {
        const output = {},
            merged = { ...obj1, ...obj2 }; // has properties of both

        for (const key in merged) {
            const value1 = obj1 && Object.keys(obj1).includes(key) ? obj1[key] : undefined;
            const value2 = obj2 && Object.keys(obj2).includes(key) ? obj2[key] : undefined;

            if (_.isPlainObject(value1) || _.isPlainObject(value2)) {
                const value = getJsonDifference(value1, value2); // recursively call
                if (Object.keys(value).length !== 0) {
                    output[key] = value;
                }

            } else {
                if (!_.isEqual(value1, value2) && (value1 || value2)) {
                    output[key] = value2;
                    // output[key][value2] = value2.
                }
            }
        }
        return output;
    }

    const changesDiff = useMemo(() => {
        return props.isEdit ? getJsonDifference(props.selectedItems[0], toSubmit) : getJsonDifference({}, toSubmit);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [toSubmit, initialForm, props.isEdit]);

    function handleSubmit () {
        delete toSubmit.lisaHostedModel;
        if (isValid && !props.isEdit) {
            createModelMutation(toSubmit);
        } else if (isValid && props.isEdit) {
            updateModelMutation(toSubmit);
        }
    }

    const requiredFields = [['modelId', 'modelName'], [], [], [], []];

    useEffect(() => {
        const parsedValue = _.mergeWith({}, initialForm, props.selectedItems[0], (a: IModelRequest, b: IModelRequest) => b === null ? a : undefined);
        if (props.isEdit) {
            setState({
                ...state,
                form: {
                    ...parsedValue,
                    containerConfig: {
                        ...parsedValue.containerConfig,
                        environment: props.selectedItems[0].containerConfig?.environment ? Object.entries(props.selectedItems[0].containerConfig?.environment).map(([key, value]) => ({ key, value })) : [],
                    },
                    lisaHostedModel: Boolean(props.selectedItems[0].containerConfig || props.selectedItems[0].autoScalingConfig || props.selectedItems[0].loadBalancerConfig)
                }
            });
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [props.isEdit]);

    useEffect(() => {
        if (!isCreating && isCreateSuccess) {
            notificationService.generateNotification(`Successfully created model: ${state.form.modelId}`, 'success');
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
            notificationService.generateNotification(`Successfully updated model: ${state.form.modelId}`, 'success');
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
                    optional: 'LISA hosted models only'
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
                                touchFields(requiredFields[state.activeStepIndex]);
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
                        description: 'Define your model\'s configuration settings using these forms.',
                        content: (
                            <BaseModelConfig item={state.form} setFields={setFields} touchFields={touchFields} formErrors={errors} isEdit={props.isEdit} />
                        )
                    },
                    {
                        title: 'Container Configuration',
                        content: (
                            <ContainerConfig item={state.form.containerConfig} setFields={setFields} touchFields={touchFields} formErrors={errors} />
                        ),
                        isOptional: true
                    },
                    {
                        title: 'Auto Scaling Configuration',
                        content: (
                            <AutoScalingConfig item={state.form.autoScalingConfig} setFields={setFields} touchFields={touchFields} formErrors={errors} />
                        ),
                        isOptional: true
                    },
                    {
                        title: 'Load Balancer Configuration',
                        content: (
                            <LoadBalancerConfig item={state.form.loadBalancerConfig} setFields={setFields} touchFields={touchFields} formErrors={errors} />
                        ),
                        isOptional: true
                    },
                    {
                        title: `Review and ${props.isEdit ? 'Update' : 'Create'}`,
                        description: `Review configuration ${props.isEdit ? 'changes' : ''} prior to submitting.`,
                        content: (
                            <ReviewModelChanges jsonDiff={changesDiff}/>
                        )
                    }
                ]}
            />
        </Modal>
    );
}

export default CreateModelModal;

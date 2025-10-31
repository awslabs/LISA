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
import { ReactElement, useEffect, useMemo, useState } from 'react';
import { scrollToInvalid, useValidationReducer } from '../../../shared/validation';
import { BaseModelConfig } from './BaseModelConfig';
import { ContainerConfig } from './ContainerConfig';
import { AutoScalingConfig } from './AutoScalingConfig';
import { LoadBalancerConfig } from './LoadBalancerConfig';
import { GuardrailsConfig } from './GuardrailsConfig';
import { useCreateModelMutation, useUpdateModelMutation } from '../../../shared/reducers/model-management.reducer';
import { useAppDispatch } from '../../../config/store';
import { useNotificationService } from '../../../shared/util/hooks';
import { ModifyMethod } from '../../../shared/validation/modify-method';
import { getJsonDifference, normalizeError } from '../../../shared/util/validationUtils';
import { setConfirmationModal } from '../../../shared/reducers/modal.reducer';
import { ReviewChanges } from '../../../shared/modal/ReviewChanges';
import { getDefaults } from '#root/lib/schema/zodUtil';
import { EcsRestartWarning } from '../EcsRestartWarning';

export type CreateModelModalProps = {
    visible: boolean;
    isEdit: boolean;
    setIsEdit: (isEdit: boolean) => void;
    setVisible: (isEdit: boolean) => void;
    selectedItems: IModel[];
    setSelectedItems: (items: IModel[]) => void;
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
        { isSuccess: isCreateSuccess, isError: isCreateError, error: createError, isLoading: isCreating, reset: resetCreate },
    ] = useCreateModelMutation();
    const [
        updateModelMutation,
        { isSuccess: isUpdateSuccess, isError: isUpdateError, error: updateError, isLoading: isUpdating, reset: resetUpdate },
    ] = useUpdateModelMutation();
    const initialForm = {
        ...getDefaults(ModelRequestSchema),
    };
    const dispatch = useAppDispatch();
    const notificationService = useNotificationService(dispatch);

    // ECS restart warning state
    const [ecsRestartAcknowledged, setEcsRestartAcknowledged] = useState(false);

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
            environment: (() => {
                if (props.isEdit) {
                    // For edit mode, include DELETE markers for removed environment variables
                    const originalEnv = props.selectedItems[0]?.containerConfig?.environment || {};
                    const result: any = {};
                    const currentKeys = new Set<string>();

                    // Add/update current variables and track keys
                    (state.form.containerConfig.environment || []).forEach(({key, value}: any) => {
                        if (key && key.trim() !== '') {
                            result[key] = value;
                            currentKeys.add(key);
                        }
                    });

                    // Mark deletions for review modal
                    Object.keys(originalEnv).forEach((key) => {
                        if (!currentKeys.has(key)) {
                            result[key] = 'LISA_MARKED_FOR_DELETION';
                        }
                    });
                    return result;
                } else {
                    // For create mode, just convert array to object
                    return state.form.containerConfig.environment?.reduce((r: any,{key,value}: any) => {
                        if (key && key.trim() !== '') {
                            r[key] = value;
                        }
                        return r;
                    }, {});
                }
            })()
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
        resetCreate();
        resetUpdate();
        setEcsRestartAcknowledged(false);
    }

    const changesDiff = useMemo(() => {
        return props.isEdit ? getJsonDifference({
            ...props.selectedItems[0],
            lisaHostedModel: Boolean(props.selectedItems[0].containerConfig || props.selectedItems[0].autoScalingConfig || props.selectedItems[0].loadBalancerConfig)
        }, toSubmit) :
            getJsonDifference({}, toSubmit);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [toSubmit, initialForm, props.isEdit]);

    // Check if ECS restart is required
    const requiresEcsRestart = useMemo(() => {
        if (!props.isEdit || !props.selectedItems[0]) return false;

        const isLisaHosted = Boolean(props.selectedItems[0].containerConfig);
        const hasContainerChanges = (changesDiff as any)?.containerConfig !== undefined;

        return isLisaHosted && hasContainerChanges;
    }, [props.isEdit, props.selectedItems, changesDiff]);

    useEffect(() => {
        if (requiresEcsRestart) {
            setEcsRestartAcknowledged(false);
        }
    }, [requiresEcsRestart]);

    function handleSubmit () {
        // Check if ECS restart acknowledgment is required but not provided
        if (requiresEcsRestart && !ecsRestartAcknowledged) {
            return; // Don't proceed with submission
        }

        delete toSubmit.lisaHostedModel;
        if (isValid && !props.isEdit && !_.isEmpty(changesDiff)) {
            resetCreate();
            createModelMutation(toSubmit);
        } else if (isValid && props.isEdit && !_.isEmpty(changesDiff)) {
            // pick only the values we care about for update
            resetUpdate();
            const updateFields: any = _.pick({...changesDiff, modelId: props.selectedItems[0].modelId}, [
                'modelId',
                'streaming',
                'enabled',
                'modelType',
                'modelDescription',
                'allowedGroups',
                'features',
                'containerConfig',
                'autoScalingConfig',
                'guardrailsConfig'
            ]);

            // Build the update request
            const baseRequest = { modelId: props.selectedItems[0].modelId };

            // Pick defined fields from updateFields for basic properties
            const basicFields = _.pickBy(updateFields, (value, key) =>
                ['streaming', 'enabled', 'modelType', 'modelDescription', 'allowedGroups', 'features'].includes(key) &&
                value !== undefined
            );

            const updateRequest: any = _.merge({}, baseRequest, basicFields);

            // Handle containerConfig if present
            if (updateFields.containerConfig !== undefined) {
                const containerConfigBase = _.omit(updateFields.containerConfig, ['healthCheckConfig', 'sharedMemorySize']);

                const containerConfig = _.merge({}, containerConfigBase, {
                    environment: (() => {
                        const originalEnv = props.selectedItems[0]?.containerConfig?.environment || {};
                        const result: any = {};
                        const currentKeys = new Set<string>();

                        // Add/update current variables and track keys
                        (state.form.containerConfig.environment || []).forEach(({key, value}: any) => {
                            if (key && key.trim() !== '') {
                                result[key] = value;
                                currentKeys.add(key);
                            }
                        });

                        // Mark deletions
                        Object.keys(originalEnv).forEach((key) => {
                            if (!currentKeys.has(key)) {
                                result[key] = 'LISA_MARKED_FOR_DELETION';
                            }
                        });
                        return result;
                    })()
                });

                // Add health check config if present
                if (updateFields.containerConfig.healthCheckConfig) {
                    const healthCheckMapping = {
                        healthCheckCommand: 'command',
                        healthCheckInterval: 'interval',
                        healthCheckTimeout: 'timeout',
                        healthCheckStartPeriod: 'startPeriod',
                        healthCheckRetries: 'retries'
                    };

                    const healthCheckFields = _.mapKeys(
                        updateFields.containerConfig.healthCheckConfig,
                        (value, key) => _.findKey(healthCheckMapping, (mappedKey) => mappedKey === key) || key
                    );
                    _.merge(containerConfig, healthCheckFields);
                }

                // Add shared memory size if present
                if (updateFields.containerConfig.sharedMemorySize !== undefined) {
                    containerConfig.sharedMemorySize = updateFields.containerConfig.sharedMemorySize;
                }
                updateRequest.containerConfig = containerConfig;
            }

            // Handle autoScalingConfig if present
            if (updateFields.autoScalingConfig) {
                updateRequest.autoScalingInstanceConfig = _.pickBy(updateFields.autoScalingConfig,
                    (value) => value !== undefined
                );
            }

            // Handle guardrailsConfig if present
            if (updateFields.guardrailsConfig !== undefined) {
                // Send the complete current guardrails config from state.form, not just the diff
                // This ensures all guardrails are preserved unless explicitly marked for deletion
                updateRequest.guardrailsConfig = state.form.guardrailsConfig;
            }

            updateModelMutation(updateRequest);
        }
    }

    const requiredFields = [['modelId', 'modelName'], ['containerConfig.image.baseImage'], [], [], []];

    useEffect(() => {
        const parsedValue = _.mergeWith({}, initialForm, props.selectedItems[0], (a: IModelRequest, b: IModelRequest) => b === null ? a : undefined);
        if (parsedValue.inferenceContainer === null){
            delete parsedValue.inferenceContainer;
        }
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
        } else {
            // For new models, default to Third Party (lisaHostedModel = false)
            setState({
                ...state,
                form: {
                    ...state.form,
                    lisaHostedModel: false
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
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isCreating, isCreateSuccess]);

    useEffect(() => {
        if (!isUpdating && isUpdateSuccess) {
            notificationService.generateNotification(`Successfully updated model: ${state.form.modelId}`, 'success');
            props.setVisible(false);
            props.setIsEdit(false);
            props.setSelectedItems([]);
            resetState();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isUpdating, isUpdateSuccess]);


    const reviewError = normalizeError('Model', isCreateError ? createError : isUpdateError ? updateError : undefined);

    const allSteps = [
        {
            title: 'Base Model Configuration',
            description: 'Define your model\'s configuration settings using these forms.',
            content: (
                <BaseModelConfig item={state.form} setFields={setFields} touchFields={touchFields} formErrors={errors} isEdit={props.isEdit} />
            ),
            onEdit: true,
            forExternalModel: true
        },
        {
            title: 'Container Configuration',
            content: (
                <ContainerConfig item={state.form.containerConfig} setFields={setFields} touchFields={touchFields} formErrors={errors} isEdit={props.isEdit} />
            ),
            isOptional: true,
            onEdit: state.form.lisaHostedModel,
            forExternalModel: false
        },
        {
            title: 'Auto Scaling Configuration',
            content: (
                <AutoScalingConfig item={state.form.autoScalingConfig} setFields={setFields} touchFields={touchFields} formErrors={errors} isEdit={props.isEdit} />
            ),
            isOptional: true,
            onEdit: state.form.lisaHostedModel,
            forExternalModel: false
        },
        {
            title: 'Load Balancer Configuration',
            content: (
                <LoadBalancerConfig item={state.form.loadBalancerConfig} setFields={setFields} touchFields={touchFields} formErrors={errors} isEdit={props.isEdit} />
            ),
            isOptional: true,
            onEdit: state.form.lisaHostedModel,
            forExternalModel: false
        },
        {
            title: 'Guardrails Configuration',
            description: 'Configure guardrails for your model (optional).',
            content: (
                <GuardrailsConfig item={state.form.guardrailsConfig || { guardrails: {} }} setFields={setFields} touchFields={touchFields} formErrors={errors} isEdit={props.isEdit} />
            ),
            onEdit: true,
            forExternalModel: true
        },
        {
            title: `Review and ${props.isEdit ? 'Update' : 'Create'}`,
            description: `Review configuration ${props.isEdit ? 'changes' : ''} prior to submitting.`,
            content: (
                <div>
                    <ReviewChanges jsonDiff={changesDiff} error={reviewError} />
                    {requiresEcsRestart && (
                        <div style={{ marginTop: '1rem' }}>
                            <EcsRestartWarning
                                acknowledged={ecsRestartAcknowledged}
                                onAcknowledge={setEcsRestartAcknowledged}
                            />
                        </div>
                    )}
                </div>
            ),
            onEdit: true,
            forExternalModel: true
        }
    ];

    const steps = allSteps.filter((step) => {
        if (props.isEdit) {
            // For edit mode, use the same logic as create mode
            if (!state.form.lisaHostedModel) {
                return step.forExternalModel;
            } else {
                return true; // Show all steps for LISA hosted models
            }
        } else {
            if (!state.form.lisaHostedModel) {
                return step.forExternalModel;
            } else {
                return true; // Show all steps for LISA hosted models
            }
        }
    });


    return (
        <Modal size={'large'} onDismiss={() => {
            dispatch(
                setConfirmationModal({
                    action: 'Discard',
                    resourceName: 'Model Creation',
                    onConfirm: () => {
                        props.setVisible(false);
                        props.setIsEdit(false);
                        resetState();
                    },
                    description: 'Are you sure you want to discard your changes?'
                }));
        }} visible={props.visible} header={`${props.isEdit ? 'Update' : 'Create'} Model`}>
            <Wizard
                submitButtonText={props.isEdit ? 'Update Model' : 'Create Model'}
                i18nStrings={{
                    stepNumberLabel: (stepNumber) => `Step ${stepNumber}`,
                    collapsedStepsLabel: (stepNumber, stepsCount) => `Step ${stepNumber} of ${stepsCount}`,
                    skipToButtonLabel: () => `Skip to ${props.isEdit ? 'Update' : 'Create'}`,
                    navigationAriaLabel: 'Steps',
                    cancelButton: 'Cancel',
                    previousButton: 'Previous',
                    nextButton: 'Next',
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
                                if (touchFields(requiredFields[state.activeStepIndex]) && isValid) {
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
                    dispatch(
                        setConfirmationModal({
                            action: 'Discard',
                            resourceName: 'Model Creation',
                            onConfirm: () => {
                                props.setVisible(false);
                                props.setIsEdit(false);
                                resetState();
                            },
                            description: 'Are you sure you want to discard your changes?'
                        }));
                }}
                onSubmit={() => {
                    handleSubmit();
                }}
                activeStepIndex={state.activeStepIndex}
                isLoadingNextStep={isCreating || isUpdating}
                allowSkipTo
                steps={steps}
            />
        </Modal>
    );
}

export default CreateModelModal;

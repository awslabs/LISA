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

import React, { ReactElement, useEffect, useMemo } from 'react';
import { Modal, Wizard } from '@cloudscape-design/components';
import { useAppDispatch } from '@/config/store';
import { scrollToInvalid, useValidationReducer } from '@/shared/validation';
import { setConfirmationModal } from '@/shared/reducers/modal.reducer';
import { useNotificationService } from '@/shared/util/hooks';
import { getJsonDifference, normalizeError } from '@/shared/util/validationUtils';
import {
    ChatAssistantStackRequestSchema,
    ChatAssistantStackRequestForm,
    IChatAssistantStack,
} from '@/shared/model/chat-assistant-stack.model';
import {
    useCreateStackMutation,
    useUpdateStackMutation,
} from '@/shared/reducers/chat-assistant-stacks.reducer';
import { useGetAllModelsQuery } from '@/shared/reducers/model-management.reducer';
import { ModelType } from '@/shared/model/model-management.model';
import {
    StackBaseForm,
    StackModelsStep,
    StackRagStep,
    StackAgentsStep,
    StackPromptsStep,
    StackAccessStep,
} from './StackFormSteps';
import { ModifyMethod } from '@/shared/validation/modify-method';
import { ReviewChanges } from '@/shared/modal/ReviewChanges';

export type CreateStackModalProps = {
    visible: boolean;
    setVisible: (v: boolean) => void;
    isEdit: boolean;
    setIsEdit: (v: boolean) => void;
    selectedStack: IChatAssistantStack | null;
    setSelectedItems: (items: IChatAssistantStack[]) => void;
};

/** Initial empty form; no Zod parse so validation only runs on Next/Submit. */
const initialForm: ChatAssistantStackRequestForm = {
    name: '',
    description: '',
    modelIds: [],
    repositoryIds: [],
    collectionIds: [],
    mcpServerIds: [],
    mcpToolIds: [],
    personaPromptId: null,
    directivePromptIds: [],
    allowedGroups: [],
};

type CreateStackState = {
    validateAll: boolean;
    form: ChatAssistantStackRequestForm;
    touched: Record<string, unknown>;
    formSubmitting: boolean;
    activeStepIndex: number;
};

export function CreateStackModal (props: CreateStackModalProps): ReactElement {
    const { visible, setVisible, isEdit, setIsEdit, selectedStack, setSelectedItems } = props;
    const dispatch = useAppDispatch();
    const notificationService = useNotificationService(dispatch);

    const [createStack, { isSuccess: isCreateSuccess, isError: isCreateError, error: createError, isLoading: isCreating, reset: resetCreate }] = useCreateStackMutation();
    const [updateStack, { isSuccess: isUpdateSuccess, isError: isUpdateError, error: updateError, isLoading: isUpdating, reset: resetUpdate }] = useUpdateStackMutation();

    const isSaving = isCreating || isUpdating;
    const { data: models } = useGetAllModelsQuery(undefined, { skip: !visible });

    const { state, setState, setFields, touchFields, errors, isValid } = useValidationReducer(
        ChatAssistantStackRequestSchema,
        {
            validateAll: false,
            touched: {},
            formSubmitting: false,
            form: initialForm,
            activeStepIndex: 0,
        } as CreateStackState
    );

    useEffect(() => {
        if (visible) {
            if (isEdit && selectedStack) {
                setState({
                    ...state,
                    form: {
                        name: selectedStack.name,
                        description: selectedStack.description,
                        modelIds: selectedStack.modelIds || [],
                        repositoryIds: selectedStack.repositoryIds || [],
                        collectionIds: selectedStack.collectionIds || [],
                        mcpServerIds: selectedStack.mcpServerIds || [],
                        mcpToolIds: selectedStack.mcpToolIds || [],
                        personaPromptId: selectedStack.personaPromptId ?? null,
                        directivePromptIds: selectedStack.directivePromptIds || [],
                        allowedGroups: selectedStack.allowedGroups || [],
                    },
                    activeStepIndex: 0,
                });
            } else {
                setState({
                    ...state,
                    form: initialForm,
                    activeStepIndex: 0,
                });
            }
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [visible, isEdit, selectedStack?.stackId]);

    useEffect(() => {
        if (!isCreating && isCreateSuccess) {
            notificationService.generateNotification('Successfully created Chat Assistant Stack', 'success');
            setVisible(false);
            setSelectedItems([]);
            resetCreate();
        } else if (!isCreating && isCreateError) {
            notificationService.generateNotification(
                normalizeError('Create Chat Assistant Stack', createError)?.message ?? 'Failed to create stack',
                'error'
            );
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isCreateSuccess, isCreateError, createError, isCreating]);

    useEffect(() => {
        if (!isUpdating && isUpdateSuccess) {
            notificationService.generateNotification('Successfully updated Chat Assistant Stack', 'success');
            setVisible(false);
            setSelectedItems([]);
            resetUpdate();
        } else if (!isUpdating && isUpdateError) {
            notificationService.generateNotification(
                normalizeError('Update Chat Assistant Stack', updateError)?.message ?? 'Failed to update stack',
                'error'
            );
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isUpdateSuccess, isUpdateError, updateError, isUpdating]);

    const changesDiff = useMemo(() => {
        if (!isEdit || !selectedStack) return state.form;
        return getJsonDifference(
            {
                name: selectedStack.name,
                description: selectedStack.description,
                modelIds: selectedStack.modelIds,
                repositoryIds: selectedStack.repositoryIds,
                collectionIds: selectedStack.collectionIds,
                mcpServerIds: selectedStack.mcpServerIds,
                mcpToolIds: selectedStack.mcpToolIds,
                personaPromptId: selectedStack.personaPromptId,
                directivePromptIds: selectedStack.directivePromptIds,
                allowedGroups: selectedStack.allowedGroups,
            },
            state.form
        );
    }, [isEdit, selectedStack, state.form]);

    const reviewError = normalizeError('Chat Assistant Stack', isEdit ? updateError : createError);

    function handleSubmit () {
        const form = state.form;
        if (!form.modelIds.length) {
            touchFields(['modelIds']);
            return;
        }
        if (form.mcpServerIds.length > 0 && models) {
            const selectedModels = models.filter((m) => form.modelIds.includes(m.modelId));
            const hasTextgen = selectedModels.some((m) => m.modelType === ModelType.textgen);
            if (!hasTextgen) {
                notificationService.generateNotification(
                    'At least one selected model must support MCP tools (e.g. text generation model).',
                    'error'
                );
                return;
            }
        }
        if (isEdit && selectedStack) {
            updateStack({ stackId: selectedStack.stackId, body: form });
        } else {
            createStack(form);
        }
    }

    function resetState () {
        setState({
            validateAll: false,
            touched: {},
            formSubmitting: false,
            form: initialForm,
            activeStepIndex: 0,
        }, ModifyMethod.Set);
        resetCreate();
        resetUpdate();
    }

    const requiredFieldsByStep: string[][] = [
        ['name', 'description'],
        ['modelIds'],
        [],
        [],
        [],
        [],
        [],
    ];

    const steps = [
        {
            title: 'Name and description',
            description: 'Identify the stack.',
            content: <StackBaseForm item={state.form} setFields={setFields} touchFields={touchFields} formErrors={errors} />,
        },
        {
            title: 'Models',
            description: 'Select at least one model.',
            content: <StackModelsStep item={state.form} setFields={setFields} touchFields={touchFields} formErrors={errors} />,
        },
        {
            title: 'RAG',
            description: 'Optional repositories and collections.',
            isOptional: true,
            content: <StackRagStep item={state.form} setFields={setFields} touchFields={touchFields} formErrors={errors} />,
        },
        {
            title: 'Agents',
            description: 'Optional MCP servers and tools.',
            isOptional: true,
            content: <StackAgentsStep item={state.form} setFields={setFields} touchFields={touchFields} formErrors={errors} />,
        },
        {
            title: 'Prompts',
            description: 'Optional persona and directive prompts.',
            isOptional: true,
            content: <StackPromptsStep item={state.form} setFields={setFields} touchFields={touchFields} formErrors={errors} />,
        },
        {
            title: 'Access',
            description: 'Allowed groups. Empty = global.',
            isOptional: true,
            content: <StackAccessStep item={state.form} setFields={setFields} touchFields={touchFields} formErrors={errors} />,
        },
        {
            title: isEdit ? 'Review and Update' : 'Review and Create',
            description: 'Review and submit.',
            content: (
                <ReviewChanges
                    jsonDiff={changesDiff}
                    error={reviewError}
                />
            ),
        },
    ];

    return (
        <Modal
            size='large'
            visible={visible}
            header={isEdit ? 'Update Chat Assistant Stack' : 'Create Chat Assistant Stack'}
            onDismiss={() => {
                dispatch(
                    setConfirmationModal({
                        action: 'Discard',
                        resourceName: 'Chat Assistant Stack',
                        onConfirm: () => {
                            setVisible(false);
                            setIsEdit(false);
                            resetState();
                        },
                        description: 'Are you sure you want to discard your changes?',
                    })
                );
            }}
        >
            <Wizard
                steps={steps}
                activeStepIndex={state.activeStepIndex}
                submitButtonText={isEdit ? 'Update Stack' : 'Create Stack'}
                isLoadingNextStep={isSaving}
                allowSkipTo
                i18nStrings={{
                    stepNumberLabel: (stepNumber) => `Step ${stepNumber}`,
                    collapsedStepsLabel: (stepNumber, stepsCount) => `Step ${stepNumber} of ${stepsCount}`,
                    skipToButtonLabel: () => (isEdit ? 'Skip to Update' : 'Skip to Create'),
                    navigationAriaLabel: 'Steps',
                    cancelButton: 'Cancel',
                    previousButton: 'Previous',
                    nextButton: 'Next',
                    optional: 'Optional',
                }}
                onNavigate={({ detail }) => {
                    const requested = detail.requestedStepIndex;
                    if (detail.reason === 'next' || detail.reason === 'skip') {
                        const toTouch = requiredFieldsByStep[state.activeStepIndex] || [];
                        if (toTouch.length) touchFields(toTouch);
                        if (!isValid && toTouch.length) {
                            scrollToInvalid();
                            return;
                        }
                    }
                    setState({ ...state, activeStepIndex: requested });
                    scrollToInvalid();
                }}
                onCancel={() => {
                    dispatch(
                        setConfirmationModal({
                            action: 'Discard',
                            resourceName: 'Chat Assistant Stack',
                            onConfirm: () => {
                                setVisible(false);
                                setIsEdit(false);
                                resetState();
                            },
                            description: 'Are you sure you want to discard your changes?',
                        })
                    );
                }}
                onSubmit={handleSubmit}
            />
        </Modal>
    );
}

export default CreateStackModal;

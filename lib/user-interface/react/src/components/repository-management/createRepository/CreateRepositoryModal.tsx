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

import { Modal, Wizard } from '@cloudscape-design/components';
import { ReactElement, useEffect, useMemo } from 'react';
import { scrollToInvalid, useValidationReducer } from '../../../shared/validation';
import { useAppDispatch } from '../../../config/store';
import { useNotificationService } from '../../../shared/util/hooks';
import { setConfirmationModal } from '../../../shared/reducers/modal.reducer';
import { useCreateRagRepositoryMutation, useUpdateRagRepositoryMutation } from '../../../shared/reducers/rag.reducer';
import { RepositoryConfigForm } from './RepositoryConfigForm';
import { ReviewChanges } from '../../../shared/modal/ReviewChanges';
import { getJsonDifference, normalizeError } from '../../../shared/util/validationUtils';
import { ModifyMethod } from '../../../shared/validation/modify-method';
import { PipelineConfigForm } from './PipelineConfigForm';
import _ from 'lodash';
import { RagRepositoryConfig, RagRepositoryConfigSchema, RagRepositoryType } from '#root/lib/schema';

export type CreateRepositoryModalProps = {
    visible: boolean;
    isEdit: boolean;
    setIsEdit: (isEdit: boolean) => void;
    setVisible: (isVisible: boolean) => void;
    selectedItems: ReadonlyArray<RagRepositoryConfig>;
    setSelectedItems: (items: ReadonlyArray<RagRepositoryConfig>) => void;
};

export type RepositoryCreateState = {
    validateAll: boolean;
    form: RagRepositoryConfig;
    touched: any;
    formSubmitting: boolean;
    activeStepIndex: number;
};

export function CreateRepositoryModal(props: CreateRepositoryModalProps): ReactElement {
    const { visible, setVisible, selectedItems, isEdit, setIsEdit } = props;
    const [
        createRepositoryMutation,
        {
            isSuccess: isCreateSuccess,
            error: createError,
            isLoading: isCreating,
            reset: resetCreate,
        },
    ] = useCreateRagRepositoryMutation();

    const [
        updateRepositoryMutation,
        {
            isSuccess: isUpdateSuccess,
            error: updateError,
            isLoading: isUpdating,
            reset: resetUpdate,
        },
    ] = useUpdateRagRepositoryMutation();

    const initialForm: RagRepositoryConfig = RagRepositoryConfigSchema.partial().parse({}) as RagRepositoryConfig;
    const dispatch = useAppDispatch();
    const notificationService = useNotificationService(dispatch);

    const {
        state,
        setState,
        setFields,
        touchFields,
        errors,
        isValid,
    } = useValidationReducer(RagRepositoryConfigSchema, {
        validateAll: false as boolean,
        touched: {},
        formSubmitting: false as boolean,
        form: {
            ...initialForm,
        },
        activeStepIndex: 0,
    } as RepositoryCreateState);

    const toSubmit = {
        ...state.form,
    };

    const changesDiff = useMemo(() => {
        return isEdit ? getJsonDifference({
            ...selectedItems[0],
        }, toSubmit) :
            getJsonDifference({}, toSubmit);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [toSubmit, initialForm, isEdit]);

    const reviewError = normalizeError('Repository', isEdit ? updateError : createError);

    const requiredFields = [['repositoryId', 'type', 'rdsConfig.username', 'rdsConfig.dbName', 'rdsConfig.dbPort', 'opensearchConfig.dataNodes', 'opensearchConfig.dataNodes', 'opensearchConfig.dataNodeInstanceType'], []];


    function handleSubmit() {
        // Validate all fields before submission
        if (isValid && !_.isEmpty(changesDiff)) {
            // For Bedrock Knowledge Base repositories, remove pipelines - they're managed by the backend
            const submissionData = { ...toSubmit };
            if (submissionData.type === RagRepositoryType.BEDROCK_KNOWLEDGE_BASE) {
                delete submissionData.pipelines;
            } else {
                // For non-Bedrock repositories, remove bedrockKnowledgeBaseConfig
                delete submissionData.bedrockKnowledgeBaseConfig;
            }

            // Additional validation: ensure repositoryId is not empty
            if (!isEdit && (!submissionData.repositoryId || submissionData.repositoryId.trim() === '')) {
                notificationService.generateNotification('Repository ID is required', 'error');
                return;
            }

            if (isEdit) {
                resetUpdate();
                // For Bedrock KB updates, send full bedrockKnowledgeBaseConfig to ensure all dataSources are included
                const updates: any = { ...changesDiff };
                if (submissionData.type === RagRepositoryType.BEDROCK_KNOWLEDGE_BASE && submissionData.bedrockKnowledgeBaseConfig) {
                    updates.bedrockKnowledgeBaseConfig = submissionData.bedrockKnowledgeBaseConfig;
                }

                updateRepositoryMutation({
                    repositoryId: submissionData.repositoryId,
                    updates: updates,
                });
            } else {
                resetCreate();
                createRepositoryMutation(submissionData);
            }
        }
    }

    useEffect(() => {
        const parsedValue = _.mergeWith({}, initialForm, props.selectedItems[0], (a: RagRepositoryConfig, b: RagRepositoryConfig) => b === null ? a : undefined);

        // Convert old chunkSize/chunkOverlap fields to new chunkingStrategy structure
        if (parsedValue.pipelines) {
            parsedValue.pipelines = parsedValue.pipelines.map((pipeline: any) => {
                // If old fields exist but no chunkingStrategy, create one
                if ((pipeline.chunkSize !== undefined || pipeline.chunkOverlap !== undefined) && !pipeline.chunkingStrategy) {
                    return {
                        ...pipeline,
                        chunkingStrategy: {
                            type: 'fixed' as const,
                            size: pipeline.chunkSize || 512,
                            overlap: pipeline.chunkOverlap || 51,
                        },
                    };
                }
                return pipeline;
            });
        }

        if (props.isEdit) {
            setState({ ...state, form: { ...parsedValue } });
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [props.isEdit]);

    useEffect(() => {
        if (!isCreating && isCreateSuccess) {
            notificationService.generateNotification(`Successfully created repository: ${state.form.repositoryId}`, 'success');
            setVisible(false);
            setIsEdit(false);
            resetState();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isCreating, isCreateSuccess]);

    useEffect(() => {
        if (!isUpdating && isUpdateSuccess) {
            notificationService.generateNotification(`Successfully updated repository: ${state.form.repositoryId}`, 'success');
            setVisible(false);
            setIsEdit(false);
            resetState();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isUpdating, isUpdateSuccess]);

    const steps = [
        {
            title: 'Repository Configuration',
            description: 'Define your repository\'s configuration',
            content: (
                <RepositoryConfigForm item={state.form} setFields={setFields} touchFields={touchFields}
                    formErrors={errors}
                    isEdit={isEdit} />
            ),
            onEdit: true,
        },
        {
            title: 'Pipeline Configuration',
            description: 'Create document ingestion pipelines from S3',
            content: (
                <PipelineConfigForm
                    item={state.form.pipelines}
                    setFields={setFields}
                    touchFields={touchFields}
                    formErrors={errors}
                    isEdit={isEdit}
                    repositoryId={state.form.repositoryId}
                    repositoryType={state.form.type} />
            ),
            isOptional: true,
            onEdit: true,
        },
        {
            title: `Review and ${isEdit ? 'Update' : 'Create'}`,
            description: `Review configuration ${isEdit ? 'changes' : ''} prior to submitting.`,
            content: (
                <ReviewChanges jsonDiff={changesDiff} error={reviewError}
                    info={isEdit ? 'Any changes will cause a redeployment of the vector store, which may result in data loss of previously store RAG documents.' : undefined} />
            ),
            onEdit: state.form,
        },
    ].filter((step) => isEdit ? step.onEdit : true);

    function resetState() {
        setState({
            validateAll: false as boolean,
            touched: {},
            formSubmitting: false as boolean,
            form: {
                ...initialForm,
            },
            activeStepIndex: 0,
        }, ModifyMethod.Set);
        resetCreate();
        resetUpdate();
    }

    return (
        <Modal size={'large'} onDismiss={() => {
            dispatch(
                setConfirmationModal({
                    action: 'Discard',
                    resourceName: 'Model Creation',
                    onConfirm: () => {
                        setVisible(false);
                        setIsEdit(false);
                        resetState();
                    },
                    description: 'Are you sure you want to discard your changes?',
                }));
        }} visible={visible} header={`${isEdit ? 'Update' : 'Create'} Repository`}>
            <Wizard
                i18nStrings={{
                    stepNumberLabel: (stepNumber) => `Step ${stepNumber}`,
                    collapsedStepsLabel: (stepNumber, stepsCount) => `Step ${stepNumber} of ${stepsCount}`,
                    skipToButtonLabel: () => `Skip to ${isEdit ? 'Update' : 'Create'}`,
                    navigationAriaLabel: 'Steps',
                    cancelButton: 'Cancel',
                    previousButton: 'Previous',
                    nextButton: 'Next',
                    optional: 'Optional',
                }}
                submitButtonText={isEdit ? 'Update Repository' : 'Create Repository'}
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
                        case 'skip': {
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
                            resourceName: 'Repository Creation',
                            onConfirm: () => {
                                setVisible(false);
                                setIsEdit(false);
                                resetState();
                            },
                            description: 'Are you sure you want to discard your changes?',
                        }));
                }}
                onSubmit={() => handleSubmit()}
                activeStepIndex={state.activeStepIndex}
                isLoadingNextStep={isCreating || isUpdating}
                allowSkipTo
                steps={steps}
            />
        </Modal>
    );
}

export default CreateRepositoryModal;

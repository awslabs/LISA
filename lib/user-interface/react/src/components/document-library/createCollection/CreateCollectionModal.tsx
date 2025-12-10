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
import { scrollToInvalid, useValidationReducer } from '@/shared/validation';
import { useAppDispatch } from '@/config/store';
import { useNotificationService } from '@/shared/util/hooks';
import { setConfirmationModal } from '@/shared/reducers/modal.reducer';
import {
    useCreateCollectionMutation,
    useUpdateCollectionMutation,
    useListRagRepositoriesQuery,
} from '@/shared/reducers/rag.reducer';
import { CollectionConfigForm } from './CollectionConfigForm';
import { ChunkingConfigForm } from './ChunkingConfigForm';
import { AccessControlForm } from './AccessControlForm';
import { ReviewChanges } from '@/shared/modal/ReviewChanges';
import { getJsonDifference, normalizeError } from '@/shared/util/validationUtils';
import { ModifyMethod } from '@/shared/validation/modify-method';
import _ from 'lodash';
import {
    RagCollectionConfig,
    RagCollectionConfigSchema,
    ChunkingStrategyType,
    RagRepositoryType,
} from '#root/lib/schema';

export type CreateCollectionModalProps = {
    visible: boolean;
    isEdit: boolean;
    setIsEdit: (isEdit: boolean) => void;
    setVisible: (isVisible: boolean) => void;
    selectedItems: ReadonlyArray<RagCollectionConfig>;
    setSelectedItems: (items: ReadonlyArray<RagCollectionConfig>) => void;
};

export type CollectionCreateState = {
    validateAll: boolean;
    form: RagCollectionConfig;
    touched: any;
    formSubmitting: boolean;
    activeStepIndex: number;
};

export function CreateCollectionModal (props: CreateCollectionModalProps): ReactElement {
    const { visible, setVisible, selectedItems, isEdit, setIsEdit } = props;

    // Fetch repositories to determine repository type
    const { data: repositories } = useListRagRepositoriesQuery();

    // Mutations
    const [
        createCollection,
        {
            isSuccess: isCreateSuccess,
            error: createError,
            isLoading: isCreating,
            reset: resetCreate,
        },
    ] = useCreateCollectionMutation();

    const [
        updateCollection,
        {
            isSuccess: isUpdateSuccess,
            error: updateError,
            isLoading: isUpdating,
            reset: resetUpdate,
        },
    ] = useUpdateCollectionMutation();

    const initialForm: RagCollectionConfig = {
        repositoryId: '',
        name: '',
        description: '',
        embeddingModel: '',
        chunkingStrategy: {
            type: ChunkingStrategyType.FIXED,
            size: 512,
            overlap: 50,
        },
        allowedGroups: [],
        metadata: { tags: [], customFields: {} },
        allowChunkingOverride: true,
    };

    const dispatch = useAppDispatch();
    const notificationService = useNotificationService(dispatch);

    // Validation reducer
    const {
        state,
        setState,
        setFields,
        touchFields,
        errors,
        isValid,
    } = useValidationReducer(RagCollectionConfigSchema, {
        validateAll: false as boolean,
        touched: {},
        formSubmitting: false as boolean,
        form: {
            ...initialForm,
        },
        activeStepIndex: 0,
    } as CollectionCreateState);

    const toSubmit = {
        ...state.form,
    };

    const changesDiff = useMemo(() => {
        if (isEdit && selectedItems.length > 0) {
            // Only compare editable fields to avoid showing undefined values
            const originalEditableFields = {
                repositoryId: selectedItems[0].repositoryId,
                name: selectedItems[0].name || '',
                description: selectedItems[0].description || '',
                embeddingModel: selectedItems[0].embeddingModel,
                chunkingStrategy: selectedItems[0].chunkingStrategy,
                allowedGroups: selectedItems[0].allowedGroups || [],
                metadata: selectedItems[0].metadata || { tags: [], customFields: {} },
                allowChunkingOverride: selectedItems[0].allowChunkingOverride !== undefined
                    ? selectedItems[0].allowChunkingOverride
                    : true,
            };
            return getJsonDifference(originalEditableFields, toSubmit);
        }
        return getJsonDifference({}, toSubmit);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [toSubmit, initialForm, isEdit]);

    const reviewError = normalizeError('Collection', isEdit ? updateError : createError);

    // Check if editing a Bedrock collection
    const selectedRepository = repositories?.find((repo) => repo.repositoryId === state.form.repositoryId);
    const isBedrockRepository = selectedRepository?.type === RagRepositoryType.BEDROCK_KNOWLEDGE_BASE;
    const disableChunking = isEdit && isBedrockRepository;

    const requiredFields = [
        ['name', 'repositoryId', 'embeddingModel'], // Step 1: Collection Configuration
        [], // Step 2: Chunking Configuration (optional)
        [], // Step 3: Access Control (optional)
    ];

    function handleSubmit () {
        if (isValid && !_.isEmpty(changesDiff)) {
            if (isEdit && selectedItems.length > 0) {
                resetUpdate();
                updateCollection({
                    repositoryId: selectedItems[0].repositoryId,
                    collectionId: selectedItems[0].collectionId,
                    name: toSubmit.name,
                    description: toSubmit.description,
                    chunkingStrategy: toSubmit.chunkingStrategy,
                    allowedGroups: toSubmit.allowedGroups,
                    metadata: toSubmit.metadata,
                    allowChunkingOverride: toSubmit.allowChunkingOverride,
                });
            } else {
                resetCreate();
                createCollection({
                    repositoryId: toSubmit.repositoryId,
                    name: toSubmit.name,
                    description: toSubmit.description,
                    embeddingModel: toSubmit.embeddingModel,
                    chunkingStrategy: toSubmit.chunkingStrategy,
                    allowedGroups: toSubmit.allowedGroups,
                    metadata: toSubmit.metadata,
                    allowChunkingOverride: toSubmit.allowChunkingOverride,
                });
            }
        }
    }

    // Pre-populate form in edit mode
    useEffect(() => {
        if (isEdit && selectedItems.length > 0) {
            const selectedCollection = selectedItems[0];
            setState({
                ...state,
                form: {
                    repositoryId: selectedCollection.repositoryId,
                    name: selectedCollection.name || '',
                    description: selectedCollection.description || '',
                    embeddingModel: selectedCollection.embeddingModel,
                    chunkingStrategy: selectedCollection.chunkingStrategy,
                    allowedGroups: selectedCollection.allowedGroups || [],
                    metadata: selectedCollection.metadata || { tags: [], customFields: {} },
                    allowChunkingOverride: selectedCollection.allowChunkingOverride !== undefined
                        ? selectedCollection.allowChunkingOverride
                        : true,
                },
            });
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isEdit, selectedItems]);

    // Success handling
    useEffect(() => {
        if (!isCreating && !isUpdating && (isCreateSuccess || isUpdateSuccess)) {
            notificationService.generateNotification(
                `Successfully ${isEdit ? 'updated' : 'created'} collection: ${state.form.name}`,
                'success'
            );
            setVisible(false);
            setIsEdit(false);
            resetState();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isCreating, isUpdating, isCreateSuccess, isUpdateSuccess]);

    // Wizard steps configuration
    const steps = [
        {
            title: 'Collection Configuration',
            description: 'Repositories can have many collections. Use collections to organize or restrict information.',
            content: (
                <CollectionConfigForm
                    item={state.form}
                    setFields={setFields}
                    touchFields={touchFields}
                    formErrors={errors}
                    isEdit={isEdit}
                />
            ),
        },
        {
            title: 'Chunking Configuration',
            description: disableChunking
                ? 'Chunking is managed by Bedrock Knowledge Base and cannot be modified'
                : 'Configure how documents are split into chunks',
            content: (
                <ChunkingConfigForm
                    item={state.form.chunkingStrategy}
                    setFields={setFields}
                    touchFields={touchFields}
                    formErrors={errors}
                    disabled={disableChunking}
                />
            ),
            isOptional: true,
        },
        {
            title: 'Access Control',
            description: 'Configure user group access permissions',
            content: (
                <AccessControlForm
                    item={state.form}
                    setFields={setFields}
                    touchFields={touchFields}
                    formErrors={errors}
                />
            ),
            isOptional: true,
        },
        {
            title: `Review and ${isEdit ? 'Update' : 'Create'}`,
            description: `Review configuration ${isEdit ? 'changes' : ''} prior to submitting`,
            content: (
                <ReviewChanges
                    jsonDiff={changesDiff}
                    error={reviewError}
                    info={isEdit && _.isEmpty(changesDiff) ? 'No changes detected. Modify the collection configuration to enable submission.' : undefined}
                />
            ),
            isOptional: false,
        },
    ];

    function resetState () {
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

    function handleDismiss () {
        dispatch(
            setConfirmationModal({
                action: 'Discard',
                resourceName: 'Collection Creation',
                onConfirm: () => {
                    setVisible(false);
                    setIsEdit(false);
                    resetState();
                },
                description: 'Are you sure you want to discard your changes?',
            })
        );
    }

    function handleCancel () {
        dispatch(
            setConfirmationModal({
                action: 'Discard',
                resourceName: 'Collection Creation',
                onConfirm: () => {
                    setVisible(false);
                    setIsEdit(false);
                    resetState();
                },
                description: 'Are you sure you want to discard your changes?',
            })
        );
    }

    function handleNavigate (event: any) {
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
    }

    return (
        <Modal
            size='large'
            onDismiss={handleDismiss}
            visible={visible}
            header={`${isEdit ? 'Update' : 'Create'} Collection`}
        >
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
                submitButtonText={isEdit ? 'Update Collection' : 'Create Collection'}
                onNavigate={handleNavigate}
                onCancel={handleCancel}
                onSubmit={handleSubmit}
                activeStepIndex={state.activeStepIndex}
                isLoadingNextStep={isCreating || isUpdating}
                allowSkipTo
                steps={steps}
            />
        </Modal>
    );
}

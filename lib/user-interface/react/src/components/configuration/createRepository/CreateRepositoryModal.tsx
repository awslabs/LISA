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
import { useCreateRagRepositoryMutation } from '../../../shared/reducers/rag.reducer';
import { getDefaults } from '../../../shared/util/zodUtil';
import { RagRepositoryConfig, RagRepositoryConfigSchema } from '../../../../../../configSchema';
import { RepositoryConfigForm } from './RepositoryConfigForm';
import { ReviewChanges } from '../../../shared/modal/ReviewChanges';
import { getJsonDifference, normalizeError } from '../../../shared/util/validationUtils';
import { ModifyMethod } from '../../../shared/validation/modify-method';
import { PipelineConfigForm } from './PipelineConfigForm';
import _ from 'lodash';

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

export function CreateRepositoryModal (props: CreateRepositoryModalProps): ReactElement {
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

    const initialForm: RagRepositoryConfig = {
        ...getDefaults(RagRepositoryConfigSchema),
    };
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

    const reviewError = normalizeError('Repository', createError);

    const requiredFields = [['repositoryId', 'type', 'rdsConfig.username', 'rdsConfig.dbName', 'rdsConfig.dbPort', 'opensearchConfig.dataNodes', 'opensearchConfig.dataNodes', 'opensearchConfig.dataNodeInstanceType'], []];


    function handleSubmit () {
        if (isValid && !_.isEmpty(changesDiff)) {
            resetCreate();
            createRepositoryMutation({ ragConfig: toSubmit });
        }
    }

    useEffect(() => {
        const parsedValue = _.mergeWith({}, initialForm, props.selectedItems[0], (a: RagRepositoryConfig, b: RagRepositoryConfig) => b === null ? a : undefined);
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

    const steps = [
        {
            title: 'Repository Configuration',
            description: 'Define your repository\'s configuration settings using these forms.',
            content: (
                <RepositoryConfigForm item={state.form} setFields={setFields} touchFields={touchFields}
                    formErrors={errors}
                    isEdit={isEdit} />
            ),
            onEdit: true,
        },
        {
            title: 'Pipeline Configuration',
            description: 'Create pipelines for ingesting RAG documents from S3',
            content: (
                <PipelineConfigForm item={state.form.pipelines} setFields={setFields} touchFields={touchFields}
                    formErrors={errors} isEdit={isEdit} />
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
    }

    return (
        <Modal size={'large'} onDismiss={() => {
            dispatch(
                setConfirmationModal({
                    action: 'Abandon',
                    resourceName: 'Model Creation',
                    onConfirm: () => {
                        setVisible(false);
                        setIsEdit(false);
                        resetState();
                    },
                    description: 'Are you sure you want to abandon your changes?',
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
                            action: 'Abandon',
                            resourceName: 'Repository Creation',
                            onConfirm: () => {
                                setVisible(false);
                                setIsEdit(false);
                                resetState();
                            },
                            description: 'Are you sure you want to abandon your changes?',
                        }));
                }}
                onSubmit={() => handleSubmit()}
                activeStepIndex={state.activeStepIndex}
                isLoadingNextStep={isCreating}
                allowSkipTo
                steps={steps}
            />
        </Modal>
    );
}

export default CreateRepositoryModal;

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

import { ReactElement, useState } from 'react';
import {
    Modal,
    Wizard,
    FormField,
    Input,
    DatePicker,
    SpaceBetween,
    Container,
    Box,
    TokenGroup,
    Button,
    Toggle,
} from '@cloudscape-design/components';
import { ICreateTokenRequest, ICreateTokenResponse } from '../../shared/model/api-token.model';
import { useCreateTokenForUserMutation } from '../../shared/reducers/api-token.reducer';
import { useAppDispatch } from '../../config/store';
import { useNotificationService } from '../../shared/util/hooks';
import { setConfirmationModal } from '../../shared/reducers/modal.reducer';

export type CreateTokenWizardProps = {
    visible: boolean;
    setVisible: (visible: boolean) => void;
    onTokenCreated: (token: ICreateTokenResponse) => void;
};

type FormData = {
    username: string;
    tokenName: string;
    isSystemToken: boolean;
    groups: string[];
    expirationDate: string;
};

export function CreateTokenWizard ({ visible, setVisible, onTokenCreated }: CreateTokenWizardProps): ReactElement {
    const dispatch = useAppDispatch();
    const notificationService = useNotificationService(dispatch);
    const [createToken, { isLoading, isError, error, reset }] = useCreateTokenForUserMutation();

    // Calculate default expiration (90 days from now)
    const getDefaultExpiration = () => {
        const date = new Date();
        date.setDate(date.getDate() + 90);
        return date.toISOString().split('T')[0];
    };

    const [activeStepIndex, setActiveStepIndex] = useState(0);
    const [formData, setFormData] = useState<FormData>(() => ({
        username: '',
        tokenName: '',
        isSystemToken: false,
        groups: [],
        expirationDate: getDefaultExpiration(),
    }));
    const [groupInput, setGroupInput] = useState('');
    const [errors, setErrors] = useState<Record<string, string>>({});

    const validateStep = (stepIndex: number): boolean => {
        const newErrors: Record<string, string> = {};

        if (stepIndex === 0) {
            if (!formData.username.trim()) {
                newErrors.username = 'Username is required';
            }
            if (!formData.tokenName.trim()) {
                newErrors.tokenName = 'Token name is required';
            }
        }

        if (stepIndex === 1) {
            if (!formData.expirationDate) {
                newErrors.expirationDate = 'Expiration date is required';
            } else {
                const selectedDate = new Date(formData.expirationDate);
                const today = new Date();
                today.setHours(0, 0, 0, 0);
                if (selectedDate <= today) {
                    newErrors.expirationDate = 'Expiration date must be in the future';
                }
            }
        }

        setErrors(newErrors);
        return Object.keys(newErrors).length === 0;
    };

    const handleSubmit = async () => {
        if (!validateStep(2)) return;

        const expirationTimestamp = Math.floor(new Date(formData.expirationDate).getTime() / 1000);

        const request: ICreateTokenRequest = {
            name: formData.tokenName,
            groups: formData.groups,
            isSystemToken: formData.isSystemToken,
            tokenExpiration: expirationTimestamp,
        };

        try {
            const result = await createToken({ username: formData.username, request }).unwrap();
            notificationService.generateNotification(
                `Successfully created token "${formData.tokenName}" for user "${formData.username}"`,
                'success'
            );
            onTokenCreated(result);
            setVisible(false);
            resetState();
        } catch {
            notificationService.generateNotification(
                `Failed to create token: ${error ? (error as any).message : 'Unknown error'}`,
                'error'
            );
        }
    };

    function resetState () {
        setActiveStepIndex(0);
        setFormData({
            username: '',
            tokenName: '',
            isSystemToken: false,
            groups: [],
            expirationDate: getDefaultExpiration(),
        });
        setGroupInput('');
        setErrors({});
        reset();
    }

    function handleDismiss () {
        dispatch(
            setConfirmationModal({
                action: 'Discard',
                resourceName: 'Token Creation',
                onConfirm: () => {
                    setVisible(false);
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
                resourceName: 'Token Creation',
                onConfirm: () => {
                    setVisible(false);
                    resetState();
                },
                description: 'Are you sure you want to discard your changes?',
            })
        );
    }

    const addGroup = () => {
        if (groupInput.trim() && !formData.groups.includes(groupInput.trim())) {
            setFormData((prev) => ({
                ...prev,
                groups: [...prev.groups, groupInput.trim()]
            }));
            setGroupInput('');
        }
    };

    const removeGroup = (groupToRemove: string) => {
        setFormData((prev) => ({
            ...prev,
            groups: prev.groups.filter((g) => g !== groupToRemove)
        }));
    };

    return (
        <Modal
            visible={visible}
            onDismiss={handleDismiss}
            size='large'
            header='Create API Token'
        >
            <Wizard
                i18nStrings={{
                    stepNumberLabel: (stepNumber) => `Step ${stepNumber}`,
                    collapsedStepsLabel: (stepNumber, stepsCount) => `Step ${stepNumber} of ${stepsCount}`,
                    skipToButtonLabel: () => 'Skip to Review',
                    navigationAriaLabel: 'Steps',
                    cancelButton: 'Cancel',
                    previousButton: 'Previous',
                    nextButton: 'Next',
                    submitButton: 'Create Token',
                    optional: 'optional',
                }}
                onNavigate={({ detail }) => {
                    const currentStep = activeStepIndex;
                    if (detail.requestedStepIndex > currentStep) {
                        if (validateStep(currentStep)) {
                            setActiveStepIndex(detail.requestedStepIndex);
                        }
                    } else {
                        setActiveStepIndex(detail.requestedStepIndex);
                    }
                }}
                onCancel={handleCancel}
                onSubmit={handleSubmit}
                activeStepIndex={activeStepIndex}
                isLoadingNextStep={isLoading}
                steps={[
                    {
                        title: 'Basic Information',
                        description: 'Specify the user and token name',
                        content: (
                            <Container>
                                <SpaceBetween size='l'>
                                    <FormField
                                        label='Username'
                                        description='The username this token will be created for'
                                        errorText={errors.username}
                                        constraintText='Enter the username (e.g., jdoe)'
                                    >
                                        <Input
                                            value={formData.username}
                                            onChange={({ detail }) => setFormData((prev) => ({ ...prev, username: detail.value }))}
                                            placeholder='Enter username'
                                        />
                                    </FormField>

                                    <FormField
                                        label='Token Name'
                                        description='A descriptive name for this token'
                                        errorText={errors.tokenName}
                                        constraintText='Enter a meaningful name to identify this token'
                                    >
                                        <Input
                                            value={formData.tokenName}
                                            onChange={({ detail }) => setFormData((prev) => ({ ...prev, tokenName: detail.value }))}
                                            placeholder='e.g., CI/CD Pipeline Token'
                                        />
                                    </FormField>

                                    <FormField
                                        label='System Token'
                                        description='System tokens allow multiple tokens per user'
                                    >
                                        <Toggle
                                            checked={formData.isSystemToken}
                                            onChange={({ detail }) => setFormData((prev) => ({ ...prev, isSystemToken: detail.checked }))}
                                        >
                                        </Toggle>
                                    </FormField>
                                </SpaceBetween>
                            </Container>
                        ),
                    },
                    {
                        title: 'Permissions',
                        description: 'Configure token permissions and expiration',
                        content: (
                            <Container>
                                <SpaceBetween size='l'>
                                    <FormField
                                        label='Groups'
                                        description='Assign groups to this token for access control'
                                    >
                                        <SpaceBetween size='xs'>
                                            <SpaceBetween direction='vertical' size='xs'>
                                                {formData.groups.length > 0 && (
                                                    <TokenGroup
                                                        items={formData.groups.map((group) => ({ label: group, dismissLabel: `Remove ${group}` }))}
                                                        onDismiss={({ detail }) => removeGroup(detail.itemIndex !== undefined ? formData.groups[detail.itemIndex] : '')}
                                                    />
                                                )}
                                                <Input
                                                    value={groupInput}
                                                    onChange={({ detail }) => setGroupInput(detail.value)}
                                                    placeholder='Enter group name'
                                                    onKeyDown={(e) => {
                                                        if (e.detail.key === 'Enter') {
                                                            e.preventDefault();
                                                            addGroup();
                                                        }
                                                    }}
                                                />
                                                <Button onClick={addGroup}>Add</Button>
                                            </SpaceBetween>
                                        </SpaceBetween>
                                    </FormField>

                                    <FormField
                                        label='Expiration Date'
                                        description='When this token will expire'
                                        errorText={errors.expirationDate}
                                        constraintText='Default is 90 days from today'
                                    >
                                        <DatePicker
                                            value={formData.expirationDate}
                                            onChange={({ detail }) => setFormData((prev) => ({ ...prev, expirationDate: detail.value }))}
                                            placeholder='YYYY-MM-DD'
                                            openCalendarAriaLabel={(selectedDate) =>
                                                'Choose expiration date' + (selectedDate ? `, selected date is ${selectedDate}` : '')
                                            }
                                        />
                                    </FormField>
                                </SpaceBetween>
                            </Container>
                        ),
                    },
                    {
                        title: 'Review and Create',
                        description: 'Review token details before creation',
                        content: (
                            <Container>
                                <SpaceBetween size='l'>
                                    <div>
                                        <Box variant='awsui-key-label'>Username</Box>
                                        <div>{formData.username}</div>
                                    </div>
                                    <div>
                                        <Box variant='awsui-key-label'>Token Name</Box>
                                        <div>{formData.tokenName}</div>
                                    </div>
                                    <div>
                                        <Box variant='awsui-key-label'>System Token</Box>
                                        <div>{formData.isSystemToken ? 'Yes' : 'No'}</div>
                                    </div>
                                    <div>
                                        <Box variant='awsui-key-label'>Groups</Box>
                                        <div>{formData.groups.length > 0 ? formData.groups.join(', ') : 'None'}</div>
                                    </div>
                                    <div>
                                        <Box variant='awsui-key-label'>Expiration Date</Box>
                                        <div>{new Date(formData.expirationDate).toLocaleDateString()}</div>
                                    </div>
                                    {isError && error && (
                                        <Box color='text-status-error'>
                                            Error: {(error as any).message || 'Failed to create token'}
                                        </Box>
                                    )}
                                </SpaceBetween>
                            </Container>
                        ),
                    },
                ]}
            />
        </Modal>
    );
}

export default CreateTokenWizard;

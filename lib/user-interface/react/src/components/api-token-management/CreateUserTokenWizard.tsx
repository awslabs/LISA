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
    Box,
    SpaceBetween,
    Button,
    FormField,
    Input,
    Container,
    Header,
    DatePicker,
    Alert,
} from '@cloudscape-design/components';
import { ICreateTokenResponse } from '../../shared/model/api-token.model';
import { useCreateOwnTokenMutation } from '../../shared/reducers/api-token.reducer';
import { useAppDispatch } from '../../config/store';
import { useNotificationService } from '../../shared/util/hooks';

export type CreateUserTokenWizardProps = {
    visible: boolean;
    setVisible: (visible: boolean) => void;
    onTokenCreated: (token: ICreateTokenResponse) => void;
};

// Helper to get default expiration (90 days from now)
const getDefaultExpiration = () => {
    const date = new Date();
    date.setDate(date.getDate() + 90);
    return date.toISOString().split('T')[0];
};

export function CreateUserTokenWizard ({ visible, setVisible, onTokenCreated }: CreateUserTokenWizardProps): ReactElement {
    const dispatch = useAppDispatch();
    const notificationService = useNotificationService(dispatch);
    const [createToken, { isLoading }] = useCreateOwnTokenMutation();

    const [tokenName, setTokenName] = useState('');
    const [expirationDate, setExpirationDate] = useState(getDefaultExpiration());
    const [errors, setErrors] = useState<{ tokenName?: string; expirationDate?: string }>({});

    const validateForm = (): boolean => {
        const newErrors: { tokenName?: string; expirationDate?: string } = {};

        if (!tokenName.trim()) {
            newErrors.tokenName = 'Token name is required';
        }

        if (!expirationDate) {
            newErrors.expirationDate = 'Expiration date is required';
        } else {
            const selectedDate = new Date(expirationDate);
            const today = new Date();
            today.setHours(0, 0, 0, 0);
            if (selectedDate <= today) {
                newErrors.expirationDate = 'Expiration date must be in the future';
            }
        }

        setErrors(newErrors);
        return Object.keys(newErrors).length === 0;
    };

    const handleSubmit = async () => {
        if (!validateForm()) {
            return;
        }

        const expirationTimestamp = Math.floor(new Date(expirationDate).getTime() / 1000);

        try {
            const result = await createToken({
                name: tokenName,
                tokenExpiration: expirationTimestamp
            }).unwrap();
            notificationService.generateNotification(
                `Successfully created token "${tokenName}"`,
                'success'
            );
            onTokenCreated(result);
            setVisible(false);
            resetState();
        } catch (err: any) {
            notificationService.generateNotification(
                `Failed to create token: ${err.message || 'Unknown error'}`,
                'error'
            );
        }
    };

    function resetState () {
        setTokenName('');
        setExpirationDate(getDefaultExpiration());
        setErrors({});
    }

    function handleDismiss () {
        if (tokenName.trim()) {
            // Only confirm if there's unsaved data
            if (window.confirm('Are you sure you want to discard your changes?')) {
                setVisible(false);
                resetState();
            }
        } else {
            setVisible(false);
            resetState();
        }
    }

    return (
        <Modal
            visible={visible}
            onDismiss={handleDismiss}
            size='medium'
            header='Create Your API Token'
            footer={
                <Box float='right'>
                    <SpaceBetween direction='horizontal' size='xs'>
                        <Button
                            variant='link'
                            onClick={handleDismiss}
                        >
                            Cancel
                        </Button>
                        <Button
                            variant='primary'
                            onClick={handleSubmit}
                            loading={isLoading}
                            disabled={!tokenName.trim()}
                        >
                            Create Token
                        </Button>
                    </SpaceBetween>
                </Box>
            }
        >
            <SpaceBetween size='l'>
                <Alert type='info' header='Note:'>
                    <p style={{ paddingTop: '10px' }}>
                        This token will be created with your current group memberships.
                    </p>
                </Alert>
                <Container header={<Header variant='h2'>Token Details</Header>}>
                    <SpaceBetween size='l'>
                        <FormField
                            label='Token Name'
                            description='A descriptive name to identify this token'
                            errorText={errors.tokenName}
                            constraintText='Enter a meaningful name (e.g., "My Development Token")'
                        >
                            <Input
                                value={tokenName}
                                onChange={({ detail }) => {
                                    setTokenName(detail.value);
                                    setErrors({ ...errors, tokenName: undefined });
                                }}
                                placeholder='e.g., My CI/CD Token'
                                autoFocus
                            />
                        </FormField>

                        <FormField
                            label='Expiration Date'
                            description='When this token will expire'
                            errorText={errors.expirationDate}
                            constraintText='Default is 90 days from today'
                        >
                            <DatePicker
                                value={expirationDate}
                                onChange={({ detail }) => {
                                    setExpirationDate(detail.value);
                                    setErrors({ ...errors, expirationDate: undefined });
                                }}
                                placeholder='YYYY-MM-DD'
                                openCalendarAriaLabel={(selectedDate) =>
                                    'Choose expiration date' + (selectedDate ? `, selected date is ${selectedDate}` : '')
                                }
                            />
                        </FormField>
                    </SpaceBetween>
                </Container>
            </SpaceBetween>
        </Modal>
    );
}

export default CreateUserTokenWizard;

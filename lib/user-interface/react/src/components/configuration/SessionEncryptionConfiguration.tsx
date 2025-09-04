/**
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License").
 * You may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import React, { ReactElement, useState, useEffect } from 'react';
import {
    Box,
    Button,
    Container,
    FormField,
    Header,
    SpaceBetween,
    Toggle,
    Alert,
    Spinner,
    StatusIndicator,
} from '@cloudscape-design/components';
import { useSessionEncryptionState } from '../../shared/util/sessionEncryption';
import { useNotificationService } from '../../shared/util/hooks';
import { useAppDispatch } from '../../config/store';

interface SessionEncryptionConfigurationProps {
    setFields: (fields: Record<string, any>) => void;
    encryptionEnabled: boolean;
    touchFields: (fields: string[]) => void;
    errors: Record<string, string>;
}

export function SessionEncryptionConfiguration({
    setFields,
    encryptionEnabled,
    touchFields,
    errors,
}: SessionEncryptionConfigurationProps): ReactElement {
    const dispatch = useAppDispatch();
    const notificationService = useNotificationService(dispatch);
    const { encryptionEnabled: currentEncryptionEnabled, migrationInProgress, toggleEncryption } = useSessionEncryptionState();
    const [isLoading, setIsLoading] = useState(false);
    const [showMigrationWarning, setShowMigrationWarning] = useState(false);

    useEffect(() => {
        setFields({ sessionEncryption: { enabled: currentEncryptionEnabled } });
    }, [currentEncryptionEnabled, setFields]);

    const handleEncryptionToggle = async (enabled: boolean) => {
        setIsLoading(true);
        try {
            if (enabled && !currentEncryptionEnabled) {
                // Show migration warning when enabling encryption
                setShowMigrationWarning(true);
            } else {
                await toggleEncryption(enabled);
                notificationService.addNotification({
                    type: 'success',
                    content: `Session encryption ${enabled ? 'enabled' : 'disabled'} successfully`,
                });
            }
        } catch (error) {
            console.error('Error toggling encryption:', error);
            notificationService.addNotification({
                type: 'error',
                content: `Failed to ${enabled ? 'enable' : 'disable'} session encryption`,
            });
        } finally {
            setIsLoading(false);
        }
    };

    const handleConfirmMigration = async () => {
        setIsLoading(true);
        try {
            await toggleEncryption(true);
            setShowMigrationWarning(false);
            notificationService.addNotification({
                type: 'success',
                content: 'Session encryption enabled successfully. Existing sessions will be encrypted when accessed.',
            });
        } catch (error) {
            console.error('Error enabling encryption:', error);
            notificationService.addNotification({
                type: 'error',
                content: 'Failed to enable session encryption',
            });
        } finally {
            setIsLoading(false);
        }
    };

    const handleCancelMigration = () => {
        setShowMigrationWarning(false);
    };

    return (
        <Container
            header={
                <Header
                    variant="h2"
                    description="Configure session data encryption at rest"
                >
                    Session Encryption
                </Header>
            }
        >
            <SpaceBetween size="m">
                {showMigrationWarning && (
                    <Alert
                        type="warning"
                        dismissible
                        onDismiss={handleCancelMigration}
                        header="Enable Session Encryption"
                    >
                        <SpaceBetween size="s">
                            <Box>
                                Enabling session encryption will encrypt all new session data at rest in DynamoDB.
                                Existing sessions will be encrypted when they are next accessed or updated.
                            </Box>
                            <Box>
                                <strong>Important:</strong> This action cannot be easily undone. Make sure you have
                                proper backup and recovery procedures in place.
                            </Box>
                            <SpaceBetween direction="horizontal" size="s">
                                <Button
                                    variant="primary"
                                    onClick={handleConfirmMigration}
                                    loading={isLoading || migrationInProgress}
                                >
                                    Enable Encryption
                                </Button>
                                <Button
                                    variant="normal"
                                    onClick={handleCancelMigration}
                                    disabled={isLoading || migrationInProgress}
                                >
                                    Cancel
                                </Button>
                            </SpaceBetween>
                        </SpaceBetween>
                    </Alert>
                )}

                <FormField
                    label="Session Data Encryption"
                    description="Encrypt session data at rest in DynamoDB to prevent unauthorized access"
                    errorText={errors.sessionEncryption?.enabled}
                >
                    <SpaceBetween direction="horizontal" size="s">
                        <Toggle
                            checked={currentEncryptionEnabled}
                            onChange={({ detail }) => {
                                touchFields(['sessionEncryption.enabled']);
                                handleEncryptionToggle(detail.checked);
                            }}
                            disabled={isLoading || migrationInProgress}
                        >
                            {currentEncryptionEnabled ? 'Enabled' : 'Disabled'}
                        </Toggle>
                        {(isLoading || migrationInProgress) && <Spinner size="normal" />}
                        {!isLoading && !migrationInProgress && (
                            <StatusIndicator
                                type={currentEncryptionEnabled ? 'success' : 'stopped'}
                            >
                                {currentEncryptionEnabled ? 'Active' : 'Inactive'}
                            </StatusIndicator>
                        )}
                    </SpaceBetween>
                </FormField>

                {currentEncryptionEnabled && (
                    <Box>
                        <Header variant="h3">Encryption Details</Header>
                        <SpaceBetween size="s">
                            <Box>
                                <strong>Encryption Method:</strong> AWS KMS with envelope encryption
                            </Box>
                            <Box>
                                <strong>Algorithm:</strong> AES-256-GCM
                            </Box>
                            <Box>
                                <strong>Key Management:</strong> Customer-managed KMS key with automatic rotation
                            </Box>
                            <Box>
                                <strong>Encrypted Fields:</strong> Session history and configuration data
                            </Box>
                        </SpaceBetween>
                    </Box>
                )}

                {!currentEncryptionEnabled && (
                    <Alert type="info" header="Session Data Security">
                        <Box>
                            When disabled, session data is stored in DynamoDB with AWS-managed encryption at rest.
                            However, users with console access can still view session content. Enable encryption
                            for additional security and compliance requirements.
                        </Box>
                    </Alert>
                )}
            </SpaceBetween>
        </Container>
    );
}

export default SessionEncryptionConfiguration;

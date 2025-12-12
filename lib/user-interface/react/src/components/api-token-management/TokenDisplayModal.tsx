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
    SpaceBetween,
    Box,
    Button,
    Alert,
    Container,
    Header,
    Checkbox,
} from '@cloudscape-design/components';
import { ICreateTokenResponse } from '../../shared/model/api-token.model';

export type TokenDisplayModalProps = {
    visible: boolean;
    token: ICreateTokenResponse | null;
    onDismiss: () => void;
};

export function TokenDisplayModal ({ visible, token, onDismiss }: TokenDisplayModalProps): ReactElement {
    const [acknowledged, setAcknowledged] = useState(false);
    const [copied, setCopied] = useState(false);

    const handleCopy = async () => {
        if (!token) return;
        try {
            await navigator.clipboard.writeText(token.token);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch (err) {
            console.error('Failed to copy token:', err);
        }
    };

    const handleClose = () => {
        setAcknowledged(false);
        setCopied(false);
        onDismiss();
    };

    const downloadToken = () => {
        if (!token) return;

        const element = document.createElement('a');
        const file = new Blob([token.token], { type: 'text/plain' });
        element.href = URL.createObjectURL(file);
        element.download = `lisa-api-token-${token.createdFor}-${Date.now()}.txt`;
        document.body.appendChild(element);
        element.click();
        document.body.removeChild(element);
    };

    if (!token) return <></>;

    return (
        <Modal
            visible={visible}
            onDismiss={() => {
                // Prevent closing by clicking outside or pressing ESC
                // User must acknowledge and click the Close button
            }}
            size='medium'
            header='API Token Created Successfully'
            footer={
                <Box float='right'>
                    <Button
                        variant='primary'
                        onClick={handleClose}
                        disabled={!acknowledged}
                    >
                        Close
                    </Button>
                </Box>
            }
        >
            <SpaceBetween size='l'>
                <Alert type='warning' header='Important: Save this token now'>
                    This is the <strong>only time</strong> you will be able to see this token.
                    It cannot be retrieved again. Make sure to copy and save it in a secure location
                    before closing this dialog.
                </Alert>

                <Container
                    header={
                        <Header
                            variant='h3'
                            actions={
                                <SpaceBetween direction='horizontal' size='xs'>
                                    <Button
                                        iconName='copy'
                                        onClick={handleCopy}
                                    >
                                        Copy to Clipboard
                                    </Button>
                                    <Button
                                        iconName='download'
                                        onClick={downloadToken}
                                    >
                                        Download
                                    </Button>
                                </SpaceBetween>
                            }
                        >
                            Your API Token
                        </Header>
                    }
                >
                    <Box
                        variant='code'
                        padding={{ vertical: 's', horizontal: 's' }}
                        fontSize='body-m'
                    >
                        <code style={{
                            wordBreak: 'break-all',
                            whiteSpace: 'pre-wrap',
                            fontFamily: 'monospace',
                            fontSize: '14px'
                        }}>
                            {token.token}
                        </code>
                    </Box>
                    {copied && (
                        <Box color='text-status-success' margin={{ top: 'xs' }}>
                            ✓ Token copied to clipboard
                        </Box>
                    )}
                </Container>

                <Container>
                    <SpaceBetween size='s'>
                        <Box variant='h4'>Token Details</Box>
                        <div>
                            <Box variant='awsui-key-label'>Token Name</Box>
                            <div>{token.name}</div>
                        </div>
                        <div>
                            <Box variant='awsui-key-label'>Created For</Box>
                            <div>{token.createdFor}</div>
                        </div>
                        <div>
                            <Box variant='awsui-key-label'>Groups</Box>
                            <div>{token.groups.length > 0 ? token.groups.join(', ') : 'None'}</div>
                        </div>
                        <div>
                            <Box variant='awsui-key-label'>Expiration</Box>
                            <div>{new Date(token.tokenExpiration * 1000).toLocaleString()}</div>
                        </div>
                        <div>
                            <Box variant='awsui-key-label'>System Token</Box>
                            <div>{token.isSystemToken ? 'Yes' : 'No'}</div>
                        </div>
                    </SpaceBetween>
                </Container>

                <Checkbox
                    checked={acknowledged}
                    onChange={({ detail }) => setAcknowledged(detail.checked)}
                >
                    I have securely saved this token
                </Checkbox>
            </SpaceBetween>
        </Modal>
    );
}

export default TokenDisplayModal;

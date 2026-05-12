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

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
    Box,
    Button,
    Container,
    Form,
    FormField,
    Header,
    Input,
    SpaceBetween,
    StatusIndicator,
    TextContent
} from '@cloudscape-design/components';
import { lisaAxios } from '@/shared/reducers/reducer.utils';
import { MCP_WORKBENCH_URI } from '@/components/utils';

type AwsStatusResponse = {
    connected: boolean;
    expiresAt?: string;
};

type ConnectResponse = {
    accountId: string;
    arn: string;
    expiresAt: string;
};

type AwsCredentialsPanelProps = {
    /** Optional hook for parent components to react when connection state changes */
    onStatusChange?: (status: AwsStatusResponse) => void;
    /** Optional session identifier to scope credentials per-session */
    sessionId?: string;
    /** Optional header title; defaults to "AWS Credentials" */
    title?: string;
};

const AwsCredentialsPanel: React.FC<AwsCredentialsPanelProps> = ({ onStatusChange, sessionId, title = 'AWS Credentials' }) => {
    const [accessKeyId, setAccessKeyId] = useState('');
    const [secretAccessKey, setSecretAccessKey] = useState('');
    const [sessionToken, setSessionToken] = useState('');
    const [region, setRegion] = useState(window.env?.AWS_REGION || 'us-east-1');

    const [status, setStatus] = useState<AwsStatusResponse | null>(null);
    const [accountId, setAccountId] = useState<string | null>(null);
    const [arn, setArn] = useState<string | null>(null);

    const [isLoadingStatus, setIsLoadingStatus] = useState(true);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [isDisconnecting, setIsDisconnecting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [now, setNow] = useState<number>(() => Date.now());

    useEffect(() => {
        if (!status?.connected || !status.expiresAt) return;
        const interval = setInterval(() => setNow(Date.now()), 30000);
        return () => clearInterval(interval);
    }, [status?.connected, status?.expiresAt]);

    const expiresInMinutes = useMemo(() => {
        if (!status?.connected || !status.expiresAt) return null;
        try {
            const expires = new Date(status.expiresAt).getTime();
            const diffMs = expires - now;
            if (diffMs <= 0) return 0;
            return Math.round(diffMs / 60000);
        } catch {
            return null;
        }
    }, [status, now]);

    const loadStatus = useCallback(async () => {
        try {
            const { data } = await lisaAxios.get<AwsStatusResponse>(`${MCP_WORKBENCH_URI}/api/aws/status`, {
                headers: sessionId ? { 'X-Session-Id': sessionId } : undefined,
            });
            setStatus(data);
            if (onStatusChange) onStatusChange(data);
        } catch (e: any) {
            setError(e.message ?? 'Failed to load AWS status');
        } finally {
            setIsLoadingStatus(false);
        }
    }, [sessionId, onStatusChange]);

    const [prevSessionId, setPrevSessionId] = useState(sessionId);
    if (sessionId !== prevSessionId) {
        setPrevSessionId(sessionId);
        setStatus(null);
        setAccountId(null);
        setArn(null);
        setError(null);
        setIsLoadingStatus(true);
    }

    useEffect(() => {
        // Data fetching on mount/prop-change: setState happens inside loadStatus only after
        // `await` (in promise continuations), which is the canonical effect pattern. The lint
        // is over-conservative here as it cannot distinguish post-await setState from sync.
        // eslint-disable-next-line react-hooks/set-state-in-effect
        void loadStatus();
    }, [loadStatus]);

    const handleConnect = async () => {
        setError(null);
        setIsSubmitting(true);
        try {
            const body = {
                accessKeyId: accessKeyId.trim(),
                secretAccessKey: secretAccessKey.trim(),
                sessionToken: sessionToken.trim() || undefined,
                region: region.trim()
            };
            const { data } = await lisaAxios.post<ConnectResponse>(`${MCP_WORKBENCH_URI}/api/aws/connect`, body, {
                headers: sessionId ? { 'X-Session-Id': sessionId } : undefined,
            });
            setAccountId(data.accountId);
            setArn(data.arn);
            const newStatus: AwsStatusResponse = { connected: true, expiresAt: data.expiresAt };
            setStatus(newStatus);
            if (onStatusChange) onStatusChange(newStatus);
        } catch (e: any) {
            setError(e.message ?? 'Failed to connect AWS credentials');
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleDisconnect = async () => {
        setError(null);
        setIsDisconnecting(true);
        try {
            await lisaAxios.delete(`${MCP_WORKBENCH_URI}/api/aws/connect`, {
                headers: sessionId ? { 'X-Session-Id': sessionId } : undefined,
            });
            const newStatus: AwsStatusResponse = { connected: false };
            setStatus(newStatus);
            setAccountId(null);
            setArn(null);
            if (onStatusChange) onStatusChange(newStatus);
        } catch (e: any) {
            setError(e.message ?? 'Failed to disconnect AWS credentials');
        } finally {
            setIsDisconnecting(false);
        }
    };

    const isConnected = status?.connected;
    const isExpired = isConnected && expiresInMinutes !== null && expiresInMinutes <= 0;

    return (
        <Form
            header={<Header variant='h2'>{title}</Header>}
            actions={
                <SpaceBetween direction='horizontal' size='s'>
                    {isConnected && (
                        <Button
                            variant='normal'
                            onClick={handleDisconnect}
                            loading={isDisconnecting}
                        >
                            Disconnect now
                        </Button>
                    )}
                    <Button
                        variant='primary'
                        disabled={isSubmitting}
                        loading={isSubmitting}
                        onClick={handleConnect}
                    >
                        {isConnected ? 'Reconnect' : 'Connect'}
                    </Button>
                </SpaceBetween>
            }
        >
            <SpaceBetween size='m' direction='vertical'>
                <TextContent>
                    <p>
                        Connect your AWS credentials to this chat session. Your keys are validated and converted to
                        short-lived session credentials stored securely in memory. To use them, your MCP server must
                        expose tools that leverage these credentials (for example, S3 list buckets or other AWS operations).
                        Without such tools, connecting credentials has no effect.
                    </p>
                    <p>
                        <strong>Caution:</strong> Credentials with broad permissions can create, modify, or delete resources
                        in your AWS account. Use IAM credentials with the minimum permissions required for the tools you
                        intend to use.
                    </p>
                </TextContent>
                <Container header={<Header>Connection status</Header>}>
                    <SpaceBetween size='s' direction='vertical'>
                        <StatusIndicator
                            type={isConnected && !isExpired ? 'success' : isConnected && isExpired ? 'warning' : 'stopped'}
                        >
                            {isConnected && !isExpired && expiresInMinutes != null
                                ? `Connected (expires in ${expiresInMinutes} minutes)`
                                : isConnected && isExpired
                                    ? 'Connected (expired)'
                                    : 'Not connected'}
                        </StatusIndicator>
                        {accountId && arn && (
                            <TextContent>
                                <Box>
                                    <small>Account ID: {accountId}</small>
                                </Box>
                                <Box>
                                    <small>ARN: {arn}</small>
                                </Box>
                            </TextContent>
                        )}
                        <TextContent>
                            <small>
                                Credentials are discarded when your session ends.
                            </small>
                        </TextContent>
                        {error && (
                            <TextContent>
                                <Box color='text-status-error'>
                                    <small>{error}</small>
                                </Box>
                            </TextContent>
                        )}
                        <Button
                            variant='inline-link'
                            onClick={() => {
                                setIsLoadingStatus(true);
                                setError(null);
                                void loadStatus();
                            }}
                            loading={isLoadingStatus}
                        >
                            Refresh status
                        </Button>
                    </SpaceBetween>
                </Container>
                <Container header={<Header>Enter AWS credentials</Header>}>
                    <SpaceBetween size='s' direction='vertical'>
                        <FormField
                            label='Access key ID'
                        >
                            <Input
                                value={accessKeyId}
                                onChange={({ detail }) => setAccessKeyId(detail.value)}
                                type='text'
                                autoComplete='off'
                            />
                        </FormField>
                        <FormField
                            label='Secret access key'
                        >
                            <Input
                                value={secretAccessKey}
                                onChange={({ detail }) => setSecretAccessKey(detail.value)}
                                type='password'
                                autoComplete='off'
                            />
                        </FormField>
                        <FormField
                            label='Session token (optional)'
                        >
                            <Input
                                value={sessionToken}
                                onChange={({ detail }) => setSessionToken(detail.value)}
                                type='password'
                                autoComplete='off'
                            />
                        </FormField>
                        <FormField
                            label='Region'
                        >
                            <Input
                                value={region}
                                onChange={({ detail }) => setRegion(detail.value)}
                                type='text'
                                autoComplete='off'
                            />
                        </FormField>
                    </SpaceBetween>
                </Container>
            </SpaceBetween>
        </Form>
    );
};

export default AwsCredentialsPanel;

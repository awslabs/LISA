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

import React, { useEffect, useState } from 'react';
import {
    Box,
    Button,
    Header,
    SpaceBetween,
    Spinner,
    StatusIndicator,
    Container,
} from '@cloudscape-design/components';
import { useDispatch } from 'react-redux';
import { getFileType, normalizeDocumentName } from '@/components/utils';
import { useLazyDownloadRagDocumentQuery } from '@/shared/reducers/rag.reducer';
import { useNotificationService } from '@/shared/util/hooks';

export type DocumentSidePanelProps = {
    visible: boolean;
    onClose: () => void;
    document: {
        documentId: string;
        repositoryId: string;
        name: string;
        source: string;
    } | null;
};

export function DocumentSidePanel ({ visible, onClose, document }: DocumentSidePanelProps) {
    const dispatch = useDispatch();
    const notificationService = useNotificationService(dispatch);
    const [downloadUrl, { isLoading: isLoadingUrl }] = useLazyDownloadRagDocumentQuery();
    const [documentUrl, setDocumentUrl] = useState<string | null>(null);
    const [textContent, setTextContent] = useState('');
    const [error, setError] = useState<string | null>(null);

    const fileType = document ? getFileType(document.name) : 'txt';

    // Reset transient state synchronously whenever the visible document
    // changes. The "adjusting state while rendering" pattern keeps the
    // setState calls out of useEffect (react-hooks/set-state-in-effect).
    const currentDocKey = visible && document?.documentId ? document.documentId : null;
    const [lastDocKey, setLastDocKey] = useState<string | null>(null);
    if (currentDocKey !== lastDocKey) {
        setLastDocKey(currentDocKey);
        setDocumentUrl((prev) => {
            if (prev) URL.revokeObjectURL(prev);
            return null;
        });
        setTextContent('');
        setError(null);
    }

    // Async load: setState calls happen after the await, so they're not
    // synchronously in the effect body and the rule is satisfied.
    useEffect(() => {
        if (!visible || !document) return;
        let cancelled = false;

        (async () => {
            try {
                const urlResponse = await downloadUrl({
                    documentId: document.documentId,
                    repositoryId: document.repositoryId,
                }).unwrap();
                if (cancelled) return;

                if (fileType === 'pdf') {
                    // Fetch PDF as blob and create object URL with correct MIME type
                    // This ensures browser displays it inline instead of downloading
                    const response = await fetch(urlResponse);
                    if (cancelled) return;
                    if (!response.ok) {
                        throw new Error(`Failed to fetch document: ${response.status} ${response.statusText}`);
                    }
                    const blob = await response.blob();
                    if (cancelled) return;

                    const pdfBlob = new Blob([blob], { type: 'application/pdf' });
                    const objectUrl = URL.createObjectURL(pdfBlob);
                    setDocumentUrl(objectUrl);
                } else if (fileType === 'txt') {
                    const response = await fetch(urlResponse);
                    if (cancelled) return;
                    if (!response.ok) {
                        throw new Error(`Failed to fetch document: ${response.status} ${response.statusText}`);
                    }
                    const text = await response.text();
                    if (cancelled) return;
                    setTextContent(text);
                }
            } catch (err) {
                if (cancelled) return;
                const errorMessage = err instanceof Error ? err.message : 'Unknown error';
                notificationService.generateNotification(
                    `Failed to load document: ${errorMessage}`,
                    'error'
                );
                setError('Failed to load document. Please try again.');
            }
        })();

        return () => {
            cancelled = true;
        };
    // notificationService is intentionally omitted because it's recreated on every
    // render; including it would cause the load effect to thrash.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [visible, document?.documentId, downloadUrl, fileType]);

    // Cleanup object URL on unmount
    useEffect(() => {
        return () => {
            if (documentUrl) {
                URL.revokeObjectURL(documentUrl);
            }
        };
    }, [documentUrl]);

    const handleDownload = async () => {
        if (!document) return;

        try {
            const url = await downloadUrl({
                documentId: document.documentId,
                repositoryId: document.repositoryId,
            }).unwrap();

            window.open(url, '_blank', 'noopener, noreferrer');
        } catch (err) {
            const errorMessage = err instanceof Error ? err.message : 'Unknown error';
            notificationService.generateNotification(
                `Failed to download document: ${errorMessage}`,
                'error'
            );
        }
    };

    if (!visible) {
        return null;
    }

    return (
        <div
            style={{
                width: '98%',
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                marginLeft: '8px',
                overflow: 'scroll'
            }}
        >
            <Container style={{
                root:{
                    borderRadius: '8px',
                }
            }}
            header={
                <Header
                    variant='h2'
                    actions={
                        <SpaceBetween direction='horizontal' size='xs'>
                            <Button
                                onClick={handleDownload}
                                disabled={!document}
                                iconName='download'
                            >
                                Download
                            </Button>
                            <Button
                                onClick={onClose}
                                iconName='close'
                                variant='icon'
                                ariaLabel='Close document viewer'
                            />
                        </SpaceBetween>
                    }
                >
                    {document ? normalizeDocumentName(document.name) : 'Document'}
                </Header>
            }
            >
                <div style={{ height: 'calc(100vh - 27rem)', overflow: 'auto' }}>
                    <SpaceBetween direction='vertical' size='m'>
                        {error && (
                            <StatusIndicator type='error'>{error}</StatusIndicator>
                        )}

                        {isLoadingUrl && (
                            <Box textAlign='center' padding='l'>
                                <Spinner size='large' />
                                <Box variant='p' padding={{ top: 's' }}>
                                    Loading document...
                                </Box>
                            </Box>
                        )}

                        {!error && !isLoadingUrl && fileType === 'pdf' && documentUrl && (
                            <Box>
                                <iframe
                                    src={documentUrl}
                                    style={{
                                        width: '100%',
                                        height: 'calc(100vh - 27rem)',
                                        border: 'none',
                                        overflow: 'hidden'
                                    }}
                                    title={document?.name || 'PDF Document'}
                                />
                            </Box>
                        )}

                        {!error && !isLoadingUrl && fileType === 'txt' && textContent && (
                            <Box>
                                <pre
                                    style={{
                                        whiteSpace: 'pre-wrap',
                                        overflow: 'auto',
                                        padding: '12px',
                                        backgroundColor: '#f4f4f4',
                                        borderRadius: '4px',
                                        fontSize: '14px',
                                        fontFamily: 'monospace',
                                        color: '#000000'
                                    }}
                                >
                                    {textContent}
                                </pre>
                            </Box>
                        )}

                        {!error && !isLoadingUrl && fileType === 'docx' && (
                            <Box textAlign='center' padding='l'>
                                <StatusIndicator type='info'>
                                    Preview not available for DOCX files
                                </StatusIndicator>
                                <Box variant='p' padding={{ top: 's' }}>
                                    File: {document?.name}
                                </Box>
                                <Box variant='p' color='text-body-secondary'>
                                    Click "Download" to download and view this file.
                                </Box>
                            </Box>
                        )}
                    </SpaceBetween>
                </div>
            </Container>
        </div>
    );
}

export default DocumentSidePanel;

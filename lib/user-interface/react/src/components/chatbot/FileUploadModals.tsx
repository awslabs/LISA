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

import {
    Modal,
    Box,
    SpaceBetween,
    Button,
    TextContent,
    FileUpload,
    Alert,
    FormField,
    Grid,
    Input,
    ProgressBar,
    StatusIndicator,
} from '@cloudscape-design/components';
import { FileTypes, StatusTypes } from '../types';
import { useState } from 'react';
import { getPresignedUrl, ingestDocuments, uploadToS3 } from '../utils';
import { RagConfig } from './RagOptions';
import { AuthContextProps } from 'react-oidc-context';

const handleUpload = async (
    selectedFiles: File[],
    handleError: (error: string) => void,
    processFile: (file: File, fileIndex: number) => Promise<boolean>,
    allowedFileTypes: FileTypes[],
    fileSizeLimit: number,
) => {
    if (selectedFiles.length > 0) {
        const successfulUploads: string[] = [];

        for (let i = 0; i < selectedFiles.length; i++) {
            const file = selectedFiles[i];
            let error = '';
            if (!allowedFileTypes.includes(file.type as FileTypes)) {
                error = `${file.name} has an unsupported file type for this operation. `;
            }
            if (file.size > fileSizeLimit) {
                error += `File ${file.name} is too big for this operation. Max file size is ${fileSizeLimit}`;
            }
            if (error) {
                handleError(error);
            } else {
                const success = await processFile(file, i + 1);
                if (success) {
                    successfulUploads.push(file.name);
                }
            }
        }
        return successfulUploads;
    }
};

export type ContextUploadProps = {
    showContextUploadModal: boolean;
    setShowContextUploadModal: React.Dispatch<React.SetStateAction<boolean>>;
    fileContext: string;
    setFileContext: React.Dispatch<React.SetStateAction<string>>;
};

export function ContextUploadModal ({
    showContextUploadModal,
    setShowContextUploadModal,
    fileContext,
    setFileContext,
}: ContextUploadProps) {
    const [selectedFiles, setSelectedFiles] = useState<File[] | undefined>([]);
    const [alerts, setAlerts] = useState<string[] | undefined>([]);

    function handleError (error: string) {
        setAlerts((oldItems) => [...oldItems, error]);
    }

    async function processFile (file: File): Promise<boolean> {
    //File context currently only supports single files
        const fileContents = await file.text();
        setFileContext(`File context: ${fileContents}`);
        setSelectedFiles([file]);
        return true;
    }

    return (
        <Modal
            onDismiss={() => {
                setShowContextUploadModal(false);
                setSelectedFiles([]);
                setAlerts([]);
            }}
            visible={showContextUploadModal}
            header='Manage File Context'
            size='large'
            footer={
                <Box float='right'>
                    <SpaceBetween direction='horizontal' size='xs'>
                        <Button
                            onClick={async () => {
                                setAlerts([]);
                                await handleUpload(selectedFiles, handleError, processFile, [FileTypes.TEXT], 10240);
                                if (alerts.length === 0) {
                                    setShowContextUploadModal(false);
                                    setSelectedFiles([]);
                                }
                            }}
                            disabled={selectedFiles.length === 0}
                        >
                            Set file context
                        </Button>
                        <Button
                            onClick={() => {
                                setShowContextUploadModal(false);
                                setFileContext('');
                                setSelectedFiles([]);
                                setAlerts([]);
                            }}
                            disabled={!fileContext}
                        >
                            Clear file context
                        </Button>
                    </SpaceBetween>
                </Box>
            }
        >
            <SpaceBetween direction='vertical' size='s'>
                <TextContent>
                    <h4>File Context</h4>
                    <p>
                        <small>
                            Upload files for LISA to use as context in this session. This additional context will be referenced to
                            answer your questions.
                        </small>
                    </p>
                </TextContent>
                <FileUpload
                    onChange={({ detail }) => setSelectedFiles(detail.value)}
                    value={selectedFiles}
                    i18nStrings={{
                        uploadButtonText: (e) => (e ? 'Choose files' : 'Choose file'),
                        dropzoneText: (e) => (e ? 'Drop files to upload' : 'Drop file to upload'),
                        removeFileAriaLabel: (e) => `Remove file ${e + 1}`,
                        limitShowFewer: 'Show fewer files',
                        limitShowMore: 'Show more files',
                        errorIconAriaLabel: 'Error',
                    }}
                    showFileSize
                    tokenLimit={3}
                    constraintText='Allowed file type is plain text. File size limit is 10 KB'
                />
                {alerts.map(function (error: string) {
                    if (error !== '') {
                        return (
                            <Alert
                                type='error'
                                statusIconAriaLabel='Error'
                                header='File upload error:'
                                dismissible
                                onDismiss={() => {
                                    setAlerts([]);
                                }}
                            >
                                {error}
                            </Alert>
                        );
                    }
                })}
            </SpaceBetween>
        </Modal>
    );
}

export type RagUploadProps = {
    auth: AuthContextProps;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    setFlashbarItems: React.Dispatch<React.SetStateAction<any[]>>;
    showRagUploadModal: boolean;
    setShowRagUploadModal: React.Dispatch<React.SetStateAction<boolean>>;
    ragConfig: RagConfig;
};

export function RagUploadModal ({
    auth,
    setFlashbarItems,
    showRagUploadModal,
    setShowRagUploadModal,
    ragConfig,
}: RagUploadProps) {
    const [selectedFiles, setSelectedFiles] = useState<File[] | undefined>([]);
    const [displayProgressBar, setDisplayProgressBar] = useState(false);
    const [progressBarValue, setProgressBarValue] = useState(0);
    const [progressBarDescription, setProgressBarDescription] = useState('');
    const [progressBarLabel, setProgressBarLabel] = useState('');
    const [ingestingFiles, setIngestingFiles] = useState(false);
    const [ingestionStatus, setIngestionStatus] = useState('');
    const [ingestionType, setIngestionType] = useState(StatusTypes.LOADING);
    const [chunkSize, setChunkSize] = useState(512);
    const [chunkOverlap, setChunkOverlap] = useState(51);
    const [alerts, setAlerts] = useState<string[] | undefined>([]);

    function handleError (error: string): void {
        setAlerts((oldItems) => [...oldItems, error]);
    }

    async function processFile (file: File, fileIndex: number): Promise<boolean> {
        setProgressBarDescription(`Uploading ${file.name}`);
        try {
            const urlResponse = await getPresignedUrl(auth.user?.id_token, file.name);
            const s3UploadStatusCode = await uploadToS3(urlResponse, file);

            if (s3UploadStatusCode !== 204) {
                throw new Error(`File ${file.name} failed to upload.`);
            }
            return true;
        } catch (err) {
            setAlerts((oldItems) => [...oldItems, `Error encountered while uploading file ${file.name}`]);
            return false;
        } finally {
            setProgressBarValue((fileIndex / selectedFiles.length) * 100);
        }
    }

    async function indexFiles (fileKeys: string[]): Promise<void> {
        setIngestingFiles(true);
        setIngestionType(StatusTypes.LOADING);
        setIngestionStatus('Ingesting documents into the selected repository...');
        try {
            // Ingest all of the documents which uploaded successfully

            const ingestResponseStatusCode = await ingestDocuments(
                auth.user?.id_token,
                fileKeys,
                ragConfig.repositoryId,
                ragConfig.embeddingModel,
                ragConfig.repositoryType,
                chunkSize,
                chunkOverlap,
            );
            if (ingestResponseStatusCode === 200) {
                setIngestionType(StatusTypes.SUCCESS);
                setIngestionStatus('Successfully ingested documents into the selected repository');
                setFlashbarItems((oldItems) => [
                    ...oldItems,
                    {
                        header: 'Success',
                        type: 'success',
                        content: `Successfully ingested ${fileKeys.length} document(s) into the selected repository.`,
                        dismissible: true,
                        dismissLabel: 'Dismiss message',
                        onDismiss: () => {
                            setFlashbarItems([]);
                        },
                        id: 'rag_success',
                    },
                ]);
                setShowRagUploadModal(false);
            } else {
                throw new Error('Failed to ingest documents into RAG');
            }
        } catch (err) {
            setIngestionType(StatusTypes.ERROR);
            setIngestionStatus('Failed to ingest documents into RAG');
        } finally {
            setIngestingFiles(false);
        }
    }

    return (
        <Modal
            onDismiss={() => {
                setShowRagUploadModal(false);
                setSelectedFiles([]);
                setAlerts([]);
                setIngestingFiles(false);
            }}
            visible={showRagUploadModal}
            header='Upload to RAG'
            size='large'
            footer={
                <Box float='right'>
                    <SpaceBetween direction='horizontal' size='xs'>
                        <Button
                            onClick={async () => {
                                setAlerts([]);
                                //Initialize the progress bar values
                                setProgressBarLabel('Uploading files to S3');
                                setDisplayProgressBar(true);
                                setProgressBarValue(0);

                                //Allowed file types are plain text, docx, and pdf. File size limit is 50 MB
                                const successfulUploads = await handleUpload(
                                    selectedFiles,
                                    handleError,
                                    processFile,
                                    [FileTypes.TEXT, FileTypes.DOCX, FileTypes.PDF],
                                    52428800,
                                );
                                setDisplayProgressBar(false);
                                if (successfulUploads.length > 0) {
                                    await indexFiles(successfulUploads);
                                }
                                if (alerts.length === 0) {
                                    setShowRagUploadModal(false);
                                    setSelectedFiles([]);
                                }
                            }}
                            disabled={selectedFiles.length === 0}
                        >
                            Upload
                        </Button>
                    </SpaceBetween>
                </Box>
            }
        >
            <SpaceBetween direction='vertical' size='s'>
                <TextContent>
                    <h4>Upload to RAG</h4>
                    <p>
                        <small>
                            Upload files to the RAG repository leveraged by LISA. This will provide LISA with trusted information for
                            answering prompts.
                        </small>
                    </p>
                </TextContent>
                <Grid gridDefinition={[{ colspan: { default: 12, xxs: 6 } }, { colspan: { default: 12, xxs: 6 } }]}>
                    <FormField label='Chunk Size' description='Size of chunks that will be persisted in the RAG repository'>
                        <Input
                            value={chunkSize.toString()}
                            type='number'
                            step={1}
                            inputMode='numeric'
                            disableBrowserAutocorrect={true}
                            onChange={(event) => {
                                const intVal = parseInt(event.detail.value);
                                if (intVal >= 0) {
                                    setChunkSize(intVal);
                                }
                            }}
                        />
                    </FormField>
                    <FormField label='Chunk Overlap' description='Size of the overlap used when generating content chunks'>
                        <Input
                            value={chunkOverlap.toString()}
                            type='number'
                            step={1}
                            inputMode='numeric'
                            disableBrowserAutocorrect={true}
                            onChange={(event) => {
                                const intVal = parseInt(event.detail.value);
                                if (intVal >= 0) {
                                    setChunkOverlap(intVal);
                                }
                            }}
                        />
                    </FormField>
                </Grid>
                <FileUpload
                    onChange={({ detail }) => setSelectedFiles(detail.value)}
                    value={selectedFiles}
                    multiple
                    i18nStrings={{
                        uploadButtonText: (e) => (e ? 'Choose files' : 'Choose file'),
                        dropzoneText: (e) => (e ? 'Drop files to upload' : 'Drop file to upload'),
                        removeFileAriaLabel: (e) => `Remove file ${e + 1}`,
                        limitShowFewer: 'Show fewer files',
                        limitShowMore: 'Show more files',
                        errorIconAriaLabel: 'Error',
                    }}
                    showFileSize
                    tokenLimit={3}
                    constraintText='Allowed file types are plain text, PDF, and docx. File size limit is 50 MB'
                />
                {alerts.map(function (error: string) {
                    if (error !== '') {
                        return (
                            <Alert
                                type='error'
                                statusIconAriaLabel='Error'
                                header='File upload error:'
                                dismissible
                                onDismiss={() => {
                                    setAlerts([]);
                                }}
                            >
                                {error}
                            </Alert>
                        );
                    }
                })}
                {displayProgressBar && (
                    <ProgressBar
                        status='in-progress'
                        value={progressBarValue}
                        description={progressBarDescription}
                        label={progressBarLabel}
                    />
                )}
                {ingestingFiles && <StatusIndicator type={ingestionType}>{ingestionStatus}</StatusIndicator>}
            </SpaceBetween>
        </Modal>
    );
}

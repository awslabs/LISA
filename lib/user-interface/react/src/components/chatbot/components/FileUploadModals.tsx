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
    Box,
    Button,
    FileUpload,
    FormField,
    Grid,
    Input,
    Modal,
    ProgressBar,
    SpaceBetween,
    StatusIndicator,
    TextContent,
} from '@cloudscape-design/components';
import {FileTypes, StatusTypes} from '../../types';
import {useState} from 'react';
import {RagConfig} from './RagOptions';
import {useAppDispatch} from '@/config/store';
import {useNotificationService} from '@/shared/util/hooks';
import {
    useIngestDocumentsMutation,
    useLazyGetPresignedUrlQuery,
    useUploadToS3Mutation,
} from '@/shared/reducers/rag.reducer';
import {uploadToS3Request} from '../../utils';
import {RagRepositoryPipeline} from '#root/lib/schema';
import { IModel } from '@/shared/model/model-management.model';

export const renameFile = (originalFile: File) => {
    // Add timestamp to filename for RAG uploads to not conflict with existing S3 files
    const newFileName = `${Date.now()}_${originalFile.name}`;
    return new File([originalFile], newFileName, {
        type: originalFile.type,
        lastModified: originalFile.lastModified,
    });
};

export const handleUpload = async (
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
    selectedModel: IModel;
};

export function ContextUploadModal ({
    showContextUploadModal,
    setShowContextUploadModal,
    fileContext,
    setFileContext,
    selectedModel
}: ContextUploadProps) {
    const [selectedFiles, setSelectedFiles] = useState<File[] | undefined>([]);
    const dispatch = useAppDispatch();
    const notificationService = useNotificationService(dispatch);
    const modelSupportsImages = selectedModel?.features?.filter((feature) => feature.name === 'imageInput')?.length && true;

    function handleError (error: string) {
        notificationService.generateNotification(error, 'error');
    }

    async function processFile (file: File): Promise<boolean> {
        //File context currently only supports single files
        let fileContents: string;

        if (file.type === FileTypes.JPEG || file.type === FileTypes.JPG || file.type === FileTypes.PNG) {
            // Handle JPEG files
            fileContents = await new Promise((resolve) => {
                const reader = new FileReader();
                reader.onloadend = () => {
                    const base64String = reader.result as string;
                    resolve(base64String);
                };
                reader.readAsDataURL(file);
            });
        } else {
            // Handle text files
            fileContents = await file.text();
        }

        setFileContext(`File context: ${fileContents}`);
        setSelectedFiles([file]);
        return true;
    }

    return (
        <Modal
            onDismiss={() => {
                setShowContextUploadModal(false);
                setSelectedFiles([]);
            }}
            visible={showContextUploadModal}
            header='Manage File Context'
            size='large'
            footer={
                <Box float='right'>
                    <SpaceBetween direction='horizontal' size='xs'>
                        <Button
                            onClick={async () => {
                                const files = selectedFiles.map((f) => renameFile(f));
                                const successfulUploads = await handleUpload(files, handleError, processFile, modelSupportsImages ? [FileTypes.TEXT, FileTypes.JPEG, FileTypes.PNG, FileTypes.WEBP, FileTypes.GIF] : [FileTypes.TEXT], 20971520);
                                if (successfulUploads.length > 0) {
                                    notificationService.generateNotification(`Successfully added file(s) to context ${successfulUploads.join(', ')}`, StatusTypes.SUCCESS);
                                    setShowContextUploadModal(false);
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
                    constraintText={`Allowed file types are ${modelSupportsImages ? 'txt, png, jpg, jpeg, gif, webp' : 'txt'}. File size limit is 20 MB.`}
                />
            </SpaceBetween>
        </Modal>
    );
}

export type RagUploadProps = {
    showRagUploadModal: boolean;
    setShowRagUploadModal: React.Dispatch<React.SetStateAction<boolean>>;
    ragConfig: RagConfig;
};

export function RagUploadModal ({
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
    const dispatch = useAppDispatch();
    const [getPresignedUrl] = useLazyGetPresignedUrlQuery();
    const notificationService = useNotificationService(dispatch);
    const [uploadToS3Mutation] = useUploadToS3Mutation();
    const [ingestDocuments] = useIngestDocumentsMutation();

    function handleError (error: string): void {
        notificationService.generateNotification(error, 'error');
    }

    async function processFile (file: File, fileIndex: number): Promise<boolean> {
        setProgressBarDescription(`Uploading ${file.name}`);

        const urlResponse = await getPresignedUrl(file.name);
        const s3UploadRequest = uploadToS3Request(urlResponse.data, file);

        const uploadResp = await uploadToS3Mutation(s3UploadRequest);
        if (uploadResp.error) {
            handleError(`Error encountered while uploading file ${file.name}`);
            return false;
        }
        setProgressBarValue((fileIndex / selectedFiles.length) * 100);
        return true;

    }

    async function indexFiles (fileKeys: string[]): Promise<void> {
        setIngestingFiles(true);
        setIngestionType(StatusTypes.LOADING);
        setIngestionStatus('Ingesting documents into the selected repository...');
        try {
            // Ingest all of the documents which uploaded successfully

            const ingestResp = await ingestDocuments({
                documents: fileKeys,
                repositoryId: ragConfig.repositoryId,
                embeddingModel: { id: ragConfig.embeddingModel.modelId, modelType: ragConfig.embeddingModel.modelType, streaming: ragConfig.embeddingModel.streaming },
                repostiroyType: ragConfig.repositoryType,
                chunkSize,
                chunkOverlap});

            if (ingestResp.error) {
                throw new Error('Failed to ingest documents into RAG');
            } else {
                setIngestionType(StatusTypes.SUCCESS);
                setIngestionStatus('Successfully ingested documents into the selected repository');
                notificationService.generateNotification(`Successfully ingested ${fileKeys.length} document(s) into the selected repository.`, 'success');
                setShowRagUploadModal(false);
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
                                //Initialize the progress bar values
                                setProgressBarLabel('Uploading files to S3');
                                setDisplayProgressBar(true);
                                setProgressBarValue(0);

                                //Allowed file types are plain text, docx, and pdf. File size limit is 50 MB
                                const files = selectedFiles.map((f) => renameFile(f));
                                const successfulUploads = await handleUpload(
                                    files,
                                    handleError,
                                    processFile,
                                    [FileTypes.TEXT, FileTypes.DOCX, FileTypes.PDF],
                                    52428800,
                                );
                                setDisplayProgressBar(false);
                                if (successfulUploads.length > 0) {
                                    await indexFiles(successfulUploads);
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
                    <FormField label='Chunk Size' description={RagRepositoryPipeline.shape.chunkSize.description}>
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
                    <FormField label='Chunk Overlap' description={RagRepositoryPipeline.shape.chunkOverlap.description}>
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
                    constraintText='Allowed file types are plain text, PDF, and docx. File size limit is 50 MB.'
                />
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

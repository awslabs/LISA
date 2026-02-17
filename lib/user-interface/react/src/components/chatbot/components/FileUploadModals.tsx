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
    Checkbox,
    FileUpload,
    Modal,
    ProgressBar,
    SpaceBetween,
    StatusIndicator,
    TextContent,
} from '@cloudscape-design/components';
import { FileTypes, StatusTypes } from '@/components/types';
import React, { useState, useEffect } from 'react';
import * as pdfjsLib from 'pdfjs-dist';
import { RagConfig } from './RagOptions';
import { useAppDispatch } from '@/config/store';
import { useNotificationService } from '@/shared/util/hooks';
import {
    useIngestDocumentsMutation,
    useLazyGetPresignedUrlQuery,
    useUploadToS3Mutation,
} from '@/shared/reducers/rag.reducer';
import { uploadToS3Request } from '@/components/utils';
import { ChunkingStrategy, ChunkingStrategyType, RagRepositoryType } from '#root/lib/schema';
import { IModel, ModelType } from '@/shared/model/model-management.model';
import { JobStatusTable } from '@/components/chatbot/components/JobStatusTable';
import { ChunkingConfigForm } from '@/shared/form/ChunkingConfigForm';
import { MetadataForm } from '@/shared/form/MetadataForm';
import { getDisplayName } from '@/shared/util/branding';

// Configure PDF.js worker to use local file
pdfjsLib.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.mjs';

// File extension mappings for validation
const AllowedExtensions =
    [
        '.py', '.js', '.jsx', '.ts', '.tsx', '.html', '.htm', '.css',
        '.java', '.c', '.cpp', '.cxx', '.cc', '.h', '.hpp', '.hxx',
        '.go', '.rs', '.rb', '.php', '.swift', '.kt', '.kts', '.scala',
        '.sh', '.bash', '.zsh', '.fish', '.ps1', '.sql', '.yaml', '.yml',
        '.json', '.xml', '.toml', '.ini', '.cfg', '.conf', '.r', '.m',
        '.cs', '.vb', '.fs', '.clj', '.cljs', '.ex', '.exs', '.erl',
        '.hrl', '.lua', '.pl', '.pm', '.dart', '.zig', '.nim', '.v',
        '.sv', '.svh', '.vhd', '.vhdl'
    ];

/**
 * Extract file extension from filename
 */
const getFileExtension = (filename: string): string => {
    const lastDot = filename.lastIndexOf('.');
    return lastDot !== -1 ? filename.slice(lastDot).toLowerCase() : '';
};

/**
 * Check if file extension is allowed
 */
const isAllowedFileExtension = (filename: string): boolean => {
    const ext = getFileExtension(filename);
    return AllowedExtensions.includes(ext);
};

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
            // Check both MIME type and file extension (extension as fallback for files without proper MIME types)
            if (!allowedFileTypes.includes(file.type as FileTypes) && !isAllowedFileExtension(file.name)) {
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
    setFileContextName: React.Dispatch<React.SetStateAction<string>>;
    setFileContextFiles: React.Dispatch<React.SetStateAction<Array<{name: string, content: string}>>>;
    selectedModel: IModel;
};

export const ContextUploadModal = ({
    showContextUploadModal,
    setShowContextUploadModal,
    fileContext,
    setFileContext,
    setFileContextName,
    setFileContextFiles,
    selectedModel
}: ContextUploadProps) => {
    const [selectedFiles, setSelectedFiles] = useState<File[] | undefined>([]);
    const dispatch = useAppDispatch();
    const notificationService = useNotificationService(dispatch);
    const modelSupportsImages = !!(selectedModel?.features?.filter((feature) => feature.name === 'imageInput')?.length) || selectedModel?.modelType === ModelType.videogen || selectedModel?.modelType === ModelType.imagegen;

    // Clear selectedFiles when fileContext is cleared externally (e.g., via badge dismissal)
    useEffect(() => {
        if (!fileContext) {
            queueMicrotask(() => setSelectedFiles([]));
            setFileContextFiles([]);
        }
    }, [fileContext, setFileContextFiles]);

    function handleError (error: string) {
        notificationService.generateNotification(error, 'error');
    }

    async function extractTextFromPDF (file: File): Promise<string> {
        const arrayBuffer = await file.arrayBuffer();
        const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;

        let fullText = '';
        for (let i = 1; i <= pdf.numPages; i++) {
            const page = await pdf.getPage(i);
            const textContent = await page.getTextContent();
            const pageText = textContent.items
                .map((item: any) => item.str)
                .join(' ');
            fullText += pageText + '\n\n';
        }

        return fullText;
    }

    // Store accumulated content in a ref-like object to avoid async state issues
    const fileContentsAccumulator: { contents: string[], files: File[] } = {
        contents: [],
        files: []
    };

    async function processFile (file: File): Promise<boolean> {
        // Process file and return its contents to be accumulated
        let fileContents: string;

        if (file.type === FileTypes.JPEG || file.type === FileTypes.JPG || file.type === FileTypes.PNG) {
            // Handle image files
            fileContents = await new Promise((resolve) => {
                const reader = new FileReader();
                reader.onloadend = () => {
                    const base64String = reader.result as string;
                    resolve(base64String);
                };
                reader.readAsDataURL(file);
            });
        } else if (file.type === FileTypes.PDF) {
            // Handle PDF files
            fileContents = await extractTextFromPDF(file);
        } else {
            // Handle text files
            fileContents = await file.text();
        }

        // Accumulate the file content with a clear separator
        fileContentsAccumulator.contents.push(`--- File: ${file.name} ---\n${fileContents}`);
        fileContentsAccumulator.files.push(file);
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
                                const successfulUploads = await handleUpload(files, handleError, processFile, modelSupportsImages
                                    ? [FileTypes.TEXT, FileTypes.JPEG, FileTypes.PNG, FileTypes.WEBP, FileTypes.GIF]
                                    : [FileTypes.TEXT, FileTypes.PDF, FileTypes.PYTHON, FileTypes.JAVASCRIPT, FileTypes.HTML, FileTypes.MARKDOWN, FileTypes.YAML, FileTypes.JSON], 20971520);

                                if (successfulUploads.length > 0) {
                                    // Combine all accumulated file contents
                                    const combinedContext = fileContentsAccumulator.contents.join('\n\n');
                                    setFileContext(`File context:\n${combinedContext}`);
                                    setFileContextName(successfulUploads.join(', '));
                                    setSelectedFiles(fileContentsAccumulator.files);

                                    // Set the array of file objects for individual badge rendering
                                    const fileObjects = fileContentsAccumulator.contents.map((content, idx) => ({
                                        name: successfulUploads[idx],
                                        content: content
                                    }));
                                    setFileContextFiles(fileObjects);

                                    notificationService.generateNotification(`Successfully added ${successfulUploads.length} file(s) to context: ${successfulUploads.join(', ')}`, StatusTypes.SUCCESS);
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
                                setFileContextName('');
                                setSelectedFiles([]);
                                setFileContextFiles([]);
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
                            Upload files for {getDisplayName()} to use as context in this session. This additional context will be referenced to
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
                    multiple
                    showFileSize
                    tokenLimit={3}
                    constraintText={`Allowed file types are ${modelSupportsImages ? 'txt, png, jpg, jpeg, gif, webp' : 'txt, pdf, md, py, js, java, and other code files'}. File size limit is 20 MB.`}
                />
            </SpaceBetween>
        </Modal>
    );
};

export type RagUploadProps = {
    showRagUploadModal: boolean;
    setShowRagUploadModal: React.Dispatch<React.SetStateAction<boolean>>;
    ragConfig: RagConfig;
};


export const RagUploadModal = ({
    showRagUploadModal,
    setShowRagUploadModal,
    ragConfig,
}: RagUploadProps) => {
    const [selectedFiles, setSelectedFiles] = useState<File[] | undefined>([]);
    const [displayProgressBar, setDisplayProgressBar] = useState(false);
    const [progressBarValue, setProgressBarValue] = useState(0);
    const [progressBarDescription, setProgressBarDescription] = useState('');
    const [progressBarLabel, setProgressBarLabel] = useState('');
    const [ingestingFiles, setIngestingFiles] = useState(false);
    const [ingestionStatus, setIngestionStatus] = useState('');
    const [ingestionType, setIngestionType] = useState(StatusTypes.LOADING);
    const [overrideChunkingStrategy, setOverrideChunkingStrategy] = useState(false);
    const [chunkingStrategy, setChunkingStrategy] = useState<ChunkingStrategy | undefined>({
        type: ChunkingStrategyType.FIXED,
        size: 512,
        overlap: 51,
    });
    const [tags, setTags] = useState<string[]>([]);
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
        if ('error' in uploadResp) {
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
                collectionId: ragConfig.collection?.collectionId,
                repositoryType: ragConfig.repositoryType,
                chunkingStrategy: overrideChunkingStrategy ? chunkingStrategy : undefined,
                metadata: tags.length > 0 ? { tags, customFields: {} } : undefined,
            });

            if ('error' in ingestResp) {
                throw new Error('Failed to ingest documents into RAG');
            } else {
                setIngestionType(StatusTypes.SUCCESS);
                const jobs = ingestResp.data?.jobs || [];
                const jobIds = jobs.map((job) => job.jobId);
                const collectionName = ingestResp.data?.collectionName || ingestResp.data?.collectionId || 'repository';
                setIngestionStatus(`Successfully submitted documents for ingestion into ${collectionName}. Job IDs: ${jobIds.join(', ')}`);
                notificationService.generateNotification(`Successfully submitted ${fileKeys.length} document(s) for ingestion into ${collectionName}. ${jobs.length} job(s) created.`, 'success');
                setShowRagUploadModal(false);
            }
        } catch {
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
                setTags([]);
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
                            Upload files to the RAG repository leveraged by {getDisplayName()}. This will provide {getDisplayName()} with trusted information for
                            answering prompts.
                        </small>
                    </p>
                </TextContent>

                {/* Chunking Strategy Override Checkbox - Hidden for Bedrock repositories */}
                {ragConfig.repositoryType !== RagRepositoryType.BEDROCK_KNOWLEDGE_BASE && (
                    <Checkbox
                        checked={overrideChunkingStrategy}
                        onChange={({ detail }) => setOverrideChunkingStrategy(detail.checked)}
                    >
                        Override default chunking strategy
                    </Checkbox>
                )}

                {/* Chunking Strategy Form - Only shown when override is enabled and not Bedrock */}
                {overrideChunkingStrategy && ragConfig.repositoryType !== RagRepositoryType.BEDROCK_KNOWLEDGE_BASE && (
                    <ChunkingConfigForm
                        item={chunkingStrategy}
                        setFields={(values) => {
                            if (values.chunkingStrategy !== undefined) {
                                setChunkingStrategy(values.chunkingStrategy);
                            } else if (values['chunkingStrategy.size'] !== undefined && chunkingStrategy?.type === ChunkingStrategyType.FIXED) {
                                setChunkingStrategy({
                                    ...chunkingStrategy,
                                    size: values['chunkingStrategy.size'],
                                });
                            } else if (values['chunkingStrategy.overlap'] !== undefined && chunkingStrategy?.type === ChunkingStrategyType.FIXED) {
                                setChunkingStrategy({
                                    ...chunkingStrategy,
                                    overlap: values['chunkingStrategy.overlap'],
                                });
                            }
                        }}
                        touchFields={() => { }}
                        formErrors={{}}
                    />
                )}

                {/* Metadata */}
                <MetadataForm
                    tags={tags}
                    onTagsChange={setTags}
                    tagsDescription='Add tags to help organize and filter uploaded documents'
                />

                <FileUpload
                    onChange={({ detail }) => setSelectedFiles(detail.value)}
                    value={selectedFiles}
                    multiple
                    data-testid='rag-upload-file-input'
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

                {/* Job Status Table */}
                <JobStatusTable
                    ragConfig={ragConfig}
                    autoLoad={showRagUploadModal}
                    title='Recent Jobs'
                />
            </SpaceBetween>
        </Modal>
    );
};

export default RagUploadModal;

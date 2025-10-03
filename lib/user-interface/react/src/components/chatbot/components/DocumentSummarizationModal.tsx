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
    Autosuggest,
    Box,
    Button,
    FileUpload,
    Modal,
    SpaceBetween,
    Textarea,
    TextContent,
} from '@cloudscape-design/components';
import { FileTypes, LisaChatSession } from '../../types';
import { useEffect, useMemo, useState } from 'react';
import { useAppDispatch } from '@/config/store';
import { useNotificationService } from '@/shared/util/hooks';
import { useGetAllModelsQuery } from '@/shared/reducers/model-management.reducer';
import { IModel, ModelStatus, ModelType } from '@/shared/model/model-management.model';
import { handleUpload } from './FileUploadModals';
import { IChatConfiguration } from '@/shared/model/chat.configurations.model';
import { v4 as uuidv4 } from 'uuid';
import FormField from '@cloudscape-design/components/form-field';
import { LisaChatMessageHistory } from '../../adapters/lisa-chat-history';
import Toggle from '@cloudscape-design/components/toggle';
import { ChatMemory } from '@/shared/util/chat-memory';

export type DocumentSummarizationModalProps = {
    showDocumentSummarizationModal: boolean;
    setShowDocumentSummarizationModal: (state: boolean) => void;
    fileContext: string;
    setFileContext: (state: string) => void;
    setUserPrompt: (state: string) => void;
    userPrompt: string;
    selectedModel: IModel;
    setSelectedModel: (state: IModel) => void;
    chatConfiguration: IChatConfiguration;
    setChatConfiguration: (state: IChatConfiguration) => void;
    setInternalSessionId: (state: string) => void;
    setSession: (state: LisaChatSession) => void;
    userName: string;
    handleSendGenerateRequest: () => void;
    setMemory: (state: ChatMemory) => void;
};

export const DocumentSummarizationModal = ({
    showDocumentSummarizationModal,
    setShowDocumentSummarizationModal,
    setFileContext,
    setUserPrompt,
    userPrompt,
    selectedModel,
    setSelectedModel,
    chatConfiguration,
    setChatConfiguration,
    setInternalSessionId,
    setSession,
    userName,
    handleSendGenerateRequest,
    setMemory
}: DocumentSummarizationModalProps) => {
    const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
    const [successfulUploads, setSuccessfulUpload] = useState<string[]>(undefined);
    const dispatch = useAppDispatch();
    const notificationService = useNotificationService(dispatch);
    const [summarize, setSummarize] = useState<boolean>(false);
    const [createNewChatSession, setCreateNewChatSession] = useState<boolean>(true);

    const { data: allModels, isFetching: isFetchingModels } = useGetAllModelsQuery(undefined, {
        refetchOnMountOrArgChange: 5,
        selectFromResult: (state) => ({
            isFetching: state.isFetching,
            data: (state.data || []).filter((model: IModel) => model.modelType === ModelType.textgen && model.status === ModelStatus.InService && model.
                features && model.features.filter((feat) => feat.name === 'summarization').length > 0),
        })
    });
    const modelsOptions = useMemo(() => allModels.map((model) => ({ label: model.modelId, value: model.modelId, description: model.features.filter((feat) => feat.name === 'summarization')[0].overview })), [allModels]);
    const [selectedPromptType, setSelectedPromptType] = useState<string>('');
    const promptOptions = [
        { label: 'Concise', value: 'concise', description: 'Short Summary (best for small documents)' },
        { label: 'Overview', value: 'overview', description: 'Key bullet points (best for large documents)' },
        { label: 'Chain of Density', value: 'cod', description: 'An iterative summarization technique' },
        { label: 'Custom', value: 'custom', description: 'Write your own prompt' },
    ];

    function handleError (error: string) {
        notificationService.generateNotification(error, 'error');
    }

    async function processFile (file: File): Promise<boolean> {
        //File context currently only supports single files
        const fileContents = await file.text();
        setFileContext(`File context: ${fileContents}`);
        setSelectedFiles([file]);
        return true;
    }

    useEffect(
        () => {
            if (summarize) {
                setSummarize(false);
                handleSendGenerateRequest();

                setShowDocumentSummarizationModal(false);
                setSelectedPromptType(undefined);
                setSuccessfulUpload(undefined);
                setSelectedFiles([]);
                setFileContext('');
            }
            // eslint-disable-next-line react-hooks/exhaustive-deps
        }, [summarize]);

    return (
        <Modal
            onDismiss={() => {
                setShowDocumentSummarizationModal(false);
                setFileContext('');
                setSelectedFiles([]);
                setUserPrompt('');
                setSelectedModel(undefined);
                setSuccessfulUpload(undefined);
                setSelectedPromptType('');
            }}
            visible={showDocumentSummarizationModal}
            header='Summarize Document'
            size='large'
            footer={
                <Box float='right'>
                    <SpaceBetween direction='horizontal' size='xs'>
                        <Button
                            onClick={() => {
                                setShowDocumentSummarizationModal(false);
                                setFileContext('');
                                setSelectedFiles([]);
                                setUserPrompt('');
                                setSelectedModel(undefined);
                                setSuccessfulUpload(undefined);
                                setSelectedPromptType('');
                            }}
                            variant={'link'}
                        >
                            Cancel
                        </Button>
                        <Button
                            onClick={async () => {
                                if (successfulUploads.length > 0) {
                                    if (createNewChatSession) {
                                        const newSessionId = uuidv4();
                                        setInternalSessionId(newSessionId);
                                        const newSession = {
                                            history: [],
                                            sessionId: newSessionId,
                                            userId: userName,
                                            startTime: new Date(Date.now()).toISOString(),
                                        };
                                        setSession(newSession);

                                        setMemory(new ChatMemory({
                                            chatHistory: new LisaChatMessageHistory(newSession),
                                            returnMessages: false,
                                            memoryKey: 'history',
                                            k: chatConfiguration.sessionConfiguration.chatHistoryBufferSize,
                                        }));
                                    }

                                    setSummarize(true);
                                }
                            }}
                            disabled={selectedFiles.length === 0 || !selectedModel || !selectedPromptType || !successfulUploads || !userPrompt}
                        >
                            Summarize
                        </Button>
                    </SpaceBetween>
                </Box>
            }
        >
            <SpaceBetween direction='vertical' size='s'>
                <TextContent>
                    <h4>Document</h4>
                    <p>
                        <small>
                            Upload files to start your summarization chat.
                        </small>
                    </p>
                </TextContent>
                <FileUpload
                    onChange={async ({ detail }) => {
                        setSelectedFiles(detail.value);
                        const uploads = await handleUpload(detail.value, handleError, processFile, [FileTypes.TEXT], 20971520);
                        setSuccessfulUpload(uploads);
                    }}
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
                    constraintText='Allowed file type is plain text. File size limit is 20 MB.'
                />
                <FormField label='Summarization Model'>
                    <Autosuggest
                        statusType={isFetchingModels ? 'loading' : 'finished'}
                        loadingText='Loading models (might take few seconds)...'
                        placeholder='Select a model'
                        empty={<div className='text-gray-500'>No models available.</div>}
                        filteringType='auto'
                        value={selectedModel?.modelId ?? ''}
                        enteredTextLabel={(text) => `Use: "${text}"`}
                        onChange={({ detail: { value } }) => {
                            if (!value || value.length === 0) {
                                setSelectedModel(undefined);
                            } else {
                                const model = allModels.find((model) => model.modelId === value);
                                if (model) {
                                    if (model.streaming !== chatConfiguration.sessionConfiguration.streaming) {
                                        setChatConfiguration({ ...chatConfiguration, sessionConfiguration: { ...chatConfiguration.sessionConfiguration, streaming: model.streaming } });
                                    }
                                    setSelectedModel(model);
                                }
                            }
                        }}
                        options={modelsOptions}
                    />
                </FormField>
                <FormField label='Prompt Type'>
                    <Autosuggest
                        placeholder='Select prompt type'
                        filteringType='auto'
                        value={selectedPromptType}
                        enteredTextLabel={(text) => `Use: "${text}"`}
                        onChange={({ detail: { value } }) => {
                            setUserPrompt('');
                            if (value && value.length !== 0) {
                                setSelectedPromptType(promptOptions.filter((option) => option.value === value)[0].label);
                                if (value === 'concise') {
                                    setUserPrompt('Please provide a short summary of the included file context. Do not include any other information.');
                                } else if (value === 'overview') {
                                    setUserPrompt('Please provide a general overview of the major topics addressed in the included file context. It will not exceed 500 words.');
                                } else if (value === 'cod') {
                                    setUserPrompt(`Please generate increasingly concise, entity-dense summaries of the included file context.
Repeat the following 2 steps 5 times.
  - Step 1: Identify 1-3 informative Entities from the included file context which are missing from the previously generated summary and are the most relevant.
  - Step 2: Write a new, denser summary of identical length which covers every entity and detail from the previous summary plus the missing entities.
  A Missing Entity is:
  - Relevant: to the main story
  - Specific: descriptive yet concise (5 words or fewer)
  - Novel: not in the previous summary
  - Faithful: present in the Article
  - Anywhere: located anywhere in the Article
  Guidelines:
  - The first summary should be long (4-5 sentences, approx. 80 words) yet
  highly non-specific, containing little information beyond the entities
  marked as missing.
  - Use overly verbose language and fillers (e.g. “this document discusses”) to reach approx. 80 words.
  - Make every word count: re-write the previous summary to improve flow and make space for additional entities.
  - Make space with fusion, compression, and removal of uninformative phrases like “the article discusses”
  - The summaries should become highly dense and concise yet self-contained, e.g., easily understood without the Article.
  - Missing entities can appear anywhere in the new summary.
  - Never drop entities from the previous summary. If space cannot be made,  add fewer new entities.
-Remember to use the exact same number of words for each summary.`);
                                } else if (value === 'custom') {
                                    setUserPrompt('Write a custom prompt here. For example, ask the model to provide the main 3-10 main points found in the included file context. Please keep this summary concise, not to exceed 400 words.');
                                }
                            }
                        }}
                        options={promptOptions}
                    />
                </FormField>
                {selectedPromptType ? <Textarea
                    key='textarea-prompt-textarea'
                    rows={10}
                    disableBrowserAutocorrect={false}
                    autoFocus
                    onChange={(e) => setUserPrompt(e.detail.value)}
                    onKeyDown={(e) => {
                        if (e.detail.key === 'Enter' && !e.detail.shiftKey) {
                            e.preventDefault();
                        }
                    }}
                    value={userPrompt}
                /> : null}
                <FormField label='Create new chat session'>
                    <Toggle checked={createNewChatSession} onChange={({ detail }) =>
                        setCreateNewChatSession(detail.checked)
                    } />
                </FormField>
            </SpaceBetween>
        </Modal>
    );
};

export default DocumentSummarizationModal;

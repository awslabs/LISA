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
    FileUpload, Autosuggest, Textarea, Grid,
} from '@cloudscape-design/components';
import { FileTypes, LisaChatSession } from '../types';
import { useMemo, useState } from 'react';
import { useAppDispatch } from '../../config/store';
import { useNotificationService } from '../../shared/util/hooks';
import { useGetAllModelsQuery } from '../../shared/reducers/model-management.reducer';
import { IModel, ModelStatus, ModelType } from '../../shared/model/model-management.model';
import { handleUpload } from './FileUploadModals';
import { IChatConfiguration } from '../../shared/model/chat.configurations.model';
import { v4 as uuidv4 } from 'uuid';
import FormField from '@cloudscape-design/components/form-field';

export type DocumentSummarizationModalProps = {
    showDocumentSummarizationModal: boolean;
    setShowDocumentSummarizationModal: (state: boolean) => void;
    fileContext: string;
    setFileContext: (state: string) => void;
    setUserPrompt: (state: string) => void;
    userPrompt: string;
    selectedModel: IModel;
    setSelectedModel: (state: IModel ) => void;
    chatConfiguration: IChatConfiguration;
    setChatConfiguration: (state: IChatConfiguration) => void;
    setInternalSessionId: (state: string ) => void;
    setSession: (state: LisaChatSession) => void;
    userName: string;
    handleSendGenerateRequest: any;
};

export function DocumentSummarizationModal ({
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
    handleSendGenerateRequest
}: DocumentSummarizationModalProps) {
    const [selectedFiles, setSelectedFiles] = useState<File[] | undefined>([]);
    const [successfulUploads, setSuccessfulUpload] = useState<string[] | undefined>(undefined);
    const dispatch = useAppDispatch();
    const notificationService = useNotificationService(dispatch);
    const [customPrompt, setCustomPrompt] = useState<string>(undefined);

    const { data: allModels, isFetching: isFetchingModels } = useGetAllModelsQuery(undefined, {refetchOnMountOrArgChange: 5,
        selectFromResult: (state) => ({
            isFetching: state.isFetching,
            data: (state.data || []).filter((model: IModel) => model.modelType === ModelType.textgen && model.status === ModelStatus.InService && model.features && model.features.includes('summarization')),
        })});
    const modelsOptions = useMemo(() => allModels.map((model) => ({ label: model.modelId, value: model.modelId })), [allModels]);
    const [selectedPromptType, setSelectedPromptType] = useState<string>('');
    const promptOptions = [
        { label: 'Concise - Short Summary (best for small documents)', value: 'concise' },
        { label: 'Overview - Key bullet points (best for large documents)', value: 'overview' },
        { label: 'Chain of Density', value: 'cod' },
        { label: 'Custom - Write your own prompt', value: 'custom' },
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

    return (
        <Modal
            onDismiss={() => {
                setShowDocumentSummarizationModal(false);
                setFileContext('');
                setSelectedFiles([]);
                setUserPrompt('');
                setSelectedModel(undefined);
                setSelectedPromptType(undefined);
                setCustomPrompt(undefined);
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
                                setSelectedPromptType(undefined);
                                setCustomPrompt(undefined);
                            }}
                            variant={'inline-link'}
                        >
                            Cancel
                        </Button>
                        <Button
                            onClick={async () => {
                                if (successfulUploads.length > 0) {
                                    const newSessionId = uuidv4();
                                    setInternalSessionId(newSessionId);
                                    const newSession = {
                                        history: [],
                                        sessionId: newSessionId,
                                        userId: userName,
                                        startTime: new Date(Date.now()).toISOString(),
                                    };
                                    setSession(newSession);

                                    handleSendGenerateRequest();
                                    setShowDocumentSummarizationModal(false);
                                    setSelectedPromptType(undefined);
                                    setSuccessfulUpload(undefined);
                                    setCustomPrompt(undefined);
                                }
                            }}
                            disabled={selectedFiles.length === 0 || !selectedModel || !selectedPromptType || !successfulUploads || (selectedPromptType === 'custom' && !customPrompt)}
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
                    onChange={async ({detail}) => {
                        setSelectedFiles(detail.value);
                        const uploads = await handleUpload(detail.value, handleError, processFile, [FileTypes.TEXT], 10240);
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
                    constraintText='Allowed file type is plain text. File size limit is 10 KB'
                />
                <Grid gridDefinition={[
                    { colspan: { default: 6 } },
                    { colspan: { default: 6 } },
                ]}>
                    <FormField label='Summarization Model'>
                        <Autosuggest
                            statusType={isFetchingModels ? 'loading' : 'finished'}
                            loadingText='Loading models (might take few seconds)...'
                            placeholder='Select a model'
                            empty={<div className='text-gray-500'>No models available.</div>}
                            filteringType='auto'
                            value={selectedModel?.modelId ?? ''}
                            onChange={({ detail: { value } }) => {
                                if (!value || value.length === 0) {
                                    setSelectedModel(undefined);
                                } else {
                                    const model = allModels.find((model) => model.modelId === value);
                                    if (model) {
                                        if (!model.streaming && chatConfiguration.sessionConfiguration.streaming) {
                                            setChatConfiguration({...chatConfiguration, sessionConfiguration: {...chatConfiguration.sessionConfiguration, streaming: false }});
                                        } else if (model.streaming && !chatConfiguration.sessionConfiguration.streaming) {
                                            setChatConfiguration({...chatConfiguration, sessionConfiguration: {...chatConfiguration.sessionConfiguration, streaming: true }});
                                        }
                                        setSelectedModel(model);
                                    }
                                }
                            }}
                            options={modelsOptions}
                        />
                    </FormField>
                    {selectedModel && selectedModel.summarizationOverview && <TextContent>
                        <small>
                            <p>
                                <b>Summarization Overview: </b>{selectedModel.summarizationOverview}
                            </p>
                        </small>
                    </TextContent>}
                </Grid>
                <Grid gridDefinition={[
                    { colspan: { default: 6 } },
                ]}>
                    <FormField label='Prompt Type'>
                        <Autosuggest
                            placeholder='Select prompt type'
                            filteringType='auto'
                            value={selectedPromptType}
                            onChange={({ detail: { value } }) => {
                                setUserPrompt('');
                                if (!value || value.length === 0) {
                                    setSelectedPromptType('');
                                } else {
                                    setSelectedPromptType(promptOptions.filter((option) => option.value === value)[0].label);
                                    if (value === 'concise') {
                                        setUserPrompt('Please provide a short summary of the included file context. Do not include any other information.');
                                    } else if (value === 'overview') {
                                        setUserPrompt('Please provide a general overview of the major topics addressed in the included file context. It will not exceed one page.');
                                    } else if (value === 'cod') {
                                        // TODO
                                    }
                                }
                            }}
                            options={promptOptions}
                        />
                    </FormField>
                </Grid>
                {selectedPromptType && selectedPromptType === 'Custom - Write your own prompt' && <>
                    <Textarea
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
                        placeholder={'Enter custom prompt here'}
                    />
                </>}
            </SpaceBetween>
        </Modal>
    );
}

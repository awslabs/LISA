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

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useAuth } from 'react-oidc-context';
import Form from '@cloudscape-design/components/form';
import Container from '@cloudscape-design/components/container';
import Box from '@cloudscape-design/components/box';
import { v4 as uuidv4 } from 'uuid';
import SpaceBetween from '@cloudscape-design/components/space-between';
import {
    Autosuggest,
    ButtonGroup,
    ButtonGroupProps,
    Grid,
    PromptInput,
    TextContent,
} from '@cloudscape-design/components';
import StatusIndicator from '@cloudscape-design/components/status-indicator';

import Message from './Message';
import { LisaChatMessage, LisaChatMessageMetadata, LisaChatSession, StatusTypes } from '../types';
import { formatDocumentsAsString, formatDocumentTitlesAsString, RESTAPI_URI, RESTAPI_VERSION } from '../utils';
import { LisaChatMessageHistory } from '../adapters/lisa-chat-history';
import RagControls, { RagConfig } from './RagOptions';
import { ContextUploadModal, RagUploadModal } from './FileUploadModals';
import { ChatOpenAI } from '@langchain/openai';
import { useGetAllModelsQuery } from '../../shared/reducers/model-management.reducer';
import { IModel, ModelStatus, ModelType } from '../../shared/model/model-management.model';
import { useLazyGetConfigurationQuery } from '../../shared/reducers/configuration.reducer';
import {
    useGetSessionHealthQuery,
    useLazyGetSessionByIdQuery,
    useUpdateSessionMutation,
} from '../../shared/reducers/session.reducer';
import { useAppDispatch } from '../../config/store';
import { useNotificationService } from '../../shared/util/hooks';
import SessionConfiguration from './SessionConfiguration';
import PromptTemplateEditor from './PromptTemplateEditor';
import { baseConfig, GenerateLLMRequestParams, IChatConfiguration } from '../../shared/model/chat.configurations.model';
import { useLazyGetRelevantDocumentsQuery } from '../../shared/reducers/rag.reducer';
import { IConfiguration } from '../../shared/model/configuration.model';
import { DocumentSummarizationModal } from './DocumentSummarizationModal';
import { ChatMemory } from '../../shared/util/chat-memory';
import { setBreadcrumbs } from '../../shared/reducers/breadcrumbs.reducer';
import { truncateText } from '../../shared/util/formats';

export default function Chat ({ sessionId }) {
    const dispatch = useAppDispatch();
    const notificationService = useNotificationService(dispatch);

    const [getRelevantDocuments] = useLazyGetRelevantDocumentsQuery();
    const {data: sessionHealth} = useGetSessionHealthQuery(undefined, {refetchOnMountOrArgChange: true});
    const [getSessionById] = useLazyGetSessionByIdQuery();
    const [updateSession] = useUpdateSessionMutation();
    const { data: allModels, isFetching: isFetchingModels } = useGetAllModelsQuery(undefined, {refetchOnMountOrArgChange: 5,
        selectFromResult: (state) => ({
            isFetching: state.isFetching,
            data: (state.data || []).filter((model) => model.modelType === ModelType.textgen && model.status === ModelStatus.InService),
        })});
    const [getConfiguration] = useLazyGetConfigurationQuery();
    const [config, setConfig] = useState<IConfiguration>();
    const [chatConfiguration, setChatConfiguration] = useState<IChatConfiguration>(baseConfig);

    const [userPrompt, setUserPrompt] = useState('');
    const [fileContext, setFileContext] = useState('');

    const [sessionConfigurationModalVisible, setSessionConfigurationModalVisible] = useState(false);
    const [promptTemplateEditorVisible, setPromptTemplateEditorVisible] = useState(false);
    const [showContextUploadModal, setShowContextUploadModal] = useState(false);
    const [showRagUploadModal, setShowRagUploadModal] = useState(false);
    const [showDocumentSummarizationModal, setShowDocumentSummarizationModal] = useState(false);

    const modelsOptions = useMemo(() => allModels.map((model) => ({ label: model.modelId, value: model.modelId })), [allModels]);
    const [selectedModel, setSelectedModel] = useState<IModel>();
    const [dirtySession, setDirtySession] = useState(false);
    const [session, setSession] = useState<LisaChatSession>({
        history: [],
        sessionId: '',
        userId: '',
        startTime: new Date(Date.now()).toISOString(),
    });
    const [internalSessionId, setInternalSessionId] = useState<string | null>(null);
    const [loadingSession, setLoadingSession] = useState(false);

    const [isConnected, setIsConnected] = useState(false);
    const [metadata, setMetadata] = useState<LisaChatMessageMetadata>({});
    const [useRag, setUseRag] = useState(false);
    const [ragConfig, setRagConfig] = useState<RagConfig>({} as RagConfig);
    const [memory, setMemory] = useState(
        new ChatMemory({
            chatHistory: new LisaChatMessageHistory(session),
            returnMessages: false,
            memoryKey: 'history',
            k: chatConfiguration.sessionConfiguration.chatHistoryBufferSize,
        }),
    );
    const bottomRef = useRef(null);
    const auth = useAuth();

    const fetchRelevantDocuments = async (query: string) => {
        const { ragTopK = 3 } = chatConfiguration.sessionConfiguration;

        return getRelevantDocuments({
            query,
            repositoryId: ragConfig.repositoryId,
            repositoryType: ragConfig.repositoryType,
            modelName: ragConfig.embeddingModel.modelId,
            topK: ragTopK,
        });
    };

    const useChatGeneration = () => {
        const [isRunning, setIsRunning] = useState(false);
        const [isStreaming, setIsStreaming] = useState(false);

        const generateResponse = async (params: GenerateLLMRequestParams) => {
            setIsRunning(true);
            try {
                const llmClient = createOpenAiClient(chatConfiguration.sessionConfiguration.streaming);

                // Convert chat history to messages format
                const messages = session.history.concat(params.message).map((msg) => ({
                    role: msg.type === 'human' ? 'user' : msg.type === 'ai' ? 'assistant' : 'system',
                    content: Array.isArray(msg.content) ? msg.content : [{ type: 'text', text: msg.content }]
                }));

                if (chatConfiguration.sessionConfiguration.streaming) {
                    setIsStreaming(true);
                    setSession((prev) => ({
                        ...prev,
                        history: [...prev.history, new LisaChatMessage({ type: 'ai', content: '', metadata: { ...metadata, ...params.message[params.message.length - 1].metadata }})],
                    }));

                    try {
                        const stream = await llmClient.stream(messages);
                        const resp: string[] = [];
                        for await (const chunk of stream) {
                            const content = chunk.content as string;
                            setSession((prev) => {
                                const lastMessage = prev.history[prev.history.length - 1];
                                return {
                                    ...prev,
                                    history: [...prev.history.slice(0, -1),
                                        new LisaChatMessage({
                                            ...lastMessage,
                                            content: lastMessage.content + content
                                        })
                                    ],
                                };
                            });
                            resp.push(content);
                        }
                        await memory.saveContext({ input: params.input }, { output: resp.join('') });
                        setIsStreaming(false);
                    } catch (exception) {
                        setSession((prev) => ({
                            ...prev,
                            history: prev.history.slice(0, -1),
                        }));
                        throw exception;
                    }
                } else {
                    const response = await llmClient.invoke(messages);
                    const content = response.content as string;
                    await memory.saveContext({ input: params.input }, { output: content });
                    setSession((prev) => ({
                        ...prev,
                        history: [...prev.history, new LisaChatMessage({ type: 'ai', content, metadata })],
                    }));
                }
            } catch (error) {
                notificationService.generateNotification('An error occurred while processing your request.', 'error', undefined, error.error?.message ? <p>{JSON.stringify(error.error.message)}</p> : undefined);
                setIsRunning(false);
                throw error;
            } finally {
                setIsRunning(false);
            }
        };

        return { isRunning, isStreaming, generateResponse };
    };

    const {isRunning, isStreaming, generateResponse} = useChatGeneration();

    useEffect(() => {
        if (sessionHealth) {
            setIsConnected(true);
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [sessionHealth]);

    useEffect(() => {
        if (!auth.isLoading && auth.isAuthenticated) {
            getConfiguration('global').then((resp) => {
                if (resp.data && resp.data.length > 0) {
                    setConfig(resp.data[0]);
                }
            });
        }
    }, [auth, getConfiguration]);

    useEffect(() => {
        if (!isRunning && session.history.length && dirtySession) {
            if (session.history.at(-1).type === 'ai' && !auth.isLoading) {
                setDirtySession(false);
                updateSession(session);
            }
        }
    }, [isRunning, session, dirtySession, auth, updateSession]);

    useEffect(() => {
        if (sessionId) {
            setInternalSessionId(sessionId);
            setLoadingSession(true);
            setSession({...session, history: []});
            dispatch(setBreadcrumbs([{
                text: 'Chatbot',
                href: ''
            }, {
                text: 'Loading session...',
                href: ''
            }]));

            getSessionById(sessionId).then((resp) => {
                // session doesn't exist so we create it
                let sess: LisaChatSession = resp.data;
                if (sess.history === undefined) {
                    sess = {
                        history: [],
                        sessionId: sessionId,
                        userId: auth.user?.profile.sub,
                        startTime: new Date(Date.now()).toISOString(),
                    };
                }
                setSession(sess);
                const firstHumanMessage = sess.history?.find((hist) => hist.type === 'human')?.content;

                // override the default breadcrumbs
                dispatch(setBreadcrumbs([{
                    text: 'Chatbot',
                    href: ''
                }, {
                    text: truncateText(Array.isArray(firstHumanMessage) ? firstHumanMessage.find((item) => item.type === 'text')?.text || '' : firstHumanMessage) || 'New Session',
                    href: ''
                }]));
                setLoadingSession(false);
            });
        } else {
            const newSessionId = uuidv4();
            setInternalSessionId(newSessionId);
            const newSession = {
                history: [],
                sessionId: newSessionId,
                userId: auth.user?.profile.sub,
                startTime: new Date(Date.now()).toISOString(),
            };
            setSession(newSession);
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [sessionId]);

    useEffect(() => {
        setMemory(
            new ChatMemory({
                chatHistory: new LisaChatMessageHistory(session),
                returnMessages: false,
                memoryKey: 'history',
                k: chatConfiguration.sessionConfiguration.chatHistoryBufferSize,
            }),
        );
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [userPrompt]);

    useEffect(() => {
        if (selectedModel && auth.isAuthenticated) {
            memory.loadMemoryVariables().then(async () => {
                const metadata: LisaChatMessageMetadata = {
                    modelName: selectedModel.modelId,
                    modelKwargs: {
                        max_tokens: chatConfiguration.sessionConfiguration.max_tokens,
                        modelKwargs: chatConfiguration.sessionConfiguration.modelArgs,
                    },
                    userId: auth.user.profile.sub,
                };
                setMetadata(metadata);
            });
        }

        if(selectedModel && selectedModel?.features.filter(feature => feature.name === 'imageInput').length === 0 && fileContext.startsWith('File context: data:image')) {
            setFileContext('');
            notificationService.generateNotification(`Removed file from context as new model doesn't support image input`, 'info');
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [selectedModel, chatConfiguration.sessionConfiguration.modelArgs, auth, userPrompt]);

    useEffect(() => {
        if (bottomRef) {
            bottomRef?.current.scrollIntoView({ behavior: 'smooth' });
        }
    }, [session]);

    const createOpenAiClient = (streaming: boolean) => {
        const modelConfig = {
            modelName: selectedModel?.modelId,
            openAIApiKey: auth.user?.id_token,
            configuration: {
                baseURL: `${RESTAPI_URI}/${RESTAPI_VERSION}/serve`,
            },
            streaming,
            maxTokens: chatConfiguration.sessionConfiguration?.max_tokens,
            modelKwargs: {
                ...chatConfiguration.sessionConfiguration?.modelArgs,
                ...(fileContext?.startsWith('File context: data:image') && {
                    model: selectedModel?.modelId,
                    max_tokens: chatConfiguration.sessionConfiguration?.max_tokens
                })
            }
        };

        return new ChatOpenAI(modelConfig);
    };

    const handleSendGenerateRequest = useCallback(async () => {
        if (!userPrompt.trim()) return;

        const messages = [];

        if (session.history.length === 0){
            messages.push(new LisaChatMessage({
                type: 'system',
                content: chatConfiguration.promptConfiguration.promptTemplate,
                metadata: {},
            }));
        }

        let messageContent, ragDocs;

        if (fileContext?.startsWith('File context: data:image')) {
            const imageData = fileContext.replace('File context: ', '');
            messageContent = [
                { type: 'text', text: userPrompt },
                { type: 'image_url', image_url: { url: `${imageData}` } }
            ];
        } else if (useRag){
            ragDocs =  await fetchRelevantDocuments(userPrompt);
            const serialized = `${fileContext}\n${formatDocumentsAsString(ragDocs.data?.docs)}`;

            messages.push(new LisaChatMessage({
                type: 'system',
                content: serialized,
                metadata: {},
            }));
            messageContent = userPrompt;
        } else if (fileContext) {
            messages.push(new LisaChatMessage({
                type: 'system',
                content: fileContext,
                metadata: {},
            }));
            messageContent = userPrompt;
        } else {
            messageContent = userPrompt;
        }

        messages.push(new LisaChatMessage({
            type: 'human',
            content: messageContent,
            metadata: {
                ...useRag ? {
                    ragContext: formatDocumentsAsString(ragDocs.data?.docs, true),
                    ragDocuments: formatDocumentTitlesAsString(ragDocs.data?.docs)
                } : {}
            },
        }));

        setSession((prev) => ({
            ...prev,
            history: prev.history.concat(...messages),
        }));

        const params: GenerateLLMRequestParams = {
            input: userPrompt,
            message: messages,
        };

        setUserPrompt('');

        await generateResponse({
            ...params
        });

        setDirtySession(true);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [userPrompt, useRag, fileContext, chatConfiguration.promptConfiguration.promptTemplate, generateResponse]);

    return (
        <div className='h-[80vh]'>
            <PromptTemplateEditor
                chatConfiguration={chatConfiguration}
                setChatConfiguration={setChatConfiguration}
                setVisible={setPromptTemplateEditorVisible}
                visible={promptTemplateEditorVisible}
            />
            <DocumentSummarizationModal
                showDocumentSummarizationModal={showDocumentSummarizationModal}
                setShowDocumentSummarizationModal={setShowDocumentSummarizationModal}
                fileContext={fileContext}
                setFileContext={setFileContext}
                setUserPrompt={setUserPrompt}
                userPrompt={userPrompt}
                selectedModel={selectedModel}
                setSelectedModel={setSelectedModel}
                chatConfiguration={chatConfiguration}
                setChatConfiguration={setChatConfiguration}
                userName={auth.user?.profile.sub}
                setInternalSessionId={setInternalSessionId}
                setSession={setSession}
                handleSendGenerateRequest={handleSendGenerateRequest}
                setMemory={setMemory}
            />
            <SessionConfiguration
                chatConfiguration={chatConfiguration}
                setChatConfiguration={setChatConfiguration}
                selectedModel={selectedModel}
                isRunning={isRunning}
                visible={sessionConfigurationModalVisible}
                setVisible={setSessionConfigurationModalVisible}
                systemConfig={config}
            />
            <RagUploadModal
                ragConfig={ragConfig}
                showRagUploadModal={showRagUploadModal}
                setShowRagUploadModal={setShowRagUploadModal}
            />
            <ContextUploadModal
                showContextUploadModal={showContextUploadModal}
                setShowContextUploadModal={setShowContextUploadModal}
                fileContext={fileContext}
                setFileContext={setFileContext}
                selectedModel={selectedModel}
            />
            <div className='overflow-y-auto h-[calc(100vh-25rem)] bottom-8'>
                <SpaceBetween direction='vertical' size='l'>
                    {session.history.map((message, idx) => (
                        <Message key={idx} message={message} showMetadata={chatConfiguration.sessionConfiguration.showMetadata} isRunning={false} isStreaming={isStreaming && idx === session.history.length - 1} markdownDisplay={chatConfiguration.sessionConfiguration.markdownDisplay}/>
                    ))}
                    {isRunning && !isStreaming && <Message isRunning={isRunning} markdownDisplay={chatConfiguration.sessionConfiguration.markdownDisplay}/>}
                    <div ref={bottomRef} />
                </SpaceBetween>
            </div>
            <div className='sticky bottom-8'>
                <form onSubmit={(e) => e.preventDefault()}>
                    <Form>
                        <Container>
                            <SpaceBetween size='m' direction='vertical'>
                                <Grid
                                    gridDefinition={[
                                        { colspan: { default: 4 } },
                                        { colspan: { default: 8} },
                                    ]}
                                >
                                    <Autosuggest
                                        disabled={isRunning}
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
                                    {window.env.RAG_ENABLED && (
                                        <RagControls
                                            isRunning={isRunning}
                                            setUseRag={setUseRag}
                                            setRagConfig={setRagConfig}
                                        />
                                    )}
                                </Grid>
                                <PromptInput
                                    value={userPrompt}
                                    actionButtonAriaLabel='Send message'
                                    actionButtonIconName='send'
                                    maxRows={4}
                                    minRows={2}
                                    spellcheck={true}
                                    placeholder={
                                        !selectedModel ? 'You must select a model before sending a message' : 'Send a message'
                                    }
                                    disabled={!selectedModel || loadingSession}
                                    onChange={({ detail }) => setUserPrompt(detail.value)}
                                    onAction={userPrompt.length > 0 && !isRunning && !loadingSession && handleSendGenerateRequest}
                                    secondaryActions={
                                        <Box padding={{ left: 'xxs', top: 'xs' }}>
                                            <ButtonGroup
                                                ariaLabel='Chat actions'
                                                onItemClick={({detail}) => {
                                                    if (detail.id === 'settings'){
                                                        setSessionConfigurationModalVisible(true);
                                                    }
                                                    if (detail.id === 'edit-prompt-template'){
                                                        setPromptTemplateEditorVisible(true);
                                                    }
                                                    if (detail.id === 'upload-to-rag'){
                                                        setShowRagUploadModal(true);
                                                    }
                                                    if (detail.id === 'add-file-to-context'){
                                                        setShowContextUploadModal(true);
                                                    }
                                                    if ( detail.id === 'summarize-document') {
                                                        setShowDocumentSummarizationModal(true);
                                                    }
                                                }}
                                                items={[
                                                    {
                                                        type: 'icon-button',
                                                        id: 'settings',
                                                        iconName: 'settings',
                                                        text: 'Session configuration'
                                                    },
                                                    ...(config?.configuration.enabledComponents.uploadRagDocs && window.env.RAG_ENABLED ?
                                                        [{
                                                            type: 'icon-button',
                                                            id: 'upload-to-rag',
                                                            iconName: 'upload',
                                                            text: 'Upload to RAG'
                                                        }] as ButtonGroupProps.Item[] : []),
                                                    ...(config?.configuration.enabledComponents.uploadContextDocs ?
                                                        [{
                                                            type: 'icon-button',
                                                            id: 'add-file-to-context',
                                                            iconName: 'insert-row',
                                                            text: 'Add file to context'
                                                        }] as ButtonGroupProps.Item[] : []),
                                                    ...(config?.configuration.enabledComponents.documentSummarization ? [{
                                                        type: 'icon-button',
                                                        id: 'summarize-document',
                                                        iconName: 'transcript',
                                                        text: 'Summarize Document'
                                                    }] as ButtonGroupProps.Item[] : []),
                                                    ...(config?.configuration.enabledComponents.editPromptTemplate ?
                                                        [{
                                                            type: 'menu-dropdown',
                                                            id: 'more-actions',
                                                            text: 'Additional Configuration',
                                                            items: [
                                                                {
                                                                    id: 'edit-prompt-template',
                                                                    iconName: 'contact',
                                                                    text: 'Edit Prompt Template'
                                                                },
                                                            ]
                                                        }] as ButtonGroupProps.Item[] : [])
                                                ]}
                                                variant='icon'
                                            />
                                        </Box>
                                    }
                                />
                                <SpaceBetween direction='vertical' size='xs'>
                                    <Grid gridDefinition={[{ colspan:6 }, { colspan:6 }]}>
                                        <Box float='left' variant='div'>
                                            <TextContent>
                                                <div style={{ paddingBottom: 8 }} className='text-xs text-gray-500'>
                                                    Session ID: {internalSessionId}
                                                </div>
                                            </TextContent>
                                        </Box>
                                        <Box float='right' variant='div'>
                                            <StatusIndicator type={isConnected ? 'success' : 'error'}>
                                                {isConnected ? 'Connected' : 'Disconnected'}
                                            </StatusIndicator>
                                        </Box>
                                    </Grid>
                                </SpaceBetween>
                            </SpaceBetween>
                        </Container>
                    </Form>
                </form>
            </div>
        </div>
    );
}

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

import { useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { useAuth } from 'react-oidc-context';
import Form from '@cloudscape-design/components/form';
import Container from '@cloudscape-design/components/container';
import Box from '@cloudscape-design/components/box';
import { v4 as uuidv4 } from 'uuid';
import SpaceBetween from '@cloudscape-design/components/space-between';
import {
    Autosuggest,
    Button,
    ButtonGroup,
    ButtonGroupProps,
    Grid,
    Header,
    PromptInput,
    TextContent,
} from '@cloudscape-design/components';
import StatusIndicator from '@cloudscape-design/components/status-indicator';

import Message from './Message';
import { LisaChatMessage, LisaChatMessageMetadata, LisaChatSession } from '../types';
import { formatDocumentsAsString, formatDocumentTitlesAsString, RESTAPI_URI, RESTAPI_VERSION } from '../utils';
import { LisaChatMessageHistory } from '../adapters/lisa-chat-history';
import RagControls, { RagConfig } from './RagOptions';
import { ContextUploadModal, RagUploadModal } from './FileUploadModals';
import { ChatOpenAI } from '@langchain/openai';
import { useGetAllModelsQuery } from '../../shared/reducers/model-management.reducer';
import { IModel, ModelStatus, ModelType } from '../../shared/model/model-management.model';
import {
    useGetSessionHealthQuery,
    useLazyGetSessionByIdQuery,
    useUpdateSessionMutation,
} from '../../shared/reducers/session.reducer';
import { useAppDispatch } from '../../config/store';
import { useNotificationService } from '../../shared/util/hooks';
import SessionConfiguration from './SessionConfiguration';
import { baseConfig, GenerateLLMRequestParams, IChatConfiguration } from '../../shared/model/chat.configurations.model';
import { useLazyGetRelevantDocumentsQuery } from '../../shared/reducers/rag.reducer';
import { IConfiguration } from '../../shared/model/configuration.model';
import { DocumentSummarizationModal } from './DocumentSummarizationModal';
import { ChatMemory } from '../../shared/util/chat-memory';
import { setBreadcrumbs } from '../../shared/reducers/breadcrumbs.reducer';
import { useNavigate } from 'react-router-dom';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faFileLines, faMessage, faPenToSquare } from '@fortawesome/free-regular-svg-icons';
import { PromptTemplateModal } from '../prompt-templates-library/PromptTemplateModal';
import ConfigurationContext from '../../shared/configuration.provider';

export default function Chat ({ sessionId }) {
    const dispatch = useAppDispatch();
    const navigate = useNavigate();
    const config: IConfiguration = useContext(ConfigurationContext);
    const notificationService = useNotificationService(dispatch);
    const modelSelectRef = useRef<HTMLInputElement>(null);

    const [getRelevantDocuments] = useLazyGetRelevantDocumentsQuery();
    const {data: sessionHealth} = useGetSessionHealthQuery(undefined, {refetchOnMountOrArgChange: true});
    const [getSessionById] = useLazyGetSessionByIdQuery();
    const [updateSession] = useUpdateSessionMutation();
    const { data: allModels, isFetching: isFetchingModels } = useGetAllModelsQuery(undefined, {refetchOnMountOrArgChange: 5,
        selectFromResult: (state) => ({
            isFetching: state.isFetching,
            data: (state.data || []).filter((model) => model.modelType === ModelType.textgen && model.status === ModelStatus.InService),
        })});
    const [chatConfiguration, setChatConfiguration] = useState<IChatConfiguration>(baseConfig);

    const [userPrompt, setUserPrompt] = useState('');
    const [fileContext, setFileContext] = useState('');

    const [sessionConfigurationModalVisible, setSessionConfigurationModalVisible] = useState(false);
    const [promptTemplateKey, setPromptTemplateKey] = useState(new Date().toISOString());
    const [showContextUploadModal, setShowContextUploadModal] = useState(false);
    const [showRagUploadModal, setShowRagUploadModal] = useState(false);
    const [showDocumentSummarizationModal, setShowDocumentSummarizationModal] = useState(false);
    const [showPromptTemplateModal, setShowPromptTemplateModal] = useState(false);

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
                let messages = session.history.concat(params.message).map((msg) => ({
                    role: msg.type === 'human' ? 'user' : msg.type === 'ai' ? 'assistant' : 'system',
                    content: Array.isArray(msg.content) ? msg.content : [{ type: 'text', text: msg.content }]
                }));

                const [systemMessage, ...remainingMessages] = messages;
                messages = [systemMessage, ...remainingMessages.slice(-(chatConfiguration.sessionConfiguration.chatHistoryBufferSize * 2) - 1)];

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

        return { isRunning, setIsRunning, isStreaming, generateResponse };
    };

    const {isRunning, setIsRunning, isStreaming, generateResponse} = useChatGeneration();

    useEffect(() => {
        if (sessionHealth) {
            setIsConnected(true);
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [sessionHealth]);

    useEffect(() => {
        if (!isRunning && session.history.length && dirtySession) {
            if (session.history.at(-1).type === 'ai' && !auth.isLoading) {
                setDirtySession(false);
                updateSession(session);
            }
        }
    }, [isRunning, session, dirtySession, auth, updateSession]);

    useEffect(() => {
        // always hide breadcrumbs
        dispatch(setBreadcrumbs([]));

        if (sessionId) {
            setInternalSessionId(sessionId);
            setLoadingSession(true);
            setSession({...session, history: []});

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

        if (selectedModel && selectedModel?.features?.filter((feature) => feature.name === 'imageInput')?.length === 0 && fileContext.startsWith('File context: data:image')) {
            setFileContext('');
            notificationService.generateNotification('Removed file from context as new model doesn\'t support image input', 'info');
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
            maxRetries: 0,
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
        setIsRunning(true);

        setSession((prev) => ({
            ...prev,
            history: prev.history.concat(new LisaChatMessage({
                type: 'human',
                content: userPrompt,
                metadata: {},
            }))
        }));

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
                { type: 'image_url', image_url: { url: `${imageData}` } },
                { type: 'text', text: userPrompt },
            ];
        } else if (useRag){
            ragDocs =  await fetchRelevantDocuments(userPrompt);
            messageContent = [
                { type: 'text', text: 'File context: ' + formatDocumentsAsString(ragDocs.data?.docs)},
                { type: 'text', text: userPrompt },
            ];
        } else if (fileContext) {
            messageContent = [
                { type: 'text', text: fileContext },
                { type: 'text', text: userPrompt },
            ];
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
            history: prev.history.slice(0, -1).concat(...messages),
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
            <PromptTemplateModal
                session={session}
                showModal={showPromptTemplateModal}
                setShowModal={setShowPromptTemplateModal}
                setUserPrompt={setUserPrompt}
                setSelectedModel={setSelectedModel}
                chatConfiguration={chatConfiguration}
                setChatConfiguration={setChatConfiguration}
                key={promptTemplateKey}
                config={config}
            />
            {session.history.length !== 0 && <SpaceBetween alignItems='end' size='l'>
                <Button
                    ariaLabel='Download Session'
                    iconAlign='right'
                    iconName='download'
                    disabled={isRunning}
                    onClick={() => {
                        const element = document.createElement('a');
                        const file = new Blob([JSON.stringify(session, null, 2)], { type: 'application/json' });
                        element.href = URL.createObjectURL(file);
                        element.download = `${session.sessionId}.json`;
                        document.body.appendChild(element); // Required for this to work in FireFox
                        element.click();
                        element.remove();
                    }}
                >
                    Download Session
                </Button>
            </SpaceBetween>}
            <div className='overflow-y-auto h-[calc(100vh-25rem)] bottom-8'>
                <SpaceBetween direction='vertical' size='l'>
                    {session.history.map((message, idx) => (
                        <Message key={idx} message={message} showMetadata={chatConfiguration.sessionConfiguration.showMetadata} isRunning={false} isStreaming={isStreaming && idx === session.history.length - 1} markdownDisplay={chatConfiguration.sessionConfiguration.markdownDisplay}/>
                    ))}
                    {isRunning && !isStreaming && <Message isRunning={isRunning} markdownDisplay={chatConfiguration.sessionConfiguration.markdownDisplay} message={new LisaChatMessage({type: 'ai', content: ''})}/>}
                    { session.history.length === 0 && sessionId === undefined && <div style={{height: '400px', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', gap: '2em', textAlign: 'center'}}>
                        <div>
                            <Header variant='h1'>What would you like to do?</Header>
                        </div>
                        <div style={{display: 'flex', flexDirection: 'row', justifyContent: 'center', alignItems: 'center', gap: '1em', textAlign: 'center'}}>
                            <Button variant='normal' onClick={() => {
                                navigate(`/ai-assistant/${uuidv4()}`);
                                modelSelectRef?.current?.focus();
                            }}>
                                <SpaceBetween direction='horizontal' size='xs'>
                                    <FontAwesomeIcon icon={faMessage} />
                                    <TextContent>Start chatting</TextContent>
                                </SpaceBetween>
                            </Button>

                            { config?.configuration?.enabledComponents?.editPromptTemplate && (
                                <Button variant='normal' onClick={() => {
                                    setPromptTemplateKey(new Date().toISOString());
                                    setShowPromptTemplateModal(true);
                                }}>
                                    <SpaceBetween direction='horizontal' size='xs'>
                                        <FontAwesomeIcon icon={faPenToSquare} />
                                        <TextContent>Select Persona</TextContent>
                                    </SpaceBetween>
                                </Button>
                            )}

                            <Button variant='normal' onClick={() => setShowDocumentSummarizationModal(true)}>
                                <SpaceBetween direction='horizontal' size='xs'>
                                    <FontAwesomeIcon icon={faFileLines} />
                                    <TextContent>Summarize a doc</TextContent>
                                </SpaceBetween>
                            </Button>
                        </div>
                    </div>}
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
                                        ref={modelSelectRef}
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
                                                        setPromptTemplateKey(new Date().toISOString());
                                                        setShowPromptTemplateModal(true);
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
                                                                    text: 'Edit Persona'
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

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

import { useState, useRef, useCallback, useEffect, useMemo } from 'react';
import { useAuth } from 'react-oidc-context';
import Form from '@cloudscape-design/components/form';
import Container from '@cloudscape-design/components/container';
import Box from '@cloudscape-design/components/box';
import { v4 as uuidv4 } from 'uuid';
import SpaceBetween from '@cloudscape-design/components/space-between';
import { Grid, TextContent, PromptInput, Autosuggest, ButtonGroup } from '@cloudscape-design/components';
import StatusIndicator from '@cloudscape-design/components/status-indicator';

import Message from './Message';
import { LisaChatMessage, LisaChatSession, LisaChatMessageMetadata } from '../types';
import { RESTAPI_URI, formatDocumentsAsString, RESTAPI_VERSION } from '../utils';
import { LisaChatMessageHistory } from '../adapters/lisa-chat-history';
import { ChatPromptTemplate, MessagesPlaceholder, PromptTemplate } from '@langchain/core/prompts';
import { RunnableSequence } from '@langchain/core/runnables';
import { StringOutputParser } from '@langchain/core/output_parsers';
import { BufferWindowMemory } from 'langchain/memory';
import RagControls, { RagConfig } from './RagOptions';
import { ContextUploadModal, RagUploadModal } from './FileUploadModals';
import { ChatOpenAI } from '@langchain/openai';
import { useGetAllModelsQuery } from '../../shared/reducers/model-management.reducer';
import { IModel, ModelStatus, ModelType } from '../../shared/model/model-management.model';
import {
    configurationApi,
    useLazyGetConfigurationQuery
} from '../../shared/reducers/configuration.reducer';
import {
    useGetSessionHealthQuery,
    useLazyGetSessionByIdQuery,
    useUpdateSessionMutation
} from '../../shared/reducers/session.reducer';
import { useAppDispatch } from '../../config/store';
import { useNotificationService } from '../../shared/util/hooks';
import SessionConfiguration from './SessionConfiguration';
import PromptTemplateEditor from './PromptTemplateEditor';
import { IChatConfiguration } from '../../shared/model/chat.configurations.model';
import { useLazyGetRelevantDocumentsQuery } from '../../shared/reducers/rag.reducer';
import { IConfiguration } from '../../shared/model/configuration.model';

export default function Chat ({ sessionId }) {
    const dispatch = useAppDispatch();
    const notificationService = useNotificationService(dispatch);
    const [getConfiguration] = useLazyGetConfigurationQuery();
    const [config, setConfig] = useState<IConfiguration>();
    const {data: sessionHealth} = useGetSessionHealthQuery(undefined, {refetchOnMountOrArgChange: true});
    const [getSessionById] = useLazyGetSessionByIdQuery();
    const [updateSession] = useUpdateSessionMutation();
    const [userPrompt, setUserPrompt] = useState('');
    const [fileContext, setFileContext] = useState('');

    const [sessionConfigurationModalVisible, setSessionConfigurationModalVisible] = useState(false);
    const { data: allModels, isFetching: isFetchingModels } = useGetAllModelsQuery(undefined, {refetchOnMountOrArgChange: 5,
        selectFromResult: (state) => ({
            isFetching: state.isFetching,
            data: (state.data || []).filter((model) => model.modelType === ModelType.textgen && model.status === ModelStatus.InService),
        })});
    const modelsOptions = useMemo(() => allModels.map((model) => ({ label: model.modelId, value: model.modelId })), [allModels]);
    const [selectedModel, setSelectedModel] = useState<IModel>();
    const [session, setSession] = useState<LisaChatSession>({
        history: [],
        sessionId: '',
        userId: '',
        startTime: new Date(Date.now()).toISOString(),
    });

    const [isStreaming, setIsStreaming] = useState(false);
    const [isConnected, setIsConnected] = useState(false);
    const [isRunning, setIsRunning] = useState(false);
    const [metadata, setMetadata] = useState<LisaChatMessageMetadata>({});
    const [internalSessionId, setInternalSessionId] = useState<string | null>(null);
    const [promptTemplateEditorVisible, setPromptTemplateEditorVisible] = useState(false);
    const [showContextUploadModal, setShowContextUploadModal] = useState(false);
    const [showRagUploadModal, setShowRagUploadModal] = useState(false);
    const [getRelevantDocuments] = useLazyGetRelevantDocumentsQuery();

    const [chatConfiguration, setChatConfiguration] = useState<IChatConfiguration>({
        promptConfiguration: {
            promptTemplate: `The following is a friendly conversation between a human and an AI. The AI is talkative and provides lots of specific details from its context. If the AI does not know the answer to a question, it truthfully says it does not know.

                              Current conversation:
                              {history}
                              {humanPrefix}: {input}
                              {aiPrefix}:`,
            humanPrefix: 'User',
            aiPrefix: 'Assistant',
        },
        sessionConfiguration: {
            streaming: false,
            showMetadata: false,
            max_tokens: null,
            chatHistoryBufferSize: 3,
            ragTopK: 3,
            modelArgs: {
                n: null,
                top_p: 0.01,
                frequency_penalty: null,
                presence_penalty: null,
                temperature: null,
                seed: null,
                stop: ['\nUser:', '\n User:', 'User:', 'User'],
            }
        }
    });

    const [ragContext, setRagContext] = useState('');
    const [useRag, setUseRag] = useState(false);
    const [ragConfig, setRagConfig] = useState<RagConfig>({} as RagConfig);
    const [memory, setMemory] = useState(
        new BufferWindowMemory({
            chatHistory: new LisaChatMessageHistory(session),
            returnMessages: false,
            memoryKey: 'history',
            k: chatConfiguration.sessionConfiguration.chatHistoryBufferSize,
            aiPrefix: chatConfiguration.promptConfiguration.aiPrefix,
            humanPrefix: chatConfiguration.promptConfiguration.humanPrefix,
        }),
    );
    const bottomRef = useRef(null);
    const auth = useAuth();

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
        if (!isRunning && session.history.length) {
            if (session.history.at(-1).type === 'ai' && !auth.isLoading) {
                updateSession(session);
            }
        }
        if (auth.isAuthenticated){
            dispatch(configurationApi.util.invalidateTags(['configuration']));
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isRunning, session, auth]);

    useEffect(() => {
        if (sessionId) {
            setInternalSessionId(sessionId);
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
        const promptNeedsContext = fileContext || useRag;
        const promptIncludesContext = chatConfiguration.promptConfiguration.promptTemplate.indexOf('{context}') > -1;

        if (promptNeedsContext && !promptIncludesContext) {
            // Add context parameter to prompt if using local file context or RAG
            // New lines included to maintain formatting in the prompt template UI
            const modifiedText = chatConfiguration.promptConfiguration.promptTemplate.replace(
                'Current conversation:',
                ` {context}

          Current conversation:`,
            );
            setChatConfiguration({...chatConfiguration, promptConfiguration: {...chatConfiguration.promptConfiguration, promptTemplate: modifiedText}});
        } else if (!promptNeedsContext && promptIncludesContext) {
            // Remove context from the prompt
            const modifiedText = chatConfiguration.promptConfiguration.promptTemplate.replace('{context}', '');
            setChatConfiguration({...chatConfiguration, promptConfiguration: {...chatConfiguration.promptConfiguration, promptTemplate: modifiedText}});
        }
    // Disabling exhaustive-deps here because we are updating the promptTemplate so we can't trigger
    // this on promptTemplate updating or we would end up in a render loop.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [fileContext, useRag]);

    useEffect(() => {
        setMemory(
            new BufferWindowMemory({
                chatHistory: new LisaChatMessageHistory(session),
                returnMessages: false,
                memoryKey: 'history',
                k: chatConfiguration.sessionConfiguration.chatHistoryBufferSize,
                aiPrefix: chatConfiguration.promptConfiguration.aiPrefix,
                humanPrefix: chatConfiguration.promptConfiguration.humanPrefix,
            }),
        );
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [userPrompt]);

    useEffect(() => {
        if (selectedModel && auth.isAuthenticated) {
            memory.loadMemoryVariables({}).then(async (formattedHistory) => {
                const promptValues = {
                    input: userPrompt,
                    history: formattedHistory.history,
                    aiPrefix: chatConfiguration.promptConfiguration.aiPrefix,
                    humanPrefix: chatConfiguration.promptConfiguration.humanPrefix
                };
                // If context is included in template then add value here
                if (chatConfiguration.promptConfiguration.promptTemplate.indexOf('{context}') > -1) {
                    if (useRag) {
                        promptValues['context'] = ragContext;
                    } else {
                        promptValues['context'] = fileContext;
                    }
                }
                const prompt = await PromptTemplate.fromTemplate(chatConfiguration.promptConfiguration.promptTemplate).format(promptValues);
                const metadata: LisaChatMessageMetadata = {
                    modelName: selectedModel.modelId,
                    modelKwargs: {
                        max_tokens: chatConfiguration.sessionConfiguration.max_tokens,
                        modelKwargs: chatConfiguration.sessionConfiguration.modelArgs,
                    },
                    userId: auth.user.profile.sub,
                    messages: prompt,
                };
                setMetadata(metadata);
            });
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [selectedModel, chatConfiguration.sessionConfiguration.modelArgs, auth, userPrompt]);

    useEffect(() => {
        if (bottomRef) {
            bottomRef?.current.scrollIntoView({ behavior: 'smooth' });
        }
    }, [session]);

    const createOpenAiClient = (streaming: boolean) => {
        return new ChatOpenAI({
            modelName: selectedModel?.modelId,
            openAIApiKey: auth.user?.id_token,
            configuration: {
                baseURL: `${RESTAPI_URI}/${RESTAPI_VERSION}/serve`,
            },
            streaming,
            maxTokens: chatConfiguration.sessionConfiguration?.max_tokens,
            modelKwargs: chatConfiguration.sessionConfiguration?.modelArgs,
        });
    };

    const contextualizeQSystemPrompt = `Given a chat history and the latest user question
    which might reference context in the chat history, formulate a standalone question
    which can be understood without the chat history. Do NOT answer the question,
    just reformulate it if needed and otherwise return it as is.`;

    const contextualizeQPrompt = ChatPromptTemplate.fromMessages([
        ['user', contextualizeQSystemPrompt],
        ['assistant', 'Okay!'],
        new MessagesPlaceholder('chatHistory'),
        ['human', '{input}'],
    ]);

    const handleSendGenerateRequest = useCallback(async () => {
        const userMessage = new LisaChatMessage({
            type: 'human',
            content: userPrompt,
            metadata: {},
        });
        setSession((prev) => ({
            ...prev,
            history: prev.history.concat(userMessage),
        }));

        setIsRunning(true);
        const inputs = {
            input: userPrompt,
            aiPrefix: chatConfiguration.promptConfiguration.aiPrefix,
            humanPrefix: chatConfiguration.promptConfiguration.humanPrefix
        };

        const llm = createOpenAiClient(chatConfiguration.sessionConfiguration.streaming);
        const useContext = fileContext || useRag;
        const inputVariables = ['history', 'input', 'aiPrefix', 'humanPrefix'];

        if (useContext) {
            inputVariables.push('context');
        }
        const questionPrompt = new PromptTemplate({
            template: chatConfiguration.promptConfiguration.promptTemplate,
            inputVariables: inputVariables,
        });

        const contextualizeQChain = contextualizeQPrompt.pipe(createOpenAiClient(false)).pipe(new StringOutputParser());

        const chainSteps = [
            {
                input: (previousOutput) => previousOutput.input,
                context: (previousOutput) => previousOutput.context,
                history: (previousOutput) => previousOutput.memory?.history || '',
                aiPrefix:(previousOutput) => previousOutput.aiPrefix,
                humanPrefix:(previousOutput) => previousOutput.humanPrefix,
            },
            questionPrompt,
            llm,
            new StringOutputParser(),
        ];

        if (useRag) {
            chainSteps.unshift({
                input: (input: { input: string; chatHistory?: LisaChatMessage[] }) => input.input,
                chatHistory: () => memory.loadMemoryVariables({}),
                context: async (input: { input: string; chatHistory?: LisaChatMessage[] }) => {
                    let question = input.input;
                    if (input.chatHistory?.length > 0) {
                        question = await contextualizeQChain.invoke(input);
                    }

                    const relevantDocs = await getRelevantDocuments({
                        query: question,
                        repositoryId: ragConfig.repositoryId,
                        repositoryType: ragConfig.repositoryType,
                        modelName: ragConfig.embeddingModel.modelId,
                        topK: chatConfiguration.sessionConfiguration.ragTopK ?? 3,
                    });
                    const serialized = `${fileContext}\n${formatDocumentsAsString(relevantDocs.data?.docs)}`;
                    setRagContext(serialized);
                    setSession((prev) => {
                        const lastMessage = prev.history[prev.history.length - 1];
                        const newMessage = new LisaChatMessage({
                            ...lastMessage,
                            metadata: {
                                ...lastMessage.metadata,
                                ragContext: formatDocumentsAsString(relevantDocs.data?.docs, true),
                            },
                        });
                        return {
                            ...prev,
                            history: prev.history.slice(0, -1).concat(newMessage),
                        };
                    });
                    return serialized;
                },
            });
        } else {
            chainSteps.unshift({
                input: (initialInput) => initialInput.input,
                memory: () => memory.loadMemoryVariables({}),
                context: () => (useContext ? fileContext : ''),
                humanPrefix: (initialInput) => initialInput.humanPrefix,
                aiPrefix: (initialInput) => initialInput.aiPrefix,
            });
        }
        const chain = RunnableSequence.from(chainSteps);
        if (chatConfiguration.sessionConfiguration.streaming) {
            setIsStreaming(true);
            setSession((prev) => ({
                ...prev,
                history: prev.history.concat(
                    new LisaChatMessage({
                        type: 'ai',
                        content: '',
                        metadata: metadata,
                    }),
                ),
            }));
            try {
                const result = await chain.stream({
                    input: userPrompt,
                    chatHistory: session.history,
                    aiPrefix: chatConfiguration.promptConfiguration.aiPrefix,
                    humanPrefix: chatConfiguration.promptConfiguration.humanPrefix
                });
                const resp: string[] = [];
                for await (const chunk of result) {
                    setSession((prev) => {
                        const lastMessage = prev.history[prev.history.length - 1];
                        const newMessage = new LisaChatMessage({
                            ...lastMessage,
                            content: lastMessage.content + chunk,

                        });
                        return {
                            ...prev,
                            history: prev.history.slice(0, -1).concat(newMessage),
                        };
                    });
                    resp.push(chunk);
                }

                memory.saveContext({input: inputs.input}, {
                    output: resp.join(''),
                });
            } catch (exception) {
                notificationService.generateNotification('An error occurred while processing your request.', 'error');
            }

            setIsStreaming(false);
        } else {
            try {
                const result = await chain.invoke(inputs);
                await memory.saveContext({input: inputs.input}, {
                    output: result,
                });
                setSession((prev) => ({
                    ...prev,
                    history: prev.history.concat(
                        new LisaChatMessage({
                            type: 'ai',
                            content: result,
                            metadata: useRag ? { ...metadata, ...prev.history[prev.history.length - 1].metadata } : metadata,
                        }),
                    ),
                }));
            } catch (exception) {
                notificationService.generateNotification('An error occurred while processing your request.', 'error');
            }
        }

        setIsRunning(false);
        setUserPrompt('');
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [userPrompt, metadata, chatConfiguration.sessionConfiguration.streaming]);

    return (
        <>
            <PromptTemplateEditor
                chatConfiguration={chatConfiguration}
                setChatConfiguration={setChatConfiguration}
                setVisible={setPromptTemplateEditorVisible}
                visible={promptTemplateEditorVisible}
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
            />
            <div className='overflow-y-auto p-2 mb-52'>
                <SpaceBetween direction='vertical' size='l'>
                    {session.history.map((message, idx) => (
                        <Message key={idx} message={message} showMetadata={chatConfiguration.sessionConfiguration.showMetadata} isRunning={false} isStreaming={isStreaming && idx === session.history.length - 1}/>
                    ))}
                    {isRunning && !isStreaming && <Message isRunning={isRunning} />}
                    <div ref={bottomRef} />
                </SpaceBetween>
            </div>
            <div className='fixed bottom-8' style={{width: 'calc(100% - 650px)'}}>
                <form onSubmit={(e) => e.preventDefault()}>
                    <Form variant='embedded'>
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
                                    disabled={!selectedModel}
                                    onChange={({ detail }) => setUserPrompt(detail.value)}
                                    onAction={userPrompt.length > 0 && handleSendGenerateRequest}
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
                                                }}
                                                items={[
                                                    {
                                                        type: 'icon-button',
                                                        id: 'settings',
                                                        iconName: 'settings',
                                                        text: 'Session configuration'
                                                    },
                                                    ...(config && config.configuration.enabledComponents.uploadRagDocs && window.env.RAG_ENABLED ?
                                                        [{
                                                            type: 'icon-button',
                                                            id: 'upload-to-rag',
                                                            iconName: 'upload',
                                                            text: 'Upload to RAG'
                                                        }] : []),
                                                    ...(config && config.configuration.enabledComponents.uploadContextDocs ?
                                                        [{
                                                            type: 'icon-button',
                                                            id: 'add-file-to-context',
                                                            iconName: 'insert-row',
                                                            text: 'Add file to context'
                                                        }] : []),
                                                    {
                                                        type: 'icon-button',
                                                        id: 'summarize-document',
                                                        iconName: 'transcript',
                                                        text: 'Summarize Document'
                                                    },
                                                    ...(config && config.configuration.enabledComponents.editPromptTemplate ?
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
                                                        }] : [])
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
        </>
    );
}

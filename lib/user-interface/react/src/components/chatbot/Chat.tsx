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

import { useCallback, useContext, useEffect, useRef, useState } from 'react';
import { useAuth } from 'react-oidc-context';
import Form from '@cloudscape-design/components/form';
import Box from '@cloudscape-design/components/box';
import SpaceBetween from '@cloudscape-design/components/space-between';
import {
    Autosuggest,
    ButtonGroup,
    Grid,
    PromptInput,
    TextContent,
} from '@cloudscape-design/components';
import StatusIndicator from '@cloudscape-design/components/status-indicator';

import Message from './components/Message';
import {
    LisaAttachImageResponse,
    LisaChatMessage,
    LisaChatSession,
    MessageTypes
} from '../types';
import RagControls from './components/RagOptions';
import { ContextUploadModal, RagUploadModal } from './components/FileUploadModals';
import { useGetAllModelsQuery } from '@/shared/reducers/model-management.reducer';
import { ModelStatus, ModelType } from '@/shared/model/model-management.model';
import {
    useAttachImageToSessionMutation,
    useGetSessionHealthQuery,
    useLazyGetSessionByIdQuery,
    useUpdateSessionMutation,
} from '@/shared/reducers/session.reducer';
import { useAppDispatch } from '@/config/store';
import { useNotificationService } from '@/shared/util/hooks';
import SessionConfiguration from './components/SessionConfiguration';
import { GenerateLLMRequestParams } from '@/shared/model/chat.configurations.model';
import { useLazyGetRelevantDocumentsQuery } from '@/shared/reducers/rag.reducer';
import { IConfiguration } from '@/shared/model/configuration.model';
import { DocumentSummarizationModal } from './components/DocumentSummarizationModal';
import { useNavigate } from 'react-router-dom';
import { PromptTemplateModal } from '../prompt-templates-library/PromptTemplateModal';
import ConfigurationContext from '@/shared/configuration.provider';
import FormField from '@cloudscape-design/components/form-field';
import { useMultipleMcp } from './hooks/mcp.hooks';
import { useChatGeneration } from './hooks/chat.hooks';
import { useSession } from './hooks/useSession.hooks';
import { useModels } from './hooks/useModels.hooks';
import { useMemory } from './hooks/useMemory.hooks';
import { useModals } from './hooks/useModals.hooks';
import { useToolChain } from './hooks/useToolChain.hooks';
import { WelcomeScreen } from './components/WelcomeScreen';
import { buildMessageContent, buildMessageMetadata } from './utils/messageBuilder.utils';
import { getButtonItems, useButtonActions } from './config/buttonConfig';
import { useListMcpServersQuery } from '@/shared/reducers/mcp-server.reducer';
import { setConfirmationModal } from '@/shared/reducers/modal.reducer';
import ConfirmationModal from '@/shared/modal/confirmation-modal';
import { darkStyles, JsonView } from 'react-json-view-lite';

export default function Chat({ sessionId }) {
    const dispatch = useAppDispatch();
    const navigate = useNavigate();
    const config: IConfiguration = useContext(ConfigurationContext);
    const notificationService = useNotificationService(dispatch);
    const modelSelectRef = useRef<HTMLInputElement>(null);
    const bottomRef = useRef(null);
    const auth = useAuth();

    // API hooks
    const [getRelevantDocuments] = useLazyGetRelevantDocumentsQuery();
    const { data: sessionHealth } = useGetSessionHealthQuery(undefined, { refetchOnMountOrArgChange: true });
    const [getSessionById] = useLazyGetSessionByIdQuery();
    const [updateSession] = useUpdateSessionMutation();
    const [attachImageToSession] = useAttachImageToSessionMutation();
    const { data: allModels, isFetching: isFetchingModels } = useGetAllModelsQuery(undefined, {
        refetchOnMountOrArgChange: 5,
        selectFromResult: (state) => ({
            isFetching: state.isFetching,
            data: (state.data || []).filter((model) => (model.modelType === ModelType.textgen || model.modelType === ModelType.imagegen) && model.status === ModelStatus.InService),
        })
    });

    // State management
    const [userPrompt, setUserPrompt] = useState('');
    const [fileContext, setFileContext] = useState('');
    const [dirtySession, setDirtySession] = useState(false);
    const [isConnected, setIsConnected] = useState(false);
    const [useRag, setUseRag] = useState(false);
    const [openAiTools, setOpenAiTools] = useState(undefined);

    // Ref to track if we're processing tool calls to prevent infinite loops
    const isProcessingToolCalls = useRef(false);
    const lastProcessedMessageIndex = useRef(-1);
    const startToolChainRef = useRef<(session: LisaChatSession) => Promise<void>>();

    // Tool call loop prevention
    const consecutiveToolCallCount = useRef(0);
    const TOOL_CALL_LIMIT = 20;
    const pendingToolChainExecution = useRef<(() => Promise<void>) | null>(null);

    const { data: { Items: mcpServers } = { Items: [] } } = useListMcpServersQuery(undefined, { refetchOnMountOrArgChange: true });
    // Use the custom hook to manage multiple MCP connections
    const { tools: mcpTools, callTool, McpConnections } = useMultipleMcp(config?.configuration?.enabledComponents?.mcpConnections ? mcpServers : undefined);

    // Custom hooks
    const {
        session,
        setSession,
        internalSessionId,
        setInternalSessionId,
        loadingSession,
        chatConfiguration,
        setChatConfiguration,
        selectedModel,
        setSelectedModel,
        ragConfig,
        setRagConfig
    } = useSession(sessionId, getSessionById);

    const { modelsOptions, handleModelChange } = useModels(
        allModels,
        chatConfiguration,
        setChatConfiguration
    );

    const { memory, setMemory, metadata } = useMemory(
        session,
        chatConfiguration,
        selectedModel,
        userPrompt,
        fileContext,
        notificationService
    );

    const {
        modals,
        openModal,
        closeModal,
        promptTemplateKey,
        filterPromptTemplateType,
        setFilterPromptTemplateType,
        refreshPromptTemplate
    } = useModals();

    const { handleButtonClick } = useButtonActions({
        openModal,
        refreshPromptTemplate,
        setFilterPromptTemplateType,
    });

    // Derived states
    const isImageGenerationMode = selectedModel?.modelType === ModelType.imagegen;

    // Format MCP tools for OpenAI when they change
    useEffect(() => {
        if (mcpTools.length > 0) {
            const formattedTools = mcpTools.map((tool) => ({
                type: 'function',
                function: {
                    ...tool,
                    parameters: {
                        ...tool.inputSchema,
                        type: 'object'
                    }
                }
            }));
            setOpenAiTools(formattedTools);
        }
    }, [mcpTools]);

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

    const { isRunning, setIsRunning, isStreaming, generateResponse, stopGeneration } = useChatGeneration({
        chatConfiguration,
        selectedModel,
        isImageGenerationMode,
        session,
        setSession,
        metadata,
        memory,
        openAiTools: config?.configuration?.enabledComponents?.mcpConnections ? openAiTools : undefined,
        auth,
        notificationService
    });

    // Tool chain hook for handling chained tool calls
    const {
        startToolChain,
        stopToolChain,
        callingToolName,
        toolApprovalModal,
        handleToolApproval,
        handleToolRejection
    } = useToolChain({
        callTool,
        generateResponse,
        session,
        setSession,
        notificationService,
    });

    // Store the startToolChain function in a ref to avoid useEffect dependency issues
    startToolChainRef.current = startToolChain;

    // Handle stop functionality
    const handleStop = useCallback(() => {
        stopToolChain();
        stopGeneration();
        setIsRunning(false);
        notificationService.generateNotification('Stopping processing...', 'info');
    }, [stopToolChain, stopGeneration, setIsRunning, notificationService]);

    // Determine if we should show stop button
    const shouldShowStopButton = isRunning || callingToolName;

    useEffect(() => {
        if (sessionHealth) {
            setIsConnected(true);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [sessionHealth]);

    // Handle tool calls with chaining support
    useEffect(() => {
        const handleToolCalls = async () => {
            if (session.history.length && !isProcessingToolCalls.current) {
                const currentMessageIndex = session.history.length - 1;

                // Update session if there are changes
                if (dirtySession) {
                    if (session.history.at(-1)?.type === MessageTypes.AI && !auth.isLoading) {
                        setDirtySession(false);
                        const message = session.history.at(-1);
                        if (session.history.at(-1).metadata.imageGeneration && Array.isArray(session.history.at(-1).content)) {
                            // Session was updated and response contained images that need to be attached to the session
                            await Promise.all(
                                (Array.isArray(message.content) ? message.content : []).map(async (content) => {
                                    if (content.type === 'image_url') {
                                        const resp = await attachImageToSession({
                                            sessionId: session.sessionId,
                                            message: content
                                        });
                                        if ('data' in resp) {
                                            const image: LisaAttachImageResponse = resp.data;
                                            content.image_url.url = image.body.image_url.url;
                                            content.image_url.s3_key = image.body.image_url.s3_key;
                                        }
                                    }
                                })
                            );
                        }
                        const updatedHistory = [...session.history.slice(0, -1), message];

                        updateSession({
                            ...session,
                            history: updatedHistory,
                            configuration: { ...chatConfiguration, selectedModel: selectedModel, ragConfig: ragConfig }
                        });
                    }
                }

                // Check if the last message has tool calls that need to be processed
                // and we haven't already processed this message
                const lastMessage = session.history.at(-1);

                if (lastMessage?.type === MessageTypes.AI &&
                    lastMessage.toolCalls &&
                    lastMessage.toolCalls.length > 0 &&
                    currentMessageIndex > lastProcessedMessageIndex.current) {

                    // Check for potential infinite loop before processing
                    consecutiveToolCallCount.current += 1;

                    if (consecutiveToolCallCount.current > TOOL_CALL_LIMIT) {
                        pendingToolChainExecution.current = async () => {
                            isProcessingToolCalls.current = true;
                            setDirtySession(true);
                            try {
                                if (startToolChainRef.current) {
                                    await startToolChainRef.current(session);
                                }
                            } finally {
                                isProcessingToolCalls.current = false;
                            }
                        };
                        dispatch(setConfirmationModal({
                            action: 'Continue',
                            resourceName: 'Tool Executions',
                            onConfirm: () => handleContinueToolCalls(),
                            onDismiss: () => handleStopToolCalls(),
                            description: `The maximum amount of (${TOOL_CALL_LIMIT}) concurrent tool executions has been reached. Would you like to continue?`,
                            ignoreResponses: true,
                        }));
                        return;
                    }

                    isProcessingToolCalls.current = true;
                    setDirtySession(true);
                    try {
                        // Start the tool chain - this will handle multiple rounds of tool calls automatically
                        if (startToolChainRef.current) {
                            await startToolChainRef.current(session);
                        }
                        // Update the last processed index after successful processing
                        lastProcessedMessageIndex.current = currentMessageIndex;
                    } finally {
                        isProcessingToolCalls.current = false;
                    }
                }
            }
        };

        handleToolCalls();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isRunning, session.history.length, dirtySession]);

    // Connection health check
    useEffect(() => {
        if (sessionHealth) {
            setIsConnected(true);
        }
    }, [sessionHealth]);

    useEffect(() => {
        if (bottomRef) {
            bottomRef?.current.scrollIntoView({ behavior: 'smooth' });
        }
    }, [session]);

    // Reset tool call counter when session changes
    useEffect(() => {
        consecutiveToolCallCount.current = 0;
    }, [sessionId]);

    // Handle loop prevention modal actions
    const handleContinueToolCalls = useCallback(async () => {
        consecutiveToolCallCount.current = 0; // Reset counter

        if (pendingToolChainExecution.current) {
            await pendingToolChainExecution.current();
            pendingToolChainExecution.current = null;
        }
    }, []);

    const handleStopToolCalls = useCallback(() => {
        consecutiveToolCallCount.current = 0; // Reset counter
        pendingToolChainExecution.current = null; // Clear pending execution
        notificationService.generateNotification('Tool call chain stopped by user', 'info');
    }, [notificationService]);

    const handleSendGenerateRequest = useCallback(async () => {
        if (!userPrompt.trim()) return;
        setIsRunning(true);

        // Reset tool call counter when human provides input
        consecutiveToolCallCount.current = 0;

        setSession((prev) => ({
            ...prev,
            history: prev.history.concat(new LisaChatMessage({
                type: 'human',
                content: userPrompt,
                metadata: isImageGenerationMode ? { imageGeneration: true } : {},
            }))
        }));

        const messages = [];

        if (session.history.length === 0 && !isImageGenerationMode) {
            messages.push(new LisaChatMessage({
                type: 'system',
                content: chatConfiguration.promptConfiguration.promptTemplate,
                metadata: {},
            }));
        }

        // Use extracted message builder utilities
        const messageContent = await buildMessageContent({
            isImageGenerationMode,
            fileContext,
            useRag,
            userPrompt,
            fetchRelevantDocuments,
        });

        const messageMetadata = await buildMessageMetadata({
            isImageGenerationMode,
            useRag,
            userPrompt,
            chatConfiguration,
            fetchRelevantDocuments,
        });

        messages.push(new LisaChatMessage({
            type: 'human',
            content: messageContent,
            metadata: messageMetadata,
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
    }, [userPrompt, useRag, fileContext, chatConfiguration, generateResponse, isImageGenerationMode, fetchRelevantDocuments, notificationService]);

    return (
        <div className='h-[80vh]'>
            {/* MCP Connections - invisible components that manage the connections */}
            {McpConnections}
            <DocumentSummarizationModal
                showDocumentSummarizationModal={modals.documentSummarization}
                setShowDocumentSummarizationModal={(show) => show ? openModal('documentSummarization') : closeModal('documentSummarization')}
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
                visible={modals.sessionConfiguration}
                setVisible={(show) => show ? openModal('sessionConfiguration') : closeModal('sessionConfiguration')}
                systemConfig={config}
            />
            <RagUploadModal
                ragConfig={ragConfig}
                showRagUploadModal={modals.ragUpload}
                setShowRagUploadModal={(show) => show ? openModal('ragUpload') : closeModal('ragUpload')}
            />
            <ContextUploadModal
                showContextUploadModal={modals.contextUpload}
                setShowContextUploadModal={(show) => show ? openModal('contextUpload') : closeModal('contextUpload')}
                fileContext={fileContext}
                setFileContext={setFileContext}
                selectedModel={selectedModel}
            />
            <PromptTemplateModal
                session={session}
                showModal={modals.promptTemplate}
                setShowModal={(show) => show ? openModal('promptTemplate') : closeModal('promptTemplate')}
                setUserPrompt={setUserPrompt}
                chatConfiguration={chatConfiguration}
                setChatConfiguration={setChatConfiguration}
                key={promptTemplateKey}
                config={config}
                type={filterPromptTemplateType}
            />
            {/* Tool Approval Modal */}
            {toolApprovalModal && (
                <ConfirmationModal
                    action='Execute'
                    resourceName={`Tool: ${toolApprovalModal.tool.name}`}
                    onConfirm={handleToolApproval}
                    onDismiss={handleToolRejection}
                    description={
                        <div>
                            <p>The AI is about to execute the following tool:</p>
                            <p><strong>Tool Name:</strong> {toolApprovalModal.tool.name}</p>
                            <p><strong>Arguments:</strong></p>
                            <JsonView data={toolApprovalModal.tool.args} style={darkStyles} />
                            <p>Do you want to allow this tool execution?</p>
                        </div>
                    }
                />
            )}
            <div className='overflow-y-auto h-[calc(100vh-25rem)] bottom-8'>
                <SpaceBetween direction='vertical' size='l'>
                    {session.history.map((message, idx) => (
                        <Message
                            key={idx}
                            message={message}
                            showMetadata={chatConfiguration.sessionConfiguration.showMetadata}
                            isRunning={false}
                            callingToolName={undefined}
                            isStreaming={isStreaming && idx === session.history.length - 1}
                            markdownDisplay={chatConfiguration.sessionConfiguration.markdownDisplay}
                            setChatConfiguration={setChatConfiguration}
                            handleSendGenerateRequest={handleSendGenerateRequest}
                            chatConfiguration={chatConfiguration}
                            setUserPrompt={setUserPrompt}
                        />
                    ))}
                    {(isRunning || callingToolName) && !isStreaming && <Message
                        isRunning={isRunning}
                        callingToolName={callingToolName}
                        markdownDisplay={chatConfiguration.sessionConfiguration.markdownDisplay}
                        message={new LisaChatMessage({ type: 'ai', content: '' })}
                        setChatConfiguration={setChatConfiguration}
                        handleSendGenerateRequest={handleSendGenerateRequest}
                        chatConfiguration={chatConfiguration}
                        setUserPrompt={setUserPrompt}
                    />}
                    {session.history.length === 0 && sessionId === undefined && (
                        <WelcomeScreen
                            navigate={navigate}
                            modelSelectRef={modelSelectRef}
                            config={config}
                            refreshPromptTemplate={refreshPromptTemplate}
                            setFilterPromptTemplateType={setFilterPromptTemplateType}
                            openModal={openModal}
                        />
                    )}
                    <div ref={bottomRef} />
                </SpaceBetween>
            </div>
            <div className='sticky bottom-8 mt-2'>
                <form onSubmit={(e) => e.preventDefault()}>
                    <Form>
                        <SpaceBetween size='m' direction='vertical'>
                            <Grid
                                gridDefinition={[
                                    { colspan: { default: 4 } },
                                    { colspan: { default: 8 } },
                                ]}
                            >
                                <FormField
                                    label={isImageGenerationMode ? <StatusIndicator type='info'>Image Generation Mode</StatusIndicator> : undefined}
                                >
                                    <Autosuggest
                                        disabled={isRunning || session.history.length > 0}
                                        statusType={isFetchingModels ? 'loading' : 'finished'}
                                        loadingText='Loading models (might take few seconds)...'
                                        placeholder='Select a model'
                                        empty={<div className='text-gray-500'>No models available.</div>}
                                        filteringType='auto'
                                        value={selectedModel?.modelId ?? ''}
                                        enteredTextLabel={(text) => `Use: "${text}"`}
                                        onChange={({ detail: { value } }) => handleModelChange(value, selectedModel, setSelectedModel)}
                                        options={modelsOptions}
                                        ref={modelSelectRef}
                                    />
                                </FormField>
                                {window.env.RAG_ENABLED && !isImageGenerationMode && (
                                    <RagControls
                                        isRunning={isRunning}
                                        setUseRag={setUseRag}
                                        setRagConfig={setRagConfig}
                                        ragConfig={ragConfig}
                                    />
                                )}
                            </Grid>
                            <PromptInput
                                value={userPrompt}
                                actionButtonAriaLabel={shouldShowStopButton ? 'Stop generation' : 'Send message'}
                                actionButtonIconName={shouldShowStopButton ? 'status-stopped' : 'send'}
                                maxRows={4}
                                minRows={2}
                                spellcheck={true}
                                placeholder={
                                    !selectedModel ? 'You must select a model before sending a message' :
                                        isImageGenerationMode ? 'Describe the image you want to generate...' :
                                            'Send a message'
                                }
                                disabled={!selectedModel || loadingSession}
                                onChange={({ detail }) => setUserPrompt(detail.value)}
                                onAction={shouldShowStopButton ? handleStop : (userPrompt.length > 0 && !isRunning && !callingToolName && !loadingSession ? handleSendGenerateRequest : undefined)}
                                secondaryActions={
                                    <Box padding={{ left: 'xxs', top: 'xs' }}>
                                        <ButtonGroup
                                            ariaLabel='Chat actions'
                                            onItemClick={handleButtonClick}
                                            items={getButtonItems(config, useRag, isImageGenerationMode)}
                                            variant='icon'
                                        />
                                    </Box>
                                }
                            />
                            <SpaceBetween direction='vertical' size='xs'>
                                <Grid gridDefinition={[{ colspan: 6 }, { colspan: 6 }]}>
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
                    </Form>
                </form>
            </div>
        </div>
    );
}

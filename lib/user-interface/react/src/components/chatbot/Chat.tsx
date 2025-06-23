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
import {
    LisaAttachImageResponse,
    LisaChatMessage,
    LisaChatMessageMetadata,
    LisaChatSession,
    MessageTypes
} from '../types';
import { formatDocumentsAsString, formatDocumentTitlesAsString, RESTAPI_URI, RESTAPI_VERSION } from '../utils';
import { LisaChatMessageHistory } from '../adapters/lisa-chat-history';
import RagControls, { RagConfig } from './RagOptions';
import { ContextUploadModal, RagUploadModal } from './FileUploadModals';
import { ChatOpenAI } from '@langchain/openai';
import { useGetAllModelsQuery } from '../../shared/reducers/model-management.reducer';
import { IModel, ModelStatus, ModelType } from '../../shared/model/model-management.model';
import {
    useAttachImageToSessionMutation,
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
import { faFileLines, faMessage, faPenToSquare, faComment } from '@fortawesome/free-regular-svg-icons';
import { PromptTemplateModal } from '../prompt-templates-library/PromptTemplateModal';
import ConfigurationContext from '../../shared/configuration.provider';
import FormField from '@cloudscape-design/components/form-field';
import { PromptTemplateType } from '@/shared/reducers/prompt-templates.reducer';
import { useMcp } from 'use-mcp/react';

// Individual MCP Connection Component
const McpConnection = ({ server, onToolsChange, onConnectionChange }: { 
    server: { url: string; clientName: string }, 
    onToolsChange: (tools: any[], clientName: string) => void,
    onConnectionChange: (connection: any, clientName: string) => void
}) => {
    const connection = useMcp({
        url: server.url,
        clientName: server.clientName,
        autoReconnect: true,
        debug: true
    });

    // Use refs to track previous values and avoid unnecessary updates
    const prevToolsRef = useRef<string>('');
    const prevCallToolRef = useRef<any>(null);

    // Memoize tools to avoid unnecessary re-renders
    const toolsString = useMemo(() => JSON.stringify(connection.tools || []), [connection.tools]);

    useEffect(() => {
        if (prevToolsRef.current !== toolsString) {
            prevToolsRef.current = toolsString;
            onToolsChange(connection.tools || [], server.clientName);
        }
    }, [toolsString, server.clientName, onToolsChange, connection.tools]);

    useEffect(() => {
        if (connection.callTool && prevCallToolRef.current !== connection.callTool) {
            prevCallToolRef.current = connection.callTool;
            onConnectionChange(connection, server.clientName);
        }
    }, [connection.callTool, server.clientName, onConnectionChange, connection]);

    return null; // This component only manages the connection
};

// Custom hook to manage multiple MCP connections dynamically
const useMultipleMcp = (servers: Array<{ url: string; clientName: string }>) => {
    const [allTools, setAllTools] = useState([]);
    const [serverToolsMap, setServerToolsMap] = useState<Map<string, any[]>>(new Map());
    const [connectionsMap, setConnectionsMap] = useState<Map<string, any>>(new Map());
    const [toolToServerMap, setToolToServerMap] = useState<Map<string, string>>(new Map());

    const handleToolsChange = useCallback((tools: any[], clientName: string) => {
        setServerToolsMap((prev) => {
            const newMap = new Map(prev);
            newMap.set(clientName, tools);
            return newMap;
        });

        // Update tool-to-server mapping
        setToolToServerMap((prev) => {
            const newMap = new Map(prev);
            // Remove old mappings for this server
            prev.forEach((serverName, toolName) => {
                if (serverName === clientName) {
                    newMap.delete(toolName);
                }
            });
            // Add new mappings
            tools.forEach((tool) => {
                if (tool.name) {
                    newMap.set(tool.name, clientName);
                }
            });
            return newMap;
        });
    }, []);

    const handleConnectionChange = useCallback((connection: any, clientName: string) => {
        setConnectionsMap((prev) => {
            const newMap = new Map(prev);
            newMap.set(clientName, connection);
            return newMap;
        });
    }, []);

    useEffect(() => {
        // Combine all tools from all servers
        const combinedTools = Array.from(serverToolsMap.values()).flat();
        setAllTools(combinedTools);
    }, [serverToolsMap]);

    const callTool = useCallback(async (toolName: string, args: any) => {
        const serverName = toolToServerMap.get(toolName);
        if (!serverName) {
            throw new Error(`Tool "${toolName}" not found in any MCP server`);
        }

        const connection = connectionsMap.get(serverName);
        if (!connection || !connection.callTool) {
            throw new Error(`Connection for server "${serverName}" not available or doesn't support tool calling`);
        }

        try {
            console.log(`Calling tool "${toolName}" on server "${serverName}" with args:`, args);
            const result = await connection.callTool(toolName, args);
            console.log(`Tool "${toolName}" result:`, result);
            return result;
        } catch (error) {
            console.error(`Error calling tool "${toolName}" on server "${serverName}":`, error);
            throw error;
        }
    }, [toolToServerMap, connectionsMap]);

    return { 
        tools: allTools, 
        callTool,
        McpConnections: servers.map((server) => (
            <McpConnection 
                key={server.clientName} 
                server={server} 
                onToolsChange={handleToolsChange}
                onConnectionChange={handleConnectionChange}
            />
        ))
    };
};

// Note: callTool is now provided by useMultipleMcp hook

export default function Chat ({ sessionId }) {
    const dispatch = useAppDispatch();
    const navigate = useNavigate();
    const config: IConfiguration = useContext(ConfigurationContext);
    const notificationService = useNotificationService(dispatch);
    const modelSelectRef = useRef<HTMLInputElement>(null);

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
    const [chatConfiguration, setChatConfiguration] = useState<IChatConfiguration>(baseConfig);
    const [openAiTools, setOpenAiTools] = useState(undefined);

    // MCP server configuration - loaded from API
    const [mcpServers, setMcpServers] = useState<Array<{ url: string; clientName: string }>>([]);

    // Load MCP servers from API on component mount
    useEffect(() => {
        const fetchMcpServers = async () => {
            try {
                // TODO: Replace with actual API endpoint
                // const response = await fetch('/api/mcp-servers');
                // const servers = await response.json();
                // setMcpServers(servers);
                
                // For now, using mock data
                setMcpServers([
                    {
                        url: 'SERVER1',
                        clientName: 'LISA-MCP-Gmail'
                    },
                    {
                        url: 'SERVER2',
                        clientName: 'LISA-MCP-Slack'
                    }
                ]);
            } catch (error) {
                console.error('Failed to fetch MCP servers:', error);
                notificationService.generateNotification('Failed to load MCP servers', 'error');
            }
        };

        fetchMcpServers();
    }, [notificationService]);

    // Use the custom hook to manage multiple MCP connections
    const { tools: mcpTools, callTool, McpConnections } = useMultipleMcp(mcpServers);

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
    const [filterPromptTemplateType, setFilterPromptTemplateType] = useState(undefined);

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

    const isImageGenerationMode = selectedModel?.modelType === ModelType.imagegen;

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
                // Handle image generation mode specifically
                if (isImageGenerationMode) {
                    try {
                        // Create image generation request
                        const imageGenParams = {
                            prompt: params.input,
                            model: selectedModel.modelId,
                            n: chatConfiguration.sessionConfiguration.imageGenerationArgs.numberOfImages,
                            size: chatConfiguration.sessionConfiguration.imageGenerationArgs.size,
                            quality: chatConfiguration.sessionConfiguration.imageGenerationArgs.quality,
                            response_format: 'url',
                        };

                        // Make API call to generate images
                        const response = await fetch(`${RESTAPI_URI}/${RESTAPI_VERSION}/serve/images/generations`, {
                            method: 'POST',
                            headers: {
                                'Authorization': `Bearer ${auth.user?.id_token}`,
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify(imageGenParams),
                        });

                        const data = await response.json();

                        if (!response.ok) {
                            throw new Error(`Image generation failed: ${JSON.stringify(data.error.message)}`);
                        }

                        const imageContent = data.data.map((img) => ({
                            image_url: {
                                url: `data:image/png;base64,${img.b64_json}`
                            },
                            type: 'image_url'
                        }));

                        // Save the response to the chat history
                        setSession((prev) => ({
                            ...prev,
                            history: [...prev.history, new LisaChatMessage({
                                type: 'ai',
                                content: imageContent,
                                metadata: {
                                    ...metadata,
                                    imageGeneration: true,
                                    imageGenerationParams: imageGenParams
                                }
                            })],
                        }));

                        await memory.saveContext({ input: params.input }, { output: imageContent });
                    } catch (error) {
                        notificationService.generateNotification('Image generation failed', 'error', undefined, error.message ? <p>{error.message}</p> : undefined);
                        setIsRunning(false);
                    }
                } else {
                    // Existing text generation code
                    const llmClient = createOpenAiClient(chatConfiguration.sessionConfiguration.streaming);

                    // Convert chat history to messages format
                    let messages = session.history.concat(params.message).map((msg) => ({
                        role: msg.type === MessageTypes.HUMAN ? 'user' : msg.type === MessageTypes.AI ? 'assistant' : 'system',
                        content: Array.isArray(msg.content) ? msg.content : selectedModel.modelName.startsWith('sagemaker') ? msg.content : [{ type: 'text', text: msg.content }]
                    }));

                    const [systemMessage, ...remainingMessages] = messages;
                    messages = [systemMessage, ...remainingMessages.slice(-(chatConfiguration.sessionConfiguration.chatHistoryBufferSize * 2) - 1)];

                    if (chatConfiguration.sessionConfiguration.streaming) {
                        setIsStreaming(true);
                        setSession((prev) => ({
                            ...prev,
                            history: [...prev.history, new LisaChatMessage({ type: 'ai', content: '', metadata: { ...metadata, ...params.message[params.message.length - 1].metadata } })],
                        }));

                        try {
                            const stream = await llmClient.stream(messages, { tools: openAiTools });
                            const resp: string[] = [];
                            const toolCallsAccumulator: { [index: number]: any } = {};

                            for await (const chunk of stream) {
                                const content = chunk.content as string;

                                // Get tool calls from LangChain streaming chunks
                                let tool_calls: any[] = [];

                                // tool_call_chunks contain streaming argument fragments
                                if ((chunk as any).tool_call_chunks?.length > 0) {
                                    tool_calls = (chunk as any).tool_call_chunks;
                                }

                                // additional_kwargs.tool_calls contain initial tool call info (ID, name)
                                if ((chunk as any).additional_kwargs?.tool_calls?.length > 0) {
                                    const additionalTCs = (chunk as any).additional_kwargs.tool_calls.map((tc: any) => ({
                                        id: tc.id,
                                        index: tc.index || 0,
                                        function: tc.function,
                                        args: tc.function?.arguments || ''
                                    }));

                                    if (tool_calls.length === 0) {
                                        tool_calls = additionalTCs;
                                    } else {
                                        // Merge tool call info from additional_kwargs
                                        additionalTCs.forEach((addTC) => {
                                            const existingTC = tool_calls.find((tc) => tc.index === addTC.index);
                                            if (existingTC) {
                                                if (!existingTC.id && addTC.id) existingTC.id = addTC.id;
                                                if (!existingTC.function?.name && addTC.function?.name) {
                                                    existingTC.function = existingTC.function || {};
                                                    existingTC.function.name = addTC.function.name;
                                                }
                                            }
                                        });
                                    }
                                }

                                // Accumulate tool call data
                                tool_calls.forEach((toolCall: any) => {
                                    const index = toolCall.index ?? 0;

                                    // Initialize accumulator entry
                                    if (!toolCallsAccumulator[index]) {
                                        toolCallsAccumulator[index] = {
                                            id: toolCall.id || '',
                                            name: toolCall.function?.name || toolCall.name || '',
                                            args: '',
                                            type: 'tool_call'
                                        };
                                    }

                                    // Update properties if not already set
                                    if (toolCall.id && !toolCallsAccumulator[index].id) {
                                        toolCallsAccumulator[index].id = toolCall.id;
                                    }
                                    if (toolCall.function?.name && !toolCallsAccumulator[index].name) {
                                        toolCallsAccumulator[index].name = toolCall.function.name;
                                    }

                                    // Accumulate arguments
                                    let args = '';
                                    if (toolCall.args) {
                                        args = toolCall.args;
                                    } else if (toolCall.function?.arguments) {
                                        args = toolCall.function.arguments;
                                    }

                                    if (args && typeof args === 'string') {
                                        toolCallsAccumulator[index].args += args;
                                    }
                                });

                                // Update streaming display with current tool calls
                                const currentToolCalls = Object.values(toolCallsAccumulator).map((toolCall: any) => {
                                    let parsedArgs = {};
                                    try {
                                        if (toolCall.args) {
                                            parsedArgs = JSON.parse(toolCall.args);
                                        }
                                    } catch (e) {
                                        parsedArgs = {};
                                    }

                                    return {
                                        id: toolCall.id,
                                        name: toolCall.name,
                                        args: parsedArgs,
                                        type: toolCall.type
                                    };
                                }).filter((toolCall) => toolCall.name);

                                setSession((prev) => {
                                    const lastMessage = prev.history[prev.history.length - 1];
                                    return {
                                        ...prev,
                                        history: [...prev.history.slice(0, -1),
                                            new LisaChatMessage({
                                                ...lastMessage,
                                                content: lastMessage.content + content,
                                                toolCalls: currentToolCalls
                                            })
                                        ],
                                    };
                                });
                                resp.push(content);
                            }

                            // Finalize tool calls with complete JSON parsing
                            const finalToolCalls = Object.values(toolCallsAccumulator).map((toolCall: any) => {
                                let parsedArgs = {};
                                try {
                                    if (toolCall.args && typeof toolCall.args === 'string') {
                                        parsedArgs = JSON.parse(toolCall.args.trim());
                                    }
                                } catch (e) {
                                    parsedArgs = {};
                                }

                                return {
                                    id: toolCall.id,
                                    name: toolCall.name,
                                    args: parsedArgs,
                                    type: toolCall.type
                                };
                            }).filter((toolCall) => toolCall.name);

                            // Update with final parsed tool calls
                            if (finalToolCalls.length > 0) {
                                setSession((prev) => {
                                    const lastMessage = prev.history[prev.history.length - 1];
                                    return {
                                        ...prev,
                                        history: [...prev.history.slice(0, -1),
                                            new LisaChatMessage({
                                                ...lastMessage,
                                                toolCalls: finalToolCalls
                                            })
                                        ],
                                    };
                                });
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
                        const response = await llmClient.invoke(messages, { tools: openAiTools });
                        const content = response.content as string;
                        await memory.saveContext({ input: params.input }, { output: content });
                        setSession((prev) => ({
                            ...prev,
                            history: [...prev.history, new LisaChatMessage({ type: 'ai', content, metadata, toolCalls: [...(response.tool_calls ?? [])] })],
                        }));
                    }
                }
            } catch (error) {
                notificationService.generateNotification('An error occurred while processing your request.', 'error', undefined, error.error?.message ? <p>{JSON.stringify(error.error.message)}</p> : undefined);
                setIsRunning(false);
                throw error;
            } finally {
                setIsRunning(false);
            }
        };

        return { isRunning, setIsRunning, isStreaming, setIsStreaming, generateResponse };
    };

    const { isRunning, setIsRunning, isStreaming, setIsStreaming, generateResponse } = useChatGeneration();

    useEffect(() => {
        if (sessionHealth) {
            setIsConnected(true);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [sessionHealth]);

    const handleUpdateSession = async () => {
        if (session.history.at(-1).type === MessageTypes.AI && !auth.isLoading) {
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
    };

    const callMcpTool = async (tool: any) => {
        const result = await callTool(tool.name, { ...tool.args });
        console.log(`Tool "${tool.name}" executed successfully:`, result);
        return result;
    };

    useEffect(() => {
        const handleToolCalls = async () => {
            if (!isRunning && session.history.length && dirtySession) {
                handleUpdateSession();
                if (session.history.at(-1).type === MessageTypes.AI && session.history.at(-1).toolCalls) {
                    const toolCalls = session.history.at(-1).toolCalls;
                    const toolResults = [];
                    
                    // Execute tool calls sequentially to avoid overwhelming the servers
                    for (const tool of toolCalls) {
                        try {
                            const result = await callMcpTool(tool);
                            
                            // Format tool result for LLM
                            let toolResultContent = '';
                            if (Array.isArray(result)) {
                                // Handle array results (like the example)
                                toolResultContent = result.map((item) => {
                                    if (item.type === 'text') {
                                        return item.text;
                                    }
                                    return JSON.stringify(item, null, 2);
                                }).join('\n');
                            } else if (typeof result === 'object') {
                                toolResultContent = JSON.stringify(result, null, 2);
                            } else {
                                toolResultContent = String(result);
                            }
                            
                            toolResults.push({
                                toolCallId: tool.id,
                                toolName: tool.name,
                                content: toolResultContent
                            });
                        } catch (error) {
                            console.error(`Failed to execute tool "${tool.name}":`, error);
                            notificationService.generateNotification(
                                `Tool execution failed: ${tool.name}`, 
                                'error', 
                                undefined, 
                                <p>{error.message}</p>
                            );
                        }
                    }
                    
                    // If we have tool results, continue the conversation
                    if (toolResults.length > 0) {
                        const toolResultsContent = toolResults.map((tr) => `Tool "${tr.toolName}" result:\n${tr.content}`).join('\n\n');
                        
                        // Continue the conversation with tool results
                        setUserPrompt(`Based on these tool results:\n\n${toolResultsContent}\n\nPlease analyze and respond:`);
                        setTimeout(() => {
                            handleSendGenerateRequest();
                            setUserPrompt('');
                        }, 100);
                    }
                    
                    // If we have tool results, continue the conversation with the LLM
                    if (toolResults.length > 0) {
                        // Add individual tool result messages to session
                        const toolResultMessages = toolResults.map((tr) => new LisaChatMessage({
                            type: 'tool',
                            content: `Tool: ${tr.toolName}\nResult: ${tr.content}`,
                            metadata: {
                                toolCallId: tr.toolCallId,
                                toolName: tr.toolName,
                                isToolResult: true
                            } as any
                        }));

                        setSession((prev) => ({
                            ...prev,
                            history: [...prev.history, ...toolResultMessages]
                        }));

                        // Continue conversation with LLM using tool results
                        setIsRunning(true);
                        try {
                            const llmClient = createOpenAiClient(chatConfiguration.sessionConfiguration.streaming);

                            // Prepare messages for LLM including tool results with proper ID mapping
                            let messages = session.history.concat(toolResultMessages).map((msg) => {
                                if (msg.type === 'tool') {
                                    return {
                                        role: 'tool',
                                        content: msg.content,
                                        tool_call_id: (msg.metadata as any).toolCallId
                                    };
                                }
                                return {
                                    role: msg.type === MessageTypes.HUMAN ? 'user' : msg.type === MessageTypes.AI ? 'assistant' : 'system',
                                    content: Array.isArray(msg.content) ? msg.content : selectedModel?.modelName?.startsWith('sagemaker') ? msg.content : [{ type: 'text', text: msg.content }],
                                    ...(msg.toolCalls && { tool_calls: msg.toolCalls.map((tc) => ({
                                        id: tc.id,
                                        type: 'function',
                                        function: {
                                            name: tc.name,
                                            arguments: JSON.stringify(tc.args)
                                        }
                                    })) })
                                };
                            });

                            const [systemMessage, ...remainingMessages] = messages;
                            messages = [systemMessage, ...remainingMessages.slice(-(chatConfiguration.sessionConfiguration.chatHistoryBufferSize * 2) - 1)];

                            if (chatConfiguration.sessionConfiguration.streaming) {
                                setIsStreaming(true);
                                setSession((prev) => ({
                                    ...prev,
                                    history: [...prev.history, new LisaChatMessage({ type: 'ai', content: '', metadata: { ...metadata, continuingFromToolResults: true } })],
                                }));

                                try {
                                    const stream = await llmClient.stream(messages, { tools: openAiTools });
                                    const resp: string[] = [];
                                    const toolCallsAccumulator: { [index: number]: any } = {};

                                    for await (const chunk of stream) {
                                        const content = chunk.content as string;

                                        // Handle tool calls in streaming response (same logic as before)
                                        let tool_calls: any[] = [];

                                        if ((chunk as any).tool_call_chunks?.length > 0) {
                                            tool_calls = (chunk as any).tool_call_chunks;
                                        }

                                        if ((chunk as any).additional_kwargs?.tool_calls?.length > 0) {
                                            const additionalTCs = (chunk as any).additional_kwargs.tool_calls.map((tc: any) => ({
                                                id: tc.id,
                                                index: tc.index || 0,
                                                function: tc.function,
                                                args: tc.function?.arguments || ''
                                            }));

                                            if (tool_calls.length === 0) {
                                                tool_calls = additionalTCs;
                                            } else {
                                                additionalTCs.forEach((addTC) => {
                                                    const existingTC = tool_calls.find((tc) => tc.index === addTC.index);
                                                    if (existingTC) {
                                                        if (!existingTC.id && addTC.id) existingTC.id = addTC.id;
                                                        if (!existingTC.function?.name && addTC.function?.name) {
                                                            existingTC.function = existingTC.function || {};
                                                            existingTC.function.name = addTC.function.name;
                                                        }
                                                    }
                                                });
                                            }
                                        }

                                        tool_calls.forEach((toolCall: any) => {
                                            const index = toolCall.index ?? 0;

                                            if (!toolCallsAccumulator[index]) {
                                                toolCallsAccumulator[index] = {
                                                    id: toolCall.id || '',
                                                    name: toolCall.function?.name || toolCall.name || '',
                                                    args: '',
                                                    type: 'tool_call'
                                                };
                                            }

                                            if (toolCall.id && !toolCallsAccumulator[index].id) {
                                                toolCallsAccumulator[index].id = toolCall.id;
                                            }
                                            if (toolCall.function?.name && !toolCallsAccumulator[index].name) {
                                                toolCallsAccumulator[index].name = toolCall.function.name;
                                            }

                                            let args = '';
                                            if (toolCall.args) {
                                                args = toolCall.args;
                                            } else if (toolCall.function?.arguments) {
                                                args = toolCall.function.arguments;
                                            }

                                            if (args && typeof args === 'string') {
                                                toolCallsAccumulator[index].args += args;
                                            }
                                        });

                                        const currentToolCalls = Object.values(toolCallsAccumulator).map((toolCall: any) => {
                                            let parsedArgs = {};
                                            try {
                                                if (toolCall.args) {
                                                    parsedArgs = JSON.parse(toolCall.args);
                                                }
                                            } catch (e) {
                                                parsedArgs = {};
                                            }

                                            return {
                                                id: toolCall.id,
                                                name: toolCall.name,
                                                args: parsedArgs,
                                                type: toolCall.type
                                            };
                                        }).filter((toolCall) => toolCall.name);

                                        setSession((prev) => {
                                            const lastMessage = prev.history[prev.history.length - 1];
                                            return {
                                                ...prev,
                                                history: [...prev.history.slice(0, -1),
                                                    new LisaChatMessage({
                                                        ...lastMessage,
                                                        content: lastMessage.content + content,
                                                        toolCalls: currentToolCalls
                                                    })
                                                ],
                                            };
                                        });
                                        resp.push(content);
                                    }

                                    const finalToolCalls = Object.values(toolCallsAccumulator).map((toolCall: any) => {
                                        let parsedArgs = {};
                                        try {
                                            if (toolCall.args && typeof toolCall.args === 'string') {
                                                parsedArgs = JSON.parse(toolCall.args.trim());
                                            }
                                        } catch (e) {
                                            parsedArgs = {};
                                        }

                                        return {
                                            id: toolCall.id,
                                            name: toolCall.name,
                                            args: parsedArgs,
                                            type: toolCall.type
                                        };
                                    }).filter((toolCall) => toolCall.name);

                                    if (finalToolCalls.length > 0) {
                                        setSession((prev) => {
                                            const lastMessage = prev.history[prev.history.length - 1];
                                            return {
                                                ...prev,
                                                history: [...prev.history.slice(0, -1),
                                                    new LisaChatMessage({
                                                        ...lastMessage,
                                                        toolCalls: finalToolCalls
                                                    })
                                                ],
                                            };
                                        });
                                    }

                                    await memory.saveContext({ input: toolResults.map(tr => `${tr.toolName}: ${tr.content}`).join('; ') }, { output: resp.join('') });
                                    setIsStreaming(false);
                                } catch (exception) {
                                    setSession((prev) => ({
                                        ...prev,
                                        history: prev.history.slice(0, -1),
                                    }));
                                    throw exception;
                                }
                            } else {
                                // Non-streaming response
                                const response = await llmClient.invoke(messages, { tools: openAiTools });
                                const content = response.content as string;
                                await memory.saveContext({ input: toolResults.map(tr => `${tr.toolName}: ${tr.content}`).join('; ') }, { output: content });
                                setSession((prev) => ({
                                    ...prev,
                                    history: [...prev.history, new LisaChatMessage({ 
                                        type: 'ai', 
                                        content, 
                                        metadata: { ...metadata, continuingFromToolResults: true }, 
                                        toolCalls: [...(response.tool_calls ?? [])] 
                                    })],
                                }));
                            }

                            setDirtySession(true);
                        } catch (error) {
                            console.error('Error continuing conversation with tool results:', error);
                            notificationService.generateNotification('Failed to continue conversation with tool results', 'error', undefined, error.message ? <p>{error.message}</p> : undefined);
                        } finally {
                            setIsRunning(false);
                        }
                    }
                }
            }
        };

        handleToolCalls();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isRunning, session, dirtySession, callTool]);

    useEffect(() => {
        // always hide breadcrumbs
        dispatch(setBreadcrumbs([]));

        if (sessionId) {
            setInternalSessionId(sessionId);
            setLoadingSession(true);
            setSession({ ...session, history: [] });

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
                setChatConfiguration(sess.configuration ?? baseConfig);
                setSelectedModel(sess.configuration?.selectedModel ?? undefined);
                setRagConfig(sess.configuration?.ragConfig ?? {} as RagConfig);
                setLoadingSession(false);
                setUserPrompt('');
            });
        } else {
            const newSessionId = uuidv4();
            setChatConfiguration(baseConfig);
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
    }, [selectedModel, chatConfiguration.sessionConfiguration.modelArgs, auth.isAuthenticated, userPrompt]);

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

        let messageContent, ragDocs;

        if (isImageGenerationMode) {
            messageContent = userPrompt;
        } else if (fileContext?.startsWith('File context: data:image')) {
            const imageData = fileContext.replace('File context: ', '');
            messageContent = [
                { type: 'image_url', image_url: { url: `${imageData}` } },
                { type: 'text', text: userPrompt },
            ];
        } else if (useRag) {
            ragDocs = await fetchRelevantDocuments(userPrompt);
            messageContent = [
                { type: 'text', text: 'File context: ' + formatDocumentsAsString(ragDocs.data?.docs) },
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
                ...(isImageGenerationMode ? {
                    imageGenerationPrompt: true,
                    imageGenerationSettings: chatConfiguration.sessionConfiguration.imageGenerationArgs
                } : {}),
                ...(useRag && !isImageGenerationMode ? {
                    ragContext: formatDocumentsAsString(ragDocs.data?.docs, true),
                    ragDocuments: formatDocumentTitlesAsString(ragDocs.data?.docs)
                } : {})
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
    }, [userPrompt, useRag, fileContext, chatConfiguration.promptConfiguration.promptTemplate, generateResponse, isImageGenerationMode]);

    return (
        <div className='h-[80vh]'>
            {/* MCP Connections - invisible components that manage the connections */}
            {McpConnections}
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
                chatConfiguration={chatConfiguration}
                setChatConfiguration={setChatConfiguration}
                key={promptTemplateKey}
                config={config}
                type={filterPromptTemplateType}
            />
            <div className='overflow-y-auto h-[calc(100vh-25rem)] bottom-8'>
                <SpaceBetween direction='vertical' size='l'>
                    {session.history.map((message, idx) => (
                        <Message
                            key={idx}
                            message={message}
                            showMetadata={chatConfiguration.sessionConfiguration.showMetadata}
                            isRunning={false} isStreaming={isStreaming && idx === session.history.length - 1}
                            markdownDisplay={chatConfiguration.sessionConfiguration.markdownDisplay}
                            setChatConfiguration={setChatConfiguration}
                            handleSendGenerateRequest={handleSendGenerateRequest}
                            chatConfiguration={chatConfiguration}
                            setUserPrompt={setUserPrompt}
                        />
                    ))}
                    {isRunning && !isStreaming && <Message
                        isRunning={isRunning}
                        markdownDisplay={chatConfiguration.sessionConfiguration.markdownDisplay}
                        message={new LisaChatMessage({ type: 'ai', content: '' })}
                        setChatConfiguration={setChatConfiguration}
                        handleSendGenerateRequest={handleSendGenerateRequest}
                        chatConfiguration={chatConfiguration}
                        setUserPrompt={setUserPrompt}
                    />}
                    {session.history.length === 0 && sessionId === undefined && <div style={{ height: '400px', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', gap: '2em', textAlign: 'center' }}>
                        <div>
                            <Header variant='h1'>What would you like to do?</Header>
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'row', justifyContent: 'center', alignItems: 'center', gap: '1em', textAlign: 'center' }}>
                            <Button variant='normal' onClick={() => {
                                navigate(`/ai-assistant/${uuidv4()}`);
                                modelSelectRef?.current?.focus();
                            }}>
                                <SpaceBetween direction='horizontal' size='xs'>
                                    <FontAwesomeIcon icon={faMessage} />
                                    <TextContent>Start chatting</TextContent>
                                </SpaceBetween>
                            </Button>

                            {config?.configuration?.enabledComponents?.showPromptTemplateLibrary && (
                                <>
                                    <Button variant='normal' onClick={() => {
                                        setPromptTemplateKey(new Date().toISOString());
                                        setFilterPromptTemplateType(PromptTemplateType.Persona);
                                        setShowPromptTemplateModal(true);
                                    }}>
                                        <SpaceBetween direction='horizontal' size='xs'>
                                            <FontAwesomeIcon icon={faPenToSquare} />
                                            <TextContent>Select Persona</TextContent>
                                        </SpaceBetween>
                                    </Button>
                                    <Button variant='normal' onClick={() => {
                                        setPromptTemplateKey(new Date().toISOString());
                                        setFilterPromptTemplateType(PromptTemplateType.Directive);
                                        setShowPromptTemplateModal(true);
                                    }}>
                                        <SpaceBetween direction='horizontal' size='xs'>
                                            <FontAwesomeIcon icon={faComment} />
                                            <TextContent>Select Directive</TextContent>
                                        </SpaceBetween>
                                    </Button>
                                </>
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
                                        onChange={({ detail: { value } }) => {
                                            if (!value || value.length === 0) {
                                                setSelectedModel(undefined);
                                            } else {
                                                const model = allModels.find((model) => model.modelId === value);
                                                if (model) {
                                                    if (!model.streaming && chatConfiguration.sessionConfiguration.streaming) {
                                                        setChatConfiguration({ ...chatConfiguration, sessionConfiguration: { ...chatConfiguration.sessionConfiguration, streaming: false } });
                                                    } else if (model.streaming && !chatConfiguration.sessionConfiguration.streaming) {
                                                        setChatConfiguration({ ...chatConfiguration, sessionConfiguration: { ...chatConfiguration.sessionConfiguration, streaming: true } });
                                                    }

                                                    setSelectedModel(model);
                                                }
                                            }
                                        }}
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
                                actionButtonAriaLabel='Send message'
                                actionButtonIconName='send'
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
                                onAction={userPrompt.length > 0 && !isRunning && !loadingSession && handleSendGenerateRequest}
                                secondaryActions={
                                    <Box padding={{ left: 'xxs', top: 'xs' }}>
                                        <ButtonGroup
                                            ariaLabel='Chat actions'
                                            onItemClick={({ detail }) => {
                                                if (detail.id === 'settings') {
                                                    setSessionConfigurationModalVisible(true);
                                                }
                                                if (detail.id === 'edit-prompt-template') {
                                                    setPromptTemplateKey(new Date().toISOString());
                                                    setFilterPromptTemplateType(PromptTemplateType.Persona);
                                                    setShowPromptTemplateModal(true);
                                                }
                                                if (detail.id === 'upload-to-rag') {
                                                    setShowRagUploadModal(true);
                                                }
                                                if (detail.id === 'add-file-to-context') {
                                                    setShowContextUploadModal(true);
                                                }
                                                if (detail.id === 'summarize-document') {
                                                    setShowDocumentSummarizationModal(true);
                                                }
                                                if (detail.id === 'insert-prompt-template') {
                                                    setPromptTemplateKey(new Date().toISOString());
                                                    setFilterPromptTemplateType(PromptTemplateType.Directive);
                                                    setShowPromptTemplateModal(true);
                                                }
                                            }}
                                            items={[
                                                {
                                                    type: 'icon-button',
                                                    id: 'settings',
                                                    iconName: 'settings',
                                                    text: 'Session configuration'
                                                },
                                                ...(config?.configuration.enabledComponents.uploadRagDocs && window.env.RAG_ENABLED && !isImageGenerationMode ?
                                                    [{
                                                        type: 'icon-button',
                                                        id: 'upload-to-rag',
                                                        iconName: 'upload',
                                                        text: 'Upload to RAG',
                                                        disabled: !useRag
                                                    }] as ButtonGroupProps.Item[] : []),
                                                ...(config?.configuration.enabledComponents.uploadContextDocs && !isImageGenerationMode ?
                                                    [{
                                                        type: 'icon-button',
                                                        id: 'add-file-to-context',
                                                        iconName: 'insert-row',
                                                        text: 'Add file to context'
                                                    }] as ButtonGroupProps.Item[] : []),
                                                ...(config?.configuration.enabledComponents.showPromptTemplateLibrary ? [{
                                                    type: 'icon-button',
                                                    id: 'insert-prompt-template',
                                                    iconName: 'contact',
                                                    text: 'Insert Prompt Template'
                                                }] as ButtonGroupProps.Item[] : []),
                                                ...(config?.configuration.enabledComponents.documentSummarization ? [{
                                                    type: 'icon-button',
                                                    id: 'summarize-document',
                                                    iconName: 'transcript',
                                                    text: 'Summarize Document'
                                                }] as ButtonGroupProps.Item[] : []),
                                                ...(config?.configuration.enabledComponents.editPromptTemplate && !isImageGenerationMode ?
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

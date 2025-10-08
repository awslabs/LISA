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

import { useCallback, useState, useRef } from 'react';
import { ChatOpenAI } from '@langchain/openai';
import {
    LisaChatMessage,
    LisaChatMessageMetadata,
    LisaChatSession,
    MessageTypes, ModelFeatures,
} from '@/components/types';
import { RESTAPI_URI, RESTAPI_VERSION } from '@/components/utils';
import { IModel } from '@/shared/model/model-management.model';
import { GenerateLLMRequestParams, IChatConfiguration } from '@/shared/model/chat.configurations.model';
import { ChatMemory } from '@/shared/util/chat-memory';

// Custom hook for chat generation
export const useChatGeneration = ({
    chatConfiguration,
    selectedModel,
    isImageGenerationMode,
    session,
    setSession,
    metadata,
    memory,
    openAiTools,
    auth,
    notificationService
}: {
    chatConfiguration: IChatConfiguration;
    selectedModel: IModel;
    isImageGenerationMode: boolean;
    session: LisaChatSession;
    setSession: React.Dispatch<React.SetStateAction<LisaChatSession>>;
    metadata: LisaChatMessageMetadata;
    memory: ChatMemory;
    openAiTools: any;
    auth: any;
    notificationService: any;
}) => {
    const [isRunning, setIsRunning] = useState(false);
    const [isStreaming, setIsStreaming] = useState(false);
    const stopRequested = useRef(false);
    const modelSupportsTools = selectedModel?.features?.filter((feature) => feature.name === ModelFeatures.TOOL_CALLS)?.length && true;

    const createOpenAiClient = useCallback((streaming: boolean) => {
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
            }
        };

        return new ChatOpenAI(modelConfig);
    }, [selectedModel, auth, chatConfiguration]);

    const generateResponse = async (params: GenerateLLMRequestParams) => {
        setIsRunning(true);
        stopRequested.current = false;
        const startTime = performance.now(); // Start client timer
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

                    // Calculate response time
                    const responseTime = (performance.now() - startTime) / 1000;

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
                            },
                            usage: {
                                responseTime: parseFloat(responseTime.toFixed(2))
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
                // Always concatenate session history with new messages
                const messagesToProcess = session.history.concat(params.message);

                let messages = messagesToProcess.map((msg) => {
                    const baseMessage: any = {
                        role: msg.type === MessageTypes.HUMAN ? 'user' :
                            msg.type === MessageTypes.AI ? 'assistant' :
                                msg.type === MessageTypes.TOOL ? 'tool' : 'system',
                        content: Array.isArray(msg.content) ? msg.content : selectedModel.modelName.startsWith('sagemaker') ? msg.content : [{ type: 'text', text: msg.content }],
                    };

                    // Add tool_call_id for tool messages
                    if (msg.type === MessageTypes.TOOL && (msg.metadata as any)?.toolCallId) {
                        baseMessage.tool_call_id = (msg.metadata as any).toolCallId;
                    }

                    // Add tool_calls for AI messages that have tool calls
                    if (msg.type === MessageTypes.AI && msg.toolCalls && msg.toolCalls.length > 0) {
                        baseMessage.tool_calls = msg.toolCalls.map((toolCall) => ({
                            id: toolCall.id,
                            type: 'function',
                            function: {
                                name: toolCall.name,
                                arguments: JSON.stringify(toolCall.args)
                            }
                        }));
                    }

                    return baseMessage;
                });

                const [systemMessage, ...initialRemainingMessages] = messages;
                let remainingMessages = initialRemainingMessages.slice(-(chatConfiguration.sessionConfiguration.chatHistoryBufferSize * 2) - 1);

                if (remainingMessages[0]?.role === MessageTypes.TOOL) {
                    remainingMessages = remainingMessages.slice(1);
                }
                messages = [systemMessage, ...remainingMessages];

                if (chatConfiguration.sessionConfiguration.streaming) {
                    setIsStreaming(true);
                    const lastMessageMetadata = params.message.length > 0 ? params.message[params.message.length - 1].metadata : {};

                    // Always create empty AI message for streaming
                    setSession((prev) => ({
                        ...prev,
                        history: [...prev.history, new LisaChatMessage({ type: 'ai', content: '', metadata: { ...metadata, ...lastMessageMetadata } })],
                    }));

                    try {
                        const stream = await llmClient.stream(messages, { tools: modelSupportsTools ? openAiTools : undefined });
                        const resp: string[] = [];
                        const toolCallsAccumulator: { [index: number]: any } = {};

                        for await (const chunk of stream) {
                            // Check if stop was requested
                            if (stopRequested.current) {
                                notificationService.generateNotification('Generation stopped by user', 'info');
                                break;
                            }

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
                                } catch {
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
                            } catch {
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
                                if (lastMessage?.type === MessageTypes.AI) {
                                    return {
                                        ...prev,
                                        history: [...prev.history.slice(0, -1),
                                            new LisaChatMessage({
                                                ...lastMessage,
                                                toolCalls: finalToolCalls
                                            })
                                        ],
                                    };
                                }
                                return prev;
                            });
                        }

                        // Calculate response time and update the final message with usage info
                        const responseTime = (performance.now() - startTime) / 1000;
                        setSession((prev) => {
                            const lastMessage = prev.history[prev.history.length - 1];
                            if (lastMessage?.type === MessageTypes.AI) {
                                return {
                                    ...prev,
                                    history: [...prev.history.slice(0, -1),
                                        new LisaChatMessage({
                                            ...lastMessage,
                                            usage: {
                                                ...lastMessage.usage,
                                                responseTime: parseFloat(responseTime.toFixed(2))
                                            }
                                        })
                                    ],
                                };
                            }
                            return prev;
                        });

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
                    const response = await llmClient.invoke(messages, { tools: modelSupportsTools ? openAiTools : undefined });
                    const content = response.content as string;
                    const usage = response.response_metadata.tokenUsage;

                    // Calculate response time
                    const responseTime = (performance.now() - startTime) / 1000;

                    await memory.saveContext({ input: params.input }, { output: content });
                    setSession((prev) => ({
                        ...prev,
                        history: [...prev.history, new LisaChatMessage({
                            type: 'ai',
                            content,
                            metadata,
                            toolCalls: [...(response.tool_calls ?? [])],
                            usage: {
                                ...usage,
                                responseTime: parseFloat(responseTime.toFixed(2))
                            }
                        })],
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

    const stopGeneration = useCallback(() => {
        stopRequested.current = true;
    }, []);

    return { isRunning, setIsRunning, isStreaming, setIsStreaming, generateResponse, createOpenAiClient, stopGeneration };
};

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
import { RESTAPI_URI, RESTAPI_VERSION, markLastUserMessageAsGuardrailTriggered } from '@/components/utils';
import { IModel } from '@/shared/model/model-management.model';
import { GenerateLLMRequestParams, IChatConfiguration } from '@/shared/model/chat.configurations.model';
import { ChatMemory } from '@/shared/util/chat-memory';
import { useAppDispatch } from '@/config/store';
import { sessionApi } from '@/shared/reducers/session.reducer';

/**
 * Parses <thinking>...</thinking> blocks from content and extracts them.
 * Only extracts complete blocks (with both opening and closing tags).
 * Returns the cleaned content (with thinking blocks removed) and the extracted thinking content.
 */
const parseThinkingBlocks = (content: string): { cleanedContent: string; thinkingContent: string } => {
    if (!content || typeof content !== 'string') {
        return { cleanedContent: content, thinkingContent: '' };
    }

    // Match complete <thinking>...</thinking> blocks (case-insensitive)
    const thinkingRegex = /<thinking>([\s\S]*?)<\/thinking>/gi;
    const thinkingBlocks: string[] = [];
    let match;

    // Extract all complete thinking blocks
    while ((match = thinkingRegex.exec(content)) !== null) {
        if (match[1]) {
            thinkingBlocks.push(match[1].trim());
        }
    }

    // Remove all complete thinking blocks from content
    const cleanedContent = content.replace(thinkingRegex, '').trim();

    // Combine all thinking blocks with newlines
    const thinkingContent = thinkingBlocks.join('\n\n');

    return { cleanedContent, thinkingContent };
};

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
    const dispatch = useAppDispatch();
    const [isRunning, setIsRunning] = useState(false);
    const [isStreaming, setIsStreaming] = useState(false);
    const stopRequested = useRef(false);
    const modelSupportsTools = selectedModel?.features?.filter((feature) => feature.name === ModelFeatures.TOOL_CALLS)?.length && true;
    const modelSupportsReasoning = selectedModel?.features?.find((feature) => feature.name === ModelFeatures.REASONING) ? true : false;

    const createOpenAiClient = useCallback((streaming: boolean) => {
        const modelConfig = {
            modelName: selectedModel?.modelId,
            // Use auth token as API key - LangChain will pass it in the Authorization header
            apiKey: auth.user?.id_token || 'dummy-key',
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

        // Capture session state before adding messages to determine if this is a new session
        const isNewSession = session.history.length === 0;

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
                // Filter out guardrail-triggered messages when sending to model
                const filteredHistory = session.history.filter((msg) => !msg.guardrailTriggered);
                // Always concatenate filtered session history with new messages
                const messagesToProcess = filteredHistory.concat(params.message);

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
                        if (modelSupportsReasoning) {
                            if (msg.reasoningContent) {
                                const thinkingBlock: any = {
                                    type: 'thinking',
                                    thinking: msg.reasoningContent
                                };
                                thinkingBlock.signature = msg.reasoningSignature;
                                baseMessage.content.unshift(thinkingBlock);
                            }
                        }
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
                        const stream = await llmClient.stream(messages, { tools: modelSupportsTools ? openAiTools : undefined, ...(modelSupportsReasoning ? { reasoning: { effort: chatConfiguration.sessionConfiguration.modelArgs.reasoning_effort } } : {}) });
                        const resp: string[] = [];
                        const toolCallsAccumulator: { [index: number]: any } = {};
                        let reasoningContentAccumulator = '';
                        let reasoningSignatureAccumulator = '';
                        let rawContentAccumulator = ''; // Accumulate raw content to parse thinking blocks

                        let guardrailTriggered = false;

                        for await (const chunk of stream) {
                            // Check if stop was requested
                            if (stopRequested.current) {
                                notificationService.generateNotification('Generation stopped by user', 'info');
                                break;
                            }

                            const content = chunk.content as string;

                            // Accumulate raw content for thinking block parsing
                            if (content) {
                                rawContentAccumulator += content;
                            }

                            // Check if this chunk indicates a guardrail was triggered
                            const isGuardrailTriggered = (chunk as any).id === 'guardrail-response';

                            if (isGuardrailTriggered) {
                                guardrailTriggered = true;
                            }

                            // Accumulate reasoning content from additional_kwargs
                            if ((chunk as any).additional_kwargs?.reasoning_content) {
                                reasoningContentAccumulator += (chunk as any).additional_kwargs.reasoning_content;
                            }

                            if ((chunk as any).additional_kwargs?.thinking_signature) {
                                reasoningSignatureAccumulator += (chunk as any).additional_kwargs.thinking_signature;
                            }

                            // Parse thinking blocks from accumulated content (only if model supports reasoning)
                            // Only parse complete blocks (wait for closing tag)
                            let cleanedContent = rawContentAccumulator;
                            if (modelSupportsReasoning) {
                                const parsed = parseThinkingBlocks(rawContentAccumulator);
                                cleanedContent = parsed.cleanedContent;
                                // If we found thinking content and API didn't provide it, use parsed content
                                // Update reasoning content as complete thinking blocks are found
                                if (parsed.thinkingContent) {
                                    if (!reasoningContentAccumulator) {
                                        reasoningContentAccumulator = parsed.thinkingContent;
                                    } else if (parsed.thinkingContent.length > reasoningContentAccumulator.length) {
                                        // If parsed content is longer, it means we got a complete block, update it
                                        reasoningContentAccumulator = parsed.thinkingContent;
                                    }
                                }
                            }

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
                                // Use cleaned content (with thinking blocks removed) for display
                                const newContent = cleanedContent;
                                const finalContent = (reasoningContentAccumulator && !newContent.trim()) ? '\u00A0' : newContent;
                                return {
                                    ...prev,
                                    history: [...prev.history.slice(0, -1),
                                        new LisaChatMessage({
                                            ...lastMessage,
                                            content: finalContent,
                                            toolCalls: currentToolCalls,
                                            reasoningContent: reasoningContentAccumulator || undefined,
                                            reasoningSignature: reasoningSignatureAccumulator,
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

                        // Final parse of thinking blocks from complete response (only if model supports reasoning)
                        const finalRawContent = resp.join('');
                        let finalCleanedContent = finalRawContent;
                        let finalReasoningContent = reasoningContentAccumulator;
                        if (modelSupportsReasoning) {
                            const parsed = parseThinkingBlocks(finalRawContent);
                            finalCleanedContent = parsed.cleanedContent;
                            // Use parsed thinking content if we didn't get it from API
                            if (parsed.thinkingContent && !finalReasoningContent) {
                                finalReasoningContent = parsed.thinkingContent;
                            }
                        }

                        // Calculate response time and update the final message with usage info
                        const responseTime = (performance.now() - startTime) / 1000;
                        setSession((prev) => {
                            const lastMessage = prev.history[prev.history.length - 1];
                            if (lastMessage?.type === MessageTypes.AI) {
                                let updatedHistory = [...prev.history.slice(0, -1),
                                    new LisaChatMessage({
                                        ...lastMessage,
                                        content: finalCleanedContent,
                                        usage: {
                                            ...lastMessage.usage,
                                            responseTime: parseFloat(responseTime.toFixed(2))
                                        },
                                        guardrailTriggered: guardrailTriggered,
                                        reasoningContent: finalReasoningContent || undefined,
                                        reasoningSignature: reasoningSignatureAccumulator,
                                    })
                                ];

                                // If guardrail was triggered, also mark the user message
                                if (guardrailTriggered) {
                                    updatedHistory = markLastUserMessageAsGuardrailTriggered(updatedHistory);
                                }

                                return {
                                    ...prev,
                                    history: updatedHistory,
                                };
                            }
                            return prev;
                        });

                        await memory.saveContext({ input: params.input }, { output: finalCleanedContent });
                        setIsStreaming(false);
                    } catch (exception) {
                        setSession((prev) => ({
                            ...prev,
                            history: prev.history.slice(0, -1),
                        }));
                        throw exception;
                    }
                } else {
                    const response = await llmClient.invoke(messages, { tools: modelSupportsTools ? openAiTools : undefined, ...(modelSupportsReasoning ? { reasoning: { effort: chatConfiguration.sessionConfiguration.modelArgs.reasoning_effort } } : {}) });
                    const rawContent = response.content as string;
                    const usage = (response.response_metadata as any)?.tokenUsage;

                    // Check if guardrail was triggered
                    const isGuardrailTriggered = (response as any)?.id === 'guardrail-response';

                    // Get reasoning content from API (preferred)
                    let reasoningContent = (response as any).additional_kwargs?.reasoning_content;
                    const reasoningSignature = (response as any).additional_kwargs?.thinking_signature;

                    // Parse thinking blocks from content (only if model supports reasoning)
                    let cleanedContent = rawContent;
                    if (modelSupportsReasoning) {
                        const parsed = parseThinkingBlocks(rawContent);
                        cleanedContent = parsed.cleanedContent;
                        // If we found thinking content and API didn't provide it, use parsed content
                        if (parsed.thinkingContent && !reasoningContent) {
                            reasoningContent = parsed.thinkingContent;
                        }
                    }

                    // Calculate response time
                    const responseTime = (performance.now() - startTime) / 1000;

                    await memory.saveContext({ input: params.input }, { output: cleanedContent });

                    // Create the AI message with cleaned content (thinking blocks removed)
                    const aiMessage = new LisaChatMessage({
                        type: 'ai',
                        content: cleanedContent,
                        metadata,
                        toolCalls: [...(response.tool_calls ?? [])],
                        usage: {
                            ...usage,
                            responseTime: parseFloat(responseTime.toFixed(2))
                        },
                        guardrailTriggered: isGuardrailTriggered,
                        reasoningContent: reasoningContent,
                        reasoningSignature: reasoningSignature
                    });

                    setSession((prev) => {
                        let updatedHistory = [...prev.history, aiMessage];

                        // If guardrail was triggered, also mark the user message
                        if (isGuardrailTriggered) {
                            updatedHistory = markLastUserMessageAsGuardrailTriggered(updatedHistory);
                        }

                        return {
                            ...prev,
                            history: updatedHistory,
                        };
                    });
                }
            }
        } catch (error) {
            notificationService.generateNotification('An error occurred while processing your request.', 'error', undefined, error.error?.message ? <p>{JSON.stringify(error.error.message)}</p> : undefined);
            setIsRunning(false);
            throw error;
        } finally {
            setIsRunning(false);
            // Invalidate session cache after any message is sent to ensure fresh data
            // This ensures session details are up-to-date when viewed from other components
            if (session.sessionId) {
                // Invalidate session cache after any message is sent to ensure fresh data
                // For new sessions, also invalidate the session list so they appear in the sidebar
                dispatch(sessionApi.util.invalidateTags([
                    { type: 'session' as const, id: session.sessionId },
                    ...(isNewSession ? ['sessions' as const] : [])
                ]));
            }
        }
    };

    const stopGeneration = useCallback(() => {
        stopRequested.current = true;
    }, []);

    return { isRunning, setIsRunning, isStreaming, setIsStreaming, generateResponse, createOpenAiClient, stopGeneration };
};

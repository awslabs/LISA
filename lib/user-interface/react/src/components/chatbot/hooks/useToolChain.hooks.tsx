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

import React, { useCallback, useRef, useState } from 'react';
import { LisaChatMessage, LisaChatSession, MessageTypes } from '@/components/types';
import { GenerateLLMRequestParams } from '@/shared/model/chat.configurations.model';
import { McpPreferences } from '@/shared/reducers/user-preferences.reducer';

export const useToolChain = ({
    callTool,
    generateResponse,
    setSession,
    notificationService,
    toolToServerMap,
    mcpPreferences,
}: {
    callTool: (toolName: string, args: any) => Promise<any>;
    generateResponse: (params: GenerateLLMRequestParams) => Promise<void>;
    session: LisaChatSession;
    setSession: (updater: (prev: LisaChatSession) => LisaChatSession) => void;
    notificationService: any;
    toolToServerMap: Map<string, string>,
    mcpPreferences: McpPreferences,
}) => {
    const isProcessingChain = useRef(false);
    const stopRequested = useRef(false);
    const [callingToolName, setCallingToolName] = useState<string>(undefined);

    // Local modal state for tool approvals
    const [toolApprovalModal, setToolApprovalModal] = useState<{
        visible: boolean;
        tool: any;
        resolve: (value: any) => void;
        reject: (error: any) => void;
    } | null>(null);

    const callMcpTool = useCallback(async (tool: any) => {
        return await callTool(tool.name, { ...tool.args });
    }, [callTool]);

    const formatToolResult = useCallback((result: any) => {
        let toolResultContent = '';
        if (Array.isArray(result)) {
            toolResultContent = result.map((item) => {
                if (item.type === 'text') {
                    return item.text;
                }
                return JSON.stringify(item, null, 2);
            }).join('\n');
        } else if (typeof result === 'object' && result !== null) {
            toolResultContent = JSON.stringify(result, null, 2);
        } else {
            toolResultContent = String(result);
        }
        return toolResultContent;
    }, []);

    const executeToolWithApproval = useCallback(async (tool: any): Promise<any> => {
        const checkOverriddenApproval = (toolName: string): boolean => {
            if (mcpPreferences?.overrideAllApprovals) {
                return true;
            } else {
                const serverName = toolToServerMap.get(toolName);
                return mcpPreferences?.enabledServers.find((server: any) => server.name === serverName)?.autoApprovedTools?.includes(toolName) ?? false;
            }
        };

        if (checkOverriddenApproval(tool.name)) {
            return await callTool(tool.name, tool.args);
        } else {
            return new Promise((resolve, reject) => {
                setToolApprovalModal({
                    visible: true,
                    tool,
                    resolve,
                    reject
                });
            });
        }
    }, [callTool, mcpPreferences, toolToServerMap]);

    const handleToolApproval = useCallback(async () => {
        if (!toolApprovalModal) return;

        try {
            setToolApprovalModal(null);
            const result = await callMcpTool(toolApprovalModal.tool);
            toolApprovalModal.resolve(result);
        } catch (error) {
            toolApprovalModal.reject(error);
        }
    }, [toolApprovalModal, callMcpTool]);

    const handleToolRejection = useCallback(() => {
        if (!toolApprovalModal) return;

        toolApprovalModal.reject(new Error('Tool execution cancelled by user'));
        setToolApprovalModal(null);
    }, [toolApprovalModal]);

    const processToolCallChain = useCallback(async (currentSession: LisaChatSession) => {

        if (isProcessingChain.current) {
            return; // Prevent concurrent processing
        }

        const lastMessage = currentSession.history.at(-1);

        // Check if there are tool calls to process
        if (!lastMessage || lastMessage.type !== MessageTypes.AI || !lastMessage.toolCalls || lastMessage.toolCalls.length === 0) {
            return; // No tool calls to process
        }

        isProcessingChain.current = true;
        stopRequested.current = false;

        try {
            const toolCalls = lastMessage.toolCalls;
            const toolResults = [];

            // Execute tool calls sequentially to avoid overwhelming the servers
            for (const tool of toolCalls) {
                // Check if stop was requested before each tool call
                if (stopRequested.current) {
                    notificationService.generateNotification('Tool chain execution stopped by user', 'info');
                    break;
                }

                setCallingToolName(tool.name);
                try {
                    const result = await executeToolWithApproval(tool);
                    const formattedContent = formatToolResult(result);

                    toolResults.push({
                        toolCallId: tool.id,
                        toolName: tool.name,
                        content: formattedContent
                    });
                } catch (error) {
                    if (error.message === 'Tool execution cancelled by user') {
                        notificationService.generateNotification(`Tool execution cancelled: ${tool.name}`, 'info');
                        break; // Stop the chain if user cancels
                    } else {
                        notificationService.generateNotification(
                            `Tool execution failed: ${tool.name}`,
                            'error',
                            undefined,
                            <p>{error.message}</p>
                        );

                        // Add error as tool result to maintain conversation flow
                        toolResults.push({
                            toolCallId: tool.id,
                            toolName: tool.name,
                            content: `Error: ${error.message}`
                        });
                    }
                }
            }

            if (toolResults.length > 0 && !stopRequested.current) {
                // Create tool result messages
                const toolResultMessages = toolResults.map((tr) => {
                    const originalTool = toolCalls.find((tool) => tool.id === tr.toolCallId);
                    return new LisaChatMessage({
                        type: MessageTypes.TOOL,
                        content: tr.content,
                        metadata: {
                            toolCallId: tr.toolCallId,
                            toolName: tr.toolName,
                            isToolResult: true,
                            args: originalTool ? originalTool.args : {},
                        } as any
                    });
                });

                // Add tool result messages to session history
                setSession((prev) => {
                    return {
                        ...prev,
                        history: [...prev.history, ...toolResultMessages]
                    };
                });

                // Generate response - this will use the updated session state
                await generateResponse({ message: toolResultMessages, input: toolResultMessages[0]?.content.toString() });
            }
        } finally {
            isProcessingChain.current = false;
            setCallingToolName(undefined);
        }
    }, [formatToolResult, generateResponse, setSession, notificationService, executeToolWithApproval]);

    const startToolChain = useCallback(async (sessionToProcess: LisaChatSession) => {
        await processToolCallChain(sessionToProcess);
    }, [processToolCallChain]);

    const stopToolChain = useCallback(() => {
        stopRequested.current = true;
    }, []);

    return {
        startToolChain,
        stopToolChain,
        isProcessingChain: () => isProcessingChain.current,
        callingToolName,
        toolApprovalModal,
        handleToolApproval,
        handleToolRejection
    };
};

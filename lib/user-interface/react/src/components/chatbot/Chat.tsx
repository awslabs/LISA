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
import { useAuth } from '../../auth/useAuth';
import Form from '@cloudscape-design/components/form';
import Box from '@cloudscape-design/components/box';
import SpaceBetween from '@cloudscape-design/components/space-between';
import Spinner from '@cloudscape-design/components/spinner';
import {
    Autosuggest,
    Checkbox,
    Grid,
    Icon,
    Flashbar,
} from '@cloudscape-design/components';
import StatusIndicator from '@cloudscape-design/components/status-indicator';

import Message from './components/Message';
import {
    LisaAttachImageResponse,
    LisaChatMessage,
    LisaChatSession,
    MessageTypes,
    ModelFeatures
} from '../types';
import RagControls from './components/RagOptions';
import { ContextUploadModal, RagUploadModal } from './components/FileUploadModals';
import { useGetAllModelsQuery } from '@/shared/reducers/model-management.reducer';
import { ModelStatus, ModelType } from '@/shared/model/model-management.model';
import {
    useAttachImageToSessionMutation,
    useGetSessionHealthQuery,
    useLazyGetSessionByIdQuery,
    useListSessionsQuery,
    useUpdateSessionMutation,
} from '@/shared/reducers/session.reducer';
import { useAppDispatch, useAppSelector } from '@/config/store';
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
import { useDynamicMaxRows } from './hooks/useDynamicMaxRows';
import { WelcomeScreen } from './components/WelcomeScreen';
import { buildMessageContent, buildMessageMetadata } from './utils/messageBuilder.utils';
import { formatContextWindow } from '../model-management/ModelManagementUtils';
import { getButtonItems, useButtonActions } from './config/buttonConfig';
import PromptPreview from './components/PromptPreview';
import ChatPromptInput from './components/ChatPromptInput';
import { Mode } from '@cloudscape-design/global-styles';
import ColorSchemeContext from '@/shared/color-scheme.provider';
import {
    McpServerStatus,
    useInvokeBedrockAgentMutation,
    useListBedrockAgentsQuery,
    useListMcpServersQuery,
    type McpServer,
} from '@/shared/reducers/mcp-server.reducer';
import {
    DefaultUserPreferences,
    McpPreferences,
    useGetUserPreferencesQuery, UserPreferences, useUpdateUserPreferencesMutation
} from '@/shared/reducers/user-preferences.reducer';
import { setConfirmationModal } from '@/shared/reducers/modal.reducer';
import { useLazyGetPromptTemplateQuery } from '@/shared/reducers/prompt-templates.reducer';
import { useGetStackQuery } from '@/shared/reducers/chat-assistant-stacks.reducer';
import { useListMcpToolsQuery } from '@/shared/reducers/mcp-tools.reducer';
import ConfirmationModal from '@/shared/modal/confirmation-modal';
import { selectCurrentUsername } from '@/shared/reducers/user.reducer';
import { isWorkbenchMcpServer } from '../utils';
import DocumentSidePanel from './components/DocumentSidePanel';
import { useDocumentSidePanel } from '@/shared/hooks/useDocumentSidePanel';

const EMPTY_STACK_MCP_SERVERS: McpServer[] = [];

export default function Chat ({ sessionId, initialStack }) {
    const dispatch = useAppDispatch();
    const navigate = useNavigate();
    const config: IConfiguration = useContext(ConfigurationContext);
    const ragSelectionAvailable = config?.configuration?.enabledComponents?.ragSelectionAvailable ?? true;
    const notificationService = useNotificationService(dispatch);
    const modelSelectRef = useRef<HTMLInputElement>(null);
    const bottomRef = useRef(null);
    const scrollContainerRef = useRef<HTMLDivElement>(null);
    const auth = useAuth();
    const userName = useAppSelector(selectCurrentUsername);

    // API hooks
    const [getRelevantDocuments] = useLazyGetRelevantDocumentsQuery();
    const { data: sessionHealth } = useGetSessionHealthQuery(undefined, { refetchOnMountOrArgChange: true });
    const [getSessionById] = useLazyGetSessionByIdQuery();
    const [updateSession] = useUpdateSessionMutation();
    const [attachImageToSession] = useAttachImageToSessionMutation();
    const { data: allModelsRaw, isFetching: isFetchingModels } = useGetAllModelsQuery(undefined, {
        refetchOnMountOrArgChange: 5,
    });

    const allModels = useMemo(() =>
        (allModelsRaw || []).filter((model) =>
            (model.modelType === ModelType.textgen || model.modelType === ModelType.imagegen || model.modelType === ModelType.videogen) &&
            model.status === ModelStatus.InService
        ),
    [allModelsRaw]
    );

    // Same types as allModels but include Stopped for dropdown (shown disabled)
    const allModelsWithStopped = useMemo(() =>
        (allModelsRaw || []).filter((model) =>
            (model.modelType === ModelType.textgen || model.modelType === ModelType.imagegen || model.modelType === ModelType.videogen) &&
            (model.status === ModelStatus.InService || model.status === ModelStatus.Stopped)
        ),
    [allModelsRaw]
    );

    // Session and effective assistant stack (from nav or loaded when resuming)
    const {
        session,
        setSession,
        setInternalSessionId,
        loadingSession,
        chatConfiguration,
        setChatConfiguration,
        selectedModel,
        setSelectedModel,
        ragConfig,
        setRagConfig,
        chatAssistantId,
        setChatAssistantId,
        internalSessionId,
    } = useSession(sessionId, getSessionById);
    const { data: resumedStack } = useGetStackQuery(chatAssistantId ?? '', {
        skip: !chatAssistantId || !!initialStack,
    });
    const effectiveStack = initialStack ?? (chatAssistantId && resumedStack ? resumedStack : undefined);

    // When using an assistant stack, restrict model dropdown to stack's modelIds; empty/null => no options
    const modelsForDropdown = useMemo(() => {
        if (!effectiveStack) return allModelsWithStopped;
        const ids = effectiveStack.modelIds ?? [];
        return ids.length ? allModelsWithStopped.filter((m) => ids.includes(m.modelId)) : [];
    }, [allModelsWithStopped, effectiveStack]);
    const { data: userPreferences } = useGetUserPreferencesQuery();
    const { data: mcpServers } = useListMcpServersQuery(undefined, {
        refetchOnMountOrArgChange: true,
        selectFromResult: (state) => ({
            isFetching: state.isFetching,
            data: (state.data?.Items || []).filter((server) => (server.status === McpServerStatus.Active)),
        })
    },);

    // State management
    const [userPrompt, setUserPrompt] = useState('');
    const [fileContext, setFileContext] = useState('');
    const [fileContextName, setFileContextName] = useState('');
    const [fileContextFiles, setFileContextFiles] = useState<Array<{name: string, content: string}>>([]);
    const [dirtySession, setDirtySession] = useState(false);
    const [isConnected, setIsConnected] = useState(false);
    const [useRag, setUseRag] = useState(false);
    const [preferences, setPreferences] = useState<UserPreferences>(undefined);
    const [modelFilterValue, setModelFilterValue] = useState('');
    const [hasUserInteractedWithModel, setHasUserInteractedWithModel] = useState(false);
    const [mermaidRenderComplete, setMermaidRenderComplete] = useState(0);
    const [videoLoadComplete, setVideoLoadComplete] = useState(0);
    const [imageLoadComplete, setImageLoadComplete] = useState(0);
    const [shouldAutoScroll, setShouldAutoScroll] = useState(true);
    const [updatingAutoApprovalForTool, setUpdatingAutoApprovalForTool] = useState<string | null>(null);
    const [showMarkdownPreview, setShowMarkdownPreview] = useState(false);

    // Document side panel management
    const { showDocSidePanel, selectedDocumentForPanel, handleOpenDocument, handleCloseDocPanel } = useDocumentSidePanel();

    // Close document side panel when session changes
    useEffect(() => {
        if (showDocSidePanel) {
            handleCloseDocPanel();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [sessionId]);

    // Get color scheme context for markdown preview
    const { colorScheme } = useContext(ColorSchemeContext);
    const isDarkMode = colorScheme === Mode.Dark;

    // Callback to handle Mermaid diagram rendering completion
    const handleMermaidRenderComplete = useCallback(() => {
        setMermaidRenderComplete((prev) => prev + 1);
    }, []);

    // Callback to handle video load completion (for auto-scroll)
    const handleVideoLoadComplete = useCallback(() => {
        setVideoLoadComplete((prev) => prev + 1);
    }, []);

    // Callback to handle image load completion (for auto-scroll)
    const handleImageLoadComplete = useCallback(() => {
        // Use setTimeout with RAF to ensure the DOM has fully updated and reflowed
        // before triggering scroll. Images can cause significant layout shifts.
        setTimeout(() => {
            requestAnimationFrame(() => {
                setImageLoadComplete((prev) => prev + 1);
            });
        }, 50);
    }, []);

    // Ref to track if we're processing tool calls to prevent infinite loops
    const isProcessingToolCalls = useRef(false);
    const lastProcessedMessageIndex = useRef(-1);
    const startToolChainRef = useRef<((session: LisaChatSession) => Promise<void>) | undefined>(undefined);

    // Memoize enabled servers. When using an assistant stack with mcpServerIds, use those servers
    // directly (turned on for this session) regardless of user preferences; otherwise use preferences.
    const enabledServers = useMemo(() => {
        if (!mcpServers) return undefined;
        if (effectiveStack) {
            const ids = effectiveStack.mcpServerIds ?? [];
            return ids.length ? mcpServers.filter((server) => ids.includes(server.id)) : EMPTY_STACK_MCP_SERVERS;
        }
        const enabledServerPrefs = userPreferences?.preferences?.mcp?.enabledServers;
        const base = enabledServerPrefs
            ? mcpServers.filter((server) => enabledServerPrefs.map((s) => s.id).includes(server.id))
            : [];
        return base.length ? base : undefined;
    }, [mcpServers, userPreferences, effectiveStack]);

    // Tool call loop prevention
    const consecutiveToolCallCount = useRef(0);
    const TOOL_CALL_LIMIT = 20;
    const pendingToolChainExecution = useRef<(() => Promise<void>) | null>(null);

    const needsWorkbenchToolList = Boolean(enabledServers?.some(isWorkbenchMcpServer));
    const workbenchListQuery = useListMcpToolsQuery(undefined, { skip: !needsWorkbenchToolList });
    const workbenchToolListDataUpdatedAt =
        'dataUpdatedAt' in workbenchListQuery && typeof workbenchListQuery.dataUpdatedAt === 'number'
            ? workbenchListQuery.dataUpdatedAt
            : undefined;
    // Include metadata so edits/resync change the key and remount the MCP client; ids alone miss same-file updates.
    const workbenchToolListFingerprint = useMemo(() => {
        if (!needsWorkbenchToolList) {
            return '';
        }
        const files = workbenchListQuery.data ?? [];
        return [...files]
            .map((t) => `${t.id}\0${t.updated_at ?? ''}\0${t.size ?? ''}`)
            .sort()
            .join('\n');
    }, [needsWorkbenchToolList, workbenchListQuery.data]);

    // Use the custom hook to manage multiple MCP connections
    const { tools: mcpTools, callTool, McpConnections, toolToServerMap, readyMcpServerCount } = useMultipleMcp(
        enabledServers,
        userPreferences?.preferences?.mcp,
        session?.sessionId,
        { workbenchToolListFingerprint, workbenchToolListDataUpdatedAt },
    );
    const [invokeBedrockAgent] = useInvokeBedrockAgentMutation();

    /** User opt-in + stack allow-list (same shape as MCP prefs vs stack), before intersecting the admin catalog from list Bedrock agents API. */
    const bedrockAgentCandidatesForChat = useMemo(() => {
        const optedIn = userPreferences?.preferences?.bedrockAgents?.enabledAgents?.filter((a) => a.enabled) ?? [];
        if (optedIn.length === 0) return [];
        if (effectiveStack) {
            const allow = new Set(effectiveStack.bedrockAgentIds ?? []);
            if (allow.size === 0) return [];
            return optedIn.filter((a) => allow.has(a.agentId));
        }
        return optedIn;
    }, [userPreferences?.preferences?.bedrockAgents?.enabledAgents, effectiveStack]);

    const skipBedrockCatalog = !config?.configuration?.enabledComponents?.bedrockAgents
        || bedrockAgentCandidatesForChat.length === 0;
    const { data: bedrockAgentsCatalog } = useListBedrockAgentsQuery(undefined, { skip: skipBedrockCatalog });

    /** Enabled for chat only if still returned by list Bedrock agents (admin catalog), like MCP servers vs list MCP API. */
    const enabledBedrockAgentsForChat = useMemo(() => {
        if (bedrockAgentCandidatesForChat.length === 0) return [];
        const agents = bedrockAgentsCatalog?.agents;
        if (!agents?.length) return [];
        const allowedIds = new Set(agents.map((a) => a.agentId));
        return bedrockAgentCandidatesForChat.filter((a) => allowedIds.has(a.agentId));
    }, [bedrockAgentCandidatesForChat, bedrockAgentsCatalog?.agents]);

    const bedrockFunctionToolIndex = useMemo(() => {
        const m = new Map<string, {
            agentId: string;
            functionName: string;
            actionGroupId: string;
            actionGroupName?: string;
        }>();
        const agents = bedrockAgentsCatalog?.agents;
        if (!agents) return m;
        for (const pref of enabledBedrockAgentsForChat) {
            const row = agents.find((x) => x.agentId === pref.agentId);
            const disabled = new Set(pref.disabledActionTools ?? []);
            for (const t of row?.actionTools ?? []) {
                if (disabled.has(t.openAiToolName)) {
                    continue;
                }
                m.set(t.openAiToolName, {
                    agentId: pref.agentId,
                    functionName: t.functionName,
                    actionGroupId: t.actionGroupId,
                    actionGroupName: t.actionGroupName || undefined,
                });
            }
        }
        return m;
    }, [bedrockAgentsCatalog?.agents, enabledBedrockAgentsForChat]);

    const isBedrockManagedTool = useCallback(
        (name: string) => name === 'invoke_bedrock_agent' || bedrockFunctionToolIndex.has(name),
        [bedrockFunctionToolIndex],
    );

    const bedrockOpenAiToolFragments = useMemo(() => {
        if (!config?.configuration?.enabledComponents?.bedrockAgents || enabledBedrockAgentsForChat.length === 0) {
            return [];
        }
        const agentIds = enabledBedrockAgentsForChat.map((a) => a.agentId);
        const names = enabledBedrockAgentsForChat.map((a) => `${a.agentId}: ${a.name}`).join('; ');
        const fragments: Array<{ type: string; function: Record<string, unknown> }> = [
            {
                type: 'function',
                function: {
                    name: 'invoke_bedrock_agent',
                    description:
                        'Invoke an Amazon Bedrock Agent with open-ended natural language. Prefer the specific '
                        + 'bedrock_* tools when the user wants a defined action (e.g. weather, add numbers). '
                        + `Enabled agents: ${names}`,
                    parameters: {
                        type: 'object',
                        properties: {
                            agentId: {
                                type: 'string',
                                enum: agentIds,
                                description: 'Target agent ID',
                            },
                            inputText: {
                                type: 'string',
                                description: 'User message or instruction to send to the agent',
                            },
                        },
                        required: ['agentId', 'inputText'],
                    },
                },
            },
        ];
        for (const pref of enabledBedrockAgentsForChat) {
            const row = bedrockAgentsCatalog?.agents?.find((x) => x.agentId === pref.agentId);
            const disabled = new Set(pref.disabledActionTools ?? []);
            for (const t of row?.actionTools ?? []) {
                if (disabled.has(t.openAiToolName)) {
                    continue;
                }
                const schema = t.parameterSchema ?? { type: 'object', properties: {}, required: [] as string[] };
                fragments.push({
                    type: 'function',
                    function: {
                        name: t.openAiToolName,
                        description:
                            `[Bedrock agent: ${row?.agentName ?? pref.agentId}; action group: ${t.actionGroupName || t.actionGroupId}] `
                            + (t.description || t.functionName),
                        parameters: {
                            type: schema.type ?? 'object',
                            properties: schema.properties ?? {},
                            required: schema.required ?? [],
                        },
                    },
                });
            }
        }
        return fragments;
    }, [
        config?.configuration?.enabledComponents,
        enabledBedrockAgentsForChat,
        bedrockAgentsCatalog?.agents,
    ]);

    const [updatePreferences, {isSuccess: isUpdatingPreferencesSuccess, isError: isUpdatingPreferencesError, isLoading: isUpdatingPreferences}] = useUpdateUserPreferencesMutation();

    // Load markdown preview preference from user preferences
    useEffect(() => {
        if (userPreferences?.preferences?.showMarkdownPreview !== undefined) {
            setShowMarkdownPreview(userPreferences.preferences.showMarkdownPreview);
        }
    }, [userPreferences]);

    // Handle markdown preview toggle
    const handleToggleMarkdownPreview = useCallback((enabled: boolean) => {
        setShowMarkdownPreview(enabled);

        const updated = {
            ...preferences,
            preferences: {
                ...preferences.preferences,
                showMarkdownPreview: enabled
            }
        };
        setPreferences(updated);
        updatePreferences(updated);
    }, [preferences, updatePreferences, setPreferences]);

    useEffect(() => {
        if (userPreferences) {
            setPreferences(userPreferences);
        } else {
            setPreferences({ ...DefaultUserPreferences, user: userName });
        }
    }, [userPreferences, userName]);

    // Handle preferences update success
    useEffect(() => {
        if (isUpdatingPreferencesSuccess) {
            notificationService.generateNotification('Successfully updated tool preferences', 'success');
            setUpdatingAutoApprovalForTool(null);
        }
    }, [isUpdatingPreferencesSuccess, notificationService]);

    // Handle preferences update error
    useEffect(() => {
        if (isUpdatingPreferencesError) {
            notificationService.generateNotification('Error updating tool preferences', 'error');
            setUpdatingAutoApprovalForTool(null);
        }
    }, [isUpdatingPreferencesError, notificationService]);

    // Custom hooks
    const { dynamicMaxRows } = useDynamicMaxRows();

    // Get sessions list lastUpdated timestamp
    const { data: sessions } = useListSessionsQuery(undefined, { refetchOnMountOrArgChange: 5 });
    const currentSessionSummary = useMemo(() =>
        sessions?.find((s) => s.sessionId === session.sessionId),
    [sessions, session.sessionId]
    );

    const { modelsOptions, handleModelChange } = useModels(
        modelsForDropdown,
        chatConfiguration,
        setChatConfiguration
    );

    // Check if the selected model has been deleted (exists in session but not in available models)
    const isModelDeleted = useMemo(() => {
        if (!selectedModel) return false;
        return !allModels?.some((model) => model.modelId === selectedModel.modelId);
    }, [selectedModel, allModels]);

    // Selected model is in dropdown but stopped (session resumed with a model that is now stopped)
    const isModelStopped = useMemo(() => {
        if (!selectedModel) return false;
        const inList = modelsForDropdown?.find((m) => m.modelId === selectedModel.modelId);
        return inList?.status === ModelStatus.Stopped;
    }, [selectedModel, modelsForDropdown]);

    // Set default model if none is selected, default model is configured, and user hasn't interacted (only InService models)
    const availableModelsForDefault = useMemo(() =>
        (modelsForDropdown || []).filter((m) => m.status === ModelStatus.InService),
    [modelsForDropdown]
    );
    useEffect(() => {
        if (!selectedModel && !hasUserInteractedWithModel && config?.configuration?.global?.defaultModel && availableModelsForDefault?.length) {
            const defaultModelId = config.configuration.global.defaultModel;
            if (availableModelsForDefault.some((m) => m.modelId === defaultModelId)) {
                handleModelChange(defaultModelId, selectedModel, setSelectedModel);
            }
        }
    }, [selectedModel, hasUserInteractedWithModel, config?.configuration?.global?.defaultModel, availableModelsForDefault, handleModelChange, setSelectedModel]);

    // Apply stack config when starting a new session from a Chat Assistant (after session exists so RAG isn't overwritten by createNewSession)
    const initialStackApplied = useRef(false);
    const [getPromptTemplate] = useLazyGetPromptTemplateQuery();
    useEffect(() => {
        const sessionReady = sessionId != null || internalSessionId != null;
        if (!initialStack || session.history.length > 0 || initialStackApplied.current || !allModels?.length || !sessionReady) return;
        const firstModelId = initialStack.modelIds?.[0];
        const model = firstModelId ? allModels.find((m) => m.modelId === firstModelId) : undefined;
        if (model) {
            handleModelChange(model.modelId, selectedModel, setSelectedModel);
            setModelFilterValue(model.modelId);
        }
        setSession((prev) => ({ ...prev, name: initialStack.name }));
        setChatAssistantId(initialStack.stackId);
        setChatConfiguration((prev) => ({ ...prev, chatAssistantId: initialStack.stackId }));

        // Set system prompt from persona prompt if configured
        if (initialStack.personaPromptId) {
            getPromptTemplate(initialStack.personaPromptId).then((result) => {
                if (result.data?.body) {
                    setChatConfiguration((prev) => ({
                        ...prev,
                        promptConfiguration: {
                            ...prev.promptConfiguration,
                            promptTemplate: result.data.body,
                        },
                    }));
                }
            });
        }

        // Set initial RAG from stack when present; clear RAG when stack has no repos
        const repoIds = initialStack.repositoryIds ?? [];
        if (repoIds.length) {
            setRagConfig((prev) => ({
                ...prev,
                repositoryId: repoIds[0],
            }));
        } else {
            setRagConfig({} as import('./components/RagOptions').RagConfig);
        }

        initialStackApplied.current = true;
    }, [initialStack, session.history.length, sessionId, internalSessionId, allModels, setSession, handleModelChange, setSelectedModel, selectedModel, getPromptTemplate, setChatConfiguration, setRagConfig, setChatAssistantId]);


    // Wrapper for handleModelChange that tracks user interaction
    const handleUserModelChange = (value: string) => {
        setHasUserInteractedWithModel(true);
        setModelFilterValue(value);
        handleModelChange(value, selectedModel, setSelectedModel);
    };

    // Update filter value when selected model changes
    useEffect(() => {
        setModelFilterValue(selectedModel?.modelId ?? '');
    }, [selectedModel]);

    const { memory, metadata } = useMemory(
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

    const { handleButtonClick: baseHandleButtonClick } = useButtonActions({
        openModal,
        refreshPromptTemplate,
        setFilterPromptTemplateType,
    });

    // Extended button click handler that includes markdown preview toggle
    const handleButtonClick = useCallback(({ detail }: { detail: { id: string } }) => {
        if (detail.id === 'toggle-markdown-preview') {
            handleToggleMarkdownPreview(!showMarkdownPreview);
        } else {
            baseHandleButtonClick({ detail });
        }
    }, [baseHandleButtonClick, handleToggleMarkdownPreview, showMarkdownPreview]);

    // Derived states
    const isImageGenerationMode = selectedModel?.modelType === ModelType.imagegen;
    const isVideoGenerationMode = selectedModel?.modelType === ModelType.videogen;

    // Format MCP tools and optional Bedrock agent tools for OpenAI when they change
    const openAiTools = useMemo(() => {
        const ec = config?.configuration?.enabledComponents;
        let formattedMcp: Array<{ type: 'function'; function: Record<string, unknown> }> = [];
        if (ec?.mcpConnections && mcpTools.length > 0) {
            try {
                formattedMcp = mcpTools.map((tool) => {
                    const schema =
                        tool?.inputSchema != null &&
                        typeof tool.inputSchema === 'object' &&
                        !Array.isArray(tool.inputSchema)
                            ? tool.inputSchema
                            : { properties: {} };
                    return {
                        type: 'function' as const,
                        function: {
                            name: tool.name,
                            description: tool.description ?? '',
                            parameters: { ...schema, type: 'object' as const },
                        },
                    };
                });
            } catch (e) {
                console.error('Failed to format MCP tools for the model:', e);
                formattedMcp = [];
            }
        }
        const bedrockFragments = ec?.bedrockAgents ? bedrockOpenAiToolFragments : [];
        const merged = [...formattedMcp, ...bedrockFragments];
        return merged.length > 0 ? merged : undefined;
    }, [mcpTools, bedrockOpenAiToolFragments, config?.configuration?.enabledComponents]);

    const toolToServerMapMerged = useMemo(() => {
        const m = new Map(toolToServerMap);
        m.set('invoke_bedrock_agent', 'Amazon Bedrock Agents');
        bedrockFunctionToolIndex.forEach((_v, key) => m.set(key, 'Amazon Bedrock Agents'));
        return m;
    }, [toolToServerMap, bedrockFunctionToolIndex]);

    const currentSessionId = session?.sessionId;
    const callToolWithBedrock = useCallback(async (toolName: string, args: any) => {
        if (toolName === 'invoke_bedrock_agent') {
            const match = enabledBedrockAgentsForChat.find((a) => a.agentId === args.agentId);
            if (!match) {
                throw new Error('Agent is not enabled. Turn it on under Libraries → Agentic connections → Bedrock agents.');
            }
            const inputText = typeof args.inputText === 'string' ? args.inputText : JSON.stringify(args.inputText ?? '');
            const sessionKey = currentSessionId ? `${currentSessionId}:${args.agentId}` : undefined;
            const res = await invokeBedrockAgent({
                agentId: match.agentId,
                agentAliasId: match.agentAliasId,
                inputText,
                sessionId: sessionKey,
            }).unwrap();
            return res.outputText;
        }
        const spec = bedrockFunctionToolIndex.get(toolName);
        if (spec) {
            const match = enabledBedrockAgentsForChat.find((a) => a.agentId === spec.agentId);
            if (!match) {
                throw new Error('Agent is not enabled. Turn it on under Libraries → Agentic connections → Bedrock agents.');
            }
            const sessionKey = currentSessionId ? `${currentSessionId}:${spec.agentId}` : undefined;
            const res = await invokeBedrockAgent({
                agentId: match.agentId,
                agentAliasId: match.agentAliasId,
                functionName: spec.functionName,
                actionGroupId: spec.actionGroupId,
                actionGroupName: spec.actionGroupName,
                parameters: args && typeof args === 'object' && !Array.isArray(args) ? args : {},
                sessionId: sessionKey,
            }).unwrap();
            return res.outputText;
        }
        return callTool(toolName, args);
    }, [
        callTool,
        invokeBedrockAgent,
        enabledBedrockAgentsForChat,
        currentSessionId,
        bedrockFunctionToolIndex,
    ]);

    const shouldAutoApproveBedrockTool = useCallback((
        toolName: string,
        toolArgs: Record<string, unknown> | undefined,
    ) => {
        if (toolName === 'invoke_bedrock_agent') {
            const id = toolArgs && typeof toolArgs.agentId === 'string' ? toolArgs.agentId : undefined;
            if (!id) return false;
            return Boolean(
                userPreferences?.preferences?.bedrockAgents?.enabledAgents?.find((a) => a.agentId === id)?.autoApproveInvoke,
            );
        }
        const spec = bedrockFunctionToolIndex.get(toolName);
        if (!spec) return false;
        return Boolean(
            userPreferences?.preferences?.bedrockAgents?.enabledAgents?.find((a) => a.agentId === spec.agentId)?.autoApproveInvoke,
        );
    }, [userPreferences?.preferences?.bedrockAgents?.enabledAgents, bedrockFunctionToolIndex]);

    const fetchRelevantDocuments = useCallback(async (query: string) => {
        const { ragTopK = 3 } = chatConfiguration.sessionConfiguration;

        return getRelevantDocuments({
            query,
            repositoryId: ragConfig.repositoryId,
            collectionId: ragConfig.collection?.collectionId,
            topK: ragTopK,
            modelName: !ragConfig.collection?.collectionId ? ragConfig.embeddingModel?.modelId : undefined,
        });
    }, [getRelevantDocuments, chatConfiguration.sessionConfiguration, ragConfig.repositoryId, ragConfig.collection, ragConfig.embeddingModel]);

    const { isRunning, setIsRunning, isStreaming, generateResponse, stopGeneration, retryResponse, errorState } = useChatGeneration({
        chatConfiguration,
        selectedModel,
        isImageGenerationMode,
        isVideoGenerationMode,
        session,
        setSession,
        metadata,
        memory,
        openAiTools: (config?.configuration?.enabledComponents?.mcpConnections
            || config?.configuration?.enabledComponents?.bedrockAgents)
            ? openAiTools
            : undefined,
        auth,
        fileContext,
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
        callTool: callToolWithBedrock,
        generateResponse,
        session,
        setSession,
        notificationService,
        toolToServerMap: toolToServerMapMerged,
        mcpPreferences: userPreferences?.preferences?.mcp,
        shouldAutoApproveBedrockTool,
        bedrockOverrideAllApprovals: Boolean(userPreferences?.preferences?.bedrockAgents?.overrideAllBedrockApprovals),
        isBedrockManagedTool,
    });

    // Store the startToolChain function in a ref to avoid useEffect dependency issues
    useEffect(() => {
        startToolChainRef.current = startToolChain;
    }, [startToolChain]);

    const bedrockAgentIdForApprovalModal = useMemo(() => {
        if (!toolApprovalModal?.tool || !isBedrockManagedTool(toolApprovalModal.tool.name)) {
            return undefined;
        }
        const t = toolApprovalModal.tool;
        if (t.name === 'invoke_bedrock_agent' && typeof t.args?.agentId === 'string') {
            return t.args.agentId;
        }
        return bedrockFunctionToolIndex.get(t.name)?.agentId;
    }, [toolApprovalModal, isBedrockManagedTool, bedrockFunctionToolIndex]);

    const toggleToolAutoApproval = (toolName: string, enabled: boolean, toolArgs?: Record<string, unknown>) => {
        if (isBedrockManagedTool(toolName)) {
            let agentId: string | undefined;
            if (toolName === 'invoke_bedrock_agent') {
                agentId = toolArgs && typeof toolArgs.agentId === 'string' ? toolArgs.agentId : undefined;
            } else {
                agentId = bedrockFunctionToolIndex.get(toolName)?.agentId;
            }
            if (!agentId) {
                setUpdatingAutoApprovalForTool(null);
                return;
            }
            setUpdatingAutoApprovalForTool(toolName);
            const cur = preferences.preferences.bedrockAgents?.enabledAgents ?? [];
            const nextAgents = cur.map((a) =>
                (a.agentId === agentId ? { ...a, autoApproveInvoke: enabled } : a));
            const updated = {
                ...preferences,
                preferences: {
                    ...preferences.preferences,
                    bedrockAgents: {
                        enabledAgents: nextAgents,
                        overrideAllBedrockApprovals:
                            preferences.preferences.bedrockAgents?.overrideAllBedrockApprovals ?? false,
                    },
                },
            };
            setPreferences(updated);
            updatePreferences(updated);
            return;
        }
        setUpdatingAutoApprovalForTool(toolName);
        const existingMcpPrefs = preferences.preferences.mcp ?? { enabledServers: [], overrideAllApprovals: false };
        const mcpPrefs: McpPreferences = {
            ...existingMcpPrefs,
            enabledServers: [...existingMcpPrefs.enabledServers]
        };
        const originalServer = mcpPrefs.enabledServers.find((server) => server.name === toolToServerMap.get(toolName));
        if (!originalServer) {
            setUpdatingAutoApprovalForTool(null);
            return; // Early return if server not found
        }
        // Create a deep copy of the server object with its nested arrays
        const serverToUpdate = {
            ...originalServer,
            autoApprovedTools: [...(originalServer.autoApprovedTools ?? [])],
        };

        if (enabled) {
            serverToUpdate.autoApprovedTools.push(toolName);
        } else {
            serverToUpdate.autoApprovedTools = serverToUpdate.autoApprovedTools.filter((item) => item !== toolName);
        }
        mcpPrefs.enabledServers = [
            ...mcpPrefs.enabledServers.filter((server) => server.name !== serverToUpdate.name),
            serverToUpdate
        ];
        updatePrefs(mcpPrefs);
    };

    const updatePrefs = (mcpPrefs: McpPreferences) => {
        const updated = {
            ...preferences,
            preferences: {
                ...preferences.preferences,
                mcp: {
                    ...preferences.preferences.mcp,
                    ...mcpPrefs
                }
            }
        };
        setPreferences(updated);
        updatePreferences(updated);
    };

    // Handle stop functionality
    const handleStop = useCallback(() => {
        stopToolChain();
        stopGeneration();
        setIsRunning(false);
        notificationService.generateNotification('Stopping processing...', 'info');
    }, [stopToolChain, stopGeneration, setIsRunning, notificationService]);

    // Determine if we should show stop button
    const shouldShowStopButton = Boolean(isRunning || callingToolName);

    useEffect(() => {
        if (sessionHealth) {
            setIsConnected(true);
        }

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
                                (Array.isArray(message.content) ? message.content : []).map(async (content: { type?: string; image_url?: { url?: string; s3_key?: string } }) => {
                                    if (content.type === 'image_url') {
                                        const resp = await attachImageToSession({
                                            sessionId: session.sessionId,
                                            message: content
                                        });
                                        if ('data' in resp) {
                                            const image: LisaAttachImageResponse = resp.data;
                                            if (content.image_url && image.body.image_url) {
                                                content.image_url.url = image.body.image_url.url;
                                                if ('s3_key' in image.body.image_url) {
                                                    content.image_url.s3_key = image.body.image_url.s3_key;
                                                }
                                            }
                                        }
                                    }
                                })
                            );
                        }
                        const updatedHistory = [...session.history.slice(0, -1), message];

                        const assistantId = chatAssistantId || effectiveStack?.stackId;
                        updateSession({
                            ...session,
                            history: updatedHistory,
                            configuration: {
                                ...chatConfiguration,
                                selectedModel: selectedModel,
                                ragConfig: ragConfig,
                                ...(assistantId ? { chatAssistantId: assistantId } : {}),
                            },
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
    }, [isRunning, session.history.length, dirtySession, chatConfiguration, chatAssistantId, effectiveStack?.stackId]);

    // Connection health check
    useEffect(() => {
        if (sessionHealth) {
            setIsConnected(true);
        }
    }, [sessionHealth]);

    // When session finishes loading, enable auto-scroll and scroll to bottom
    useEffect(() => {
        if (!loadingSession && session.history.length > 0 && sessionId) {
            // Re-enable auto-scroll when a session is loaded
            setShouldAutoScroll(true);

            // For sessions with images, we need multiple scroll attempts because:
            // - Base64 images load instantly (synchronously)
            // - Cached images load very quickly
            // - The browser needs time to reflow the layout with image dimensions
            const scrollToBottom = () => {
                if (scrollContainerRef.current) {
                    scrollContainerRef.current.scrollTop = scrollContainerRef.current.scrollHeight;
                }
            };

            // Multiple scroll attempts with increasing delays to ensure we reach the bottom
            // as images fully load and the container height updates
            const delays = [0, 50, 150, 300, 500];
            const timeoutIds = delays.map((delay) => setTimeout(scrollToBottom, delay));

            // Cleanup timeouts if component unmounts or effect re-runs
            return () => {
                timeoutIds.forEach((id) => clearTimeout(id));
            };
        }
    }, [loadingSession, sessionId, session.history.length]);

    useEffect(() => {
        if (shouldAutoScroll && scrollContainerRef.current) {
            // Scroll the container directly to the bottom
            // This is more reliable than scrollIntoView for ensuring we reach the actual bottom
            const container = scrollContainerRef.current;
            container.scrollTop = container.scrollHeight;
        }
    }, [isStreaming, session, mermaidRenderComplete, videoLoadComplete, imageLoadComplete, shouldAutoScroll]);

    // Scroll event listener to detect scroll position
    useEffect(() => {
        const scrollContainer = scrollContainerRef.current;
        if (!scrollContainer) return;

        const handleScroll = () => {
            // Check if we're at the bottom
            const { scrollTop, scrollHeight, clientHeight } = scrollContainer;
            const distanceFromBottom = scrollHeight - scrollTop - clientHeight;

            // Small threshold to account for rounding issues
            const AT_BOTTOM_THRESHOLD = 30;

            if (distanceFromBottom <= AT_BOTTOM_THRESHOLD) {
                // At bottom - ensure auto-scroll is enabled
                if (!shouldAutoScroll) {
                    setShouldAutoScroll(true);
                }
            } else {
                // Not at bottom - disable auto-scroll
                if (shouldAutoScroll) {
                    setShouldAutoScroll(false);
                }
            }
        };

        scrollContainer.addEventListener('scroll', handleScroll);
        return () => scrollContainer.removeEventListener('scroll', handleScroll);
    }, [shouldAutoScroll]);

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

        // Re-enable auto-scroll when user sends a new message
        setShouldAutoScroll(true);

        // When using an assistant, set session name to "{assistant name} - {first user prompt}" on first message
        const isFirstMessage = session.history.length === 0;
        setSession((prev) => ({
            ...prev,
            ...(effectiveStack && isFirstMessage ? { name: `${effectiveStack.name} - ${userPrompt}` } : {}),
            history: prev.history.concat(new LisaChatMessage({
                type: 'human',
                content: userPrompt,
                metadata: isImageGenerationMode ? { imageGeneration: true } : isVideoGenerationMode ? { videoGeneration: true } : {},
            }))
        }));

        const messages = [];

        if (session.history.length === 0 && !isImageGenerationMode && !isVideoGenerationMode) {
            messages.push(new LisaChatMessage({
                type: 'system',
                content: chatConfiguration.promptConfiguration.promptTemplate,
                metadata: {},
            }));
        }

        // Fetch RAG documents once if needed
        let ragDocs = null;
        if (useRag && !isImageGenerationMode && !isVideoGenerationMode) {
            ragDocs = await fetchRelevantDocuments(userPrompt);
        }

        // Use extracted message builder utilities
        const messageContent = await buildMessageContent({
            isImageGenerationMode: isImageGenerationMode || isVideoGenerationMode,
            fileContext,
            useRag,
            userPrompt,
            ragDocs,
        });

        const messageMetadata = await buildMessageMetadata({
            isImageGenerationMode: isImageGenerationMode || isVideoGenerationMode,
            useRag,
            chatConfiguration,
            ragDocs,
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
    }, [userPrompt, useRag, fileContext, chatConfiguration, generateResponse, isImageGenerationMode, isVideoGenerationMode, fetchRelevantDocuments, notificationService]);

    // Ref to track if we're processing a keyboard event
    const isKeyboardEventRef = useRef(false);

    // Custom action handler that only allows stop on button clicks
    const handleAction = useCallback(() => {
        // If this is a keyboard event, don't process it here (it's handled in handleKeyPress)
        if (isKeyboardEventRef.current) {
            return;
        }

        if (shouldShowStopButton) {
            // Only allow stop action on button clicks (not keyboard events)
            handleStop();
        } else {
            // Normal send functionality - allow both button clicks and Enter key
            if (userPrompt.length > 0 && !isRunning && !callingToolName && !loadingSession) {
                handleSendGenerateRequest();
            }
        }
    }, [shouldShowStopButton, handleStop, userPrompt.length, isRunning, callingToolName, loadingSession, handleSendGenerateRequest]);

    // Handle Enter key press
    const handleKeyPress = useCallback((event: any) => {
        if (event.detail.key === 'Enter' && !event.detail.shiftKey) {
            event.preventDefault();
            isKeyboardEventRef.current = true;

            // Handle the action directly for keyboard events
            if (shouldShowStopButton) {
                // Do nothing for stop button when Enter is pressed
            } else {
                // Normal send functionality for Enter key
                if (userPrompt.length > 0 && !isRunning && !callingToolName && !loadingSession) {
                    handleSendGenerateRequest();
                }
            }

            // Reset the flag after a short delay
            setTimeout(() => {
                isKeyboardEventRef.current = false;
            }, 100);
        }
    }, [shouldShowStopButton, userPrompt.length, isRunning, callingToolName, loadingSession, handleSendGenerateRequest]);

    const getButtonItemsWithAssistantMode = useCallback((...args: Parameters<typeof getButtonItems>) => {
        const [config, useRag, isImageGen, isVideoGen, isConnected, isModelDel, showMd] = args;
        return getButtonItems(config, useRag, isImageGen, isVideoGen, isConnected, isModelDel, showMd, !!effectiveStack, !!selectedModel, loadingSession);
    }, [effectiveStack, selectedModel, loadingSession]);

    const promptInputProps = useMemo(() => ({
        userPrompt,
        shouldShowStopButton,
        dynamicMaxRows,
        isModelDeleted,
        isConnected,
        selectedModel,
        loadingSession,
        isImageGenerationMode,
        isVideoGenerationMode,
        fileContext,
        fileContextName,
        fileContextFiles,
        config,
        useRag,
        showMarkdownPreview,
        setUserPrompt,
        setFileContext,
        setFileContextName,
        setFileContextFiles,
        handleAction,
        handleKeyPress,
        handleButtonClick,
        getButtonItems: getButtonItemsWithAssistantMode,
    }), [
        userPrompt,
        shouldShowStopButton,
        dynamicMaxRows,
        isModelDeleted,
        isConnected,
        selectedModel,
        loadingSession,
        isImageGenerationMode,
        isVideoGenerationMode,
        fileContext,
        fileContextName,
        fileContextFiles,
        config,
        useRag,
        showMarkdownPreview,
        handleAction,
        handleKeyPress,
        handleButtonClick,
        getButtonItemsWithAssistantMode,
    ]);

    return (
        <div className='flex flex-col h-[85vh]'>
            {/* Agentic connections (MCP) — invisible components that manage server connections */}
            {McpConnections}
            {useMemo(() => (<DocumentSummarizationModal
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

            />), [modals.documentSummarization, openModal, closeModal, fileContext, setFileContext, setUserPrompt, userPrompt, selectedModel, setSelectedModel, chatConfiguration, setChatConfiguration, auth.user?.profile.sub, setInternalSessionId, setSession, handleSendGenerateRequest]) }

            {useMemo(() => (<SessionConfiguration
                chatConfiguration={chatConfiguration}
                setChatConfiguration={setChatConfiguration}
                selectedModel={selectedModel}
                isRunning={isRunning}
                visible={modals.sessionConfiguration}
                setVisible={(show) => show ? openModal('sessionConfiguration') : closeModal('sessionConfiguration')}
                systemConfig={config}
                session={session}
                updateSession={updateSession}
                ragConfig={ragConfig}

            />), [modals.sessionConfiguration, chatConfiguration, setChatConfiguration, selectedModel, isRunning, openModal, closeModal, config, session, updateSession, ragConfig])}
            {useMemo(() => (window.env.RAG_ENABLED ? <RagUploadModal
                ragConfig={ragConfig}
                showRagUploadModal={modals.ragUpload}
                setShowRagUploadModal={(show) => show ? openModal('ragUpload') : closeModal('ragUpload')}
            /> : null), [ragConfig, modals.ragUpload, openModal, closeModal])}

            {useMemo(() => (<ContextUploadModal
                showContextUploadModal={modals.contextUpload}
                setShowContextUploadModal={(show) => show ? openModal('contextUpload') : closeModal('contextUpload')}
                fileContext={fileContext}
                setFileContext={setFileContext}
                setFileContextName={setFileContextName}
                setFileContextFiles={setFileContextFiles}
                selectedModel={selectedModel}

            />), [modals.contextUpload, openModal, closeModal, fileContext, setFileContext, setFileContextName, setFileContextFiles, selectedModel])}
            {useMemo(() => (<PromptTemplateModal
                session={session}
                showModal={modals.promptTemplate}
                setShowModal={(show) => show ? openModal('promptTemplate') : closeModal('promptTemplate')}
                setUserPrompt={setUserPrompt}
                chatConfiguration={chatConfiguration}
                setChatConfiguration={setChatConfiguration}
                key={promptTemplateKey}
                config={config}
                type={filterPromptTemplateType}
                allowedDirectivePromptIds={effectiveStack ? (effectiveStack.directivePromptIds ?? []) : undefined}
                // eslint-disable-next-line react-hooks/exhaustive-deps
            />), [modals.promptTemplate, session, openModal, closeModal, chatConfiguration, setChatConfiguration, promptTemplateKey, config, filterPromptTemplateType, effectiveStack?.directivePromptIds])}
            {/* Tool Approval Modal */}
            {toolApprovalModal && (
                <ConfirmationModal
                    action='Execute'
                    title={isBedrockManagedTool(toolApprovalModal.tool.name) ? 'Confirm Bedrock agent invocation' : 'Confirm MCP Tool Execution'}
                    onConfirm={handleToolApproval}
                    onDismiss={handleToolRejection}
                    description={
                        <SpaceBetween size='xs' direction='vertical'>
                            <SpaceBetween size='xs' direction='vertical'>
                                <div><strong>Source:</strong> {toolToServerMapMerged.get(toolApprovalModal.tool.name) ?? toolApprovalModal.tool.name}</div>
                                <div><strong>Tool:</strong> {toolApprovalModal.tool.name}</div>
                                <div><strong>Details:</strong></div>
                                {JSON.stringify(toolApprovalModal.tool.args).replace('{', '').replace('}', '')}
                            </SpaceBetween>
                            <hr />
                            {updatingAutoApprovalForTool === toolApprovalModal.tool.name ? (
                                <Box>
                                    <Spinner size='normal' /> Updating preferences...
                                </Box>
                            ) : (
                                <Checkbox
                                    onChange={({ detail }) =>
                                        toggleToolAutoApproval(
                                            toolApprovalModal.tool.name,
                                            detail.checked,
                                            toolApprovalModal.tool.args,
                                        )
                                    }
                                    checked={
                                        isBedrockManagedTool(toolApprovalModal.tool.name)
                                            ? Boolean(
                                                bedrockAgentIdForApprovalModal
                                                && preferences?.preferences?.bedrockAgents?.enabledAgents?.find(
                                                    (a) => a.agentId === bedrockAgentIdForApprovalModal,
                                                )?.autoApproveInvoke,
                                            )
                                            : Boolean(preferences?.preferences?.mcp?.enabledServers.find((server) => server.name === toolToServerMap.get(toolApprovalModal.tool.name))?.autoApprovedTools?.includes(toolApprovalModal.tool.name))
                                    }
                                    disabled={isUpdatingPreferences}
                                >
                                    {isBedrockManagedTool(toolApprovalModal.tool.name)
                                        ? 'Auto-approve invocations for this agent in the future'
                                        : 'Auto-approve this tool in the future'}
                                </Checkbox>
                            )}
                        </SpaceBetween>
                    }
                />
            )}

            {/* Sticky warning banner for deleted or stopped model */}
            {isModelDeleted && (
                <div className='sticky top-0 z-50'>
                    <Box padding={{ horizontal: 'l', top: 's' }}>
                        <Flashbar
                            items={[
                                {
                                    type: 'warning',
                                    dismissible: false,
                                    content: isModelStopped ? (
                                        <>
                                            This session uses the model <strong>{selectedModel?.modelId}</strong> which is stopped.
                                            Start it from Model management or start a new session with a different model.
                                            You can view the conversation history but cannot send new messages until the model is started.
                                        </>
                                    ) : (
                                        <>
                                            This session uses the model <strong>{selectedModel?.modelId}</strong> which is no longer available.
                                            You can view the conversation history but cannot send new messages.
                                            Please start a new session with a different model.
                                        </>
                                    ),
                                    id: 'model-deleted-warning',
                                },
                            ]}
                        />
                    </Box>
                </div>
            )}

            {effectiveStack && (
                <Box padding={{ horizontal: 'l', vertical: 's' }} variant='div'>
                    <SpaceBetween direction='horizontal' size='s' alignItems='center'>
                        <StatusIndicator type='info'>Chat Assistant</StatusIndicator>
                        <Box variant='strong'>{effectiveStack.name}</Box>
                        {effectiveStack.description && (
                            <Box
                                variant='p'
                                color='text-body-secondary'
                            >
                                - {effectiveStack.description}
                            </Box>
                        )}
                    </SpaceBetween>
                </Box>
            )}

            {/* Split layout container */}
            <div style={{
                display: 'grid',
                gridTemplateColumns: showDocSidePanel ? '1fr 1fr' : '1fr',
                gap: '0',
                height: 'calc(100vh - 21rem)',
                overflow: 'hidden'
            }}>
                {/* Chat messages area */}
                <div ref={scrollContainerRef} className='overflow-y-auto bottom-8'>
                    <SpaceBetween direction='vertical' size='l'>

                        {loadingSession && (
                            <Box textAlign='center' padding='l'>
                                <SpaceBetween size='s' direction='vertical'>
                                    <Spinner size='large' />
                                    <Box color='text-status-info'>Loading session...</Box>
                                    <Box variant='small' color='text-status-inactive'>Please wait while we load your conversation history</Box>
                                </SpaceBetween>
                            </Box>
                        )}

                        {useMemo(() => {
                            if (loadingSession) return null;

                            return session.history.map((message, idx) => (<Message
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
                                onMermaidRenderComplete={handleMermaidRenderComplete}
                                onVideoLoadComplete={handleVideoLoadComplete}
                                onImageLoadComplete={handleImageLoadComplete}
                                retryResponse={retryResponse}
                                errorState={errorState && idx === session.history.length - 1 }
                                onOpenDocument={handleOpenDocument}
                            />));
                            // eslint-disable-next-line react-hooks/exhaustive-deps
                        }, [session.history, chatConfiguration, loadingSession])}

                        {!loadingSession && (isRunning || callingToolName) && !isStreaming && !isImageGenerationMode && !isVideoGenerationMode && <Message
                            isRunning={isRunning}
                            callingToolName={callingToolName}
                            markdownDisplay={chatConfiguration.sessionConfiguration.markdownDisplay}
                            message={new LisaChatMessage({ type: 'ai', content: '' })}
                            setChatConfiguration={setChatConfiguration}
                            handleSendGenerateRequest={handleSendGenerateRequest}
                            chatConfiguration={chatConfiguration}
                            setUserPrompt={setUserPrompt}
                            onMermaidRenderComplete={handleMermaidRenderComplete}
                            onVideoLoadComplete={handleVideoLoadComplete}
                            onImageLoadComplete={handleImageLoadComplete}
                            onOpenDocument={handleOpenDocument}
                        />}
                        {!loadingSession && session.history.length === 0 && sessionId === undefined && !effectiveStack && (
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

                {/* Document side panel */}
                {showDocSidePanel && (
                    <DocumentSidePanel
                        visible={showDocSidePanel}
                        onClose={handleCloseDocPanel}
                        document={selectedDocumentForPanel}
                    />
                )}
            </div>

            <div className='sticky mt-2'>
                <form onSubmit={(e) => e.preventDefault()}>
                    <Form>
                        <SpaceBetween size='xs' direction='vertical'>
                            <Grid
                                gridDefinition={[
                                    { colspan: { default: 4 } },
                                    { colspan: { default: 8 } },
                                ]}
                            >
                                <FormField
                                    label={isImageGenerationMode || isVideoGenerationMode ? <StatusIndicator type='info'>{isImageGenerationMode ? 'Image Generation Mode' : 'Video Generation Mode'}</StatusIndicator> : undefined}
                                >
                                    <SpaceBetween size='xs' direction='vertical'>
                                        <Autosuggest
                                            data-testid='model-selection-autosuggest'
                                            disabled={isRunning || session.history.length > 0}
                                            statusType={isFetchingModels ? 'loading' : 'finished'}
                                            loadingText='Loading models (might take few seconds)...'
                                            placeholder='Select a model'
                                            empty={<div className='text-zinc-500'>No models available.</div>}
                                            filteringType='auto'
                                            value={modelFilterValue}
                                            enteredTextLabel={(text) => `Use: "${text}"`}
                                            onChange={({ detail: { value } }) => handleUserModelChange(value)}
                                            options={modelsOptions}
                                            ref={modelSelectRef}
                                            controlId='model-selection-autosuggest'
                                        />
                                    </SpaceBetween>
                                </FormField>
                                {window.env.RAG_ENABLED && !isImageGenerationMode && !isVideoGenerationMode && (
                                    <RagControls
                                        isRunning={isRunning}
                                        setUseRag={setUseRag}
                                        setRagConfig={setRagConfig}
                                        ragConfig={ragConfig}
                                        selectionAvailable={ragSelectionAvailable}
                                        allowedRepositoryIds={effectiveStack ? (effectiveStack.repositoryIds ?? []) : undefined}
                                        allowedCollectionIds={effectiveStack ? (effectiveStack.collectionIds ?? []) : undefined}
                                    />
                                )}
                            </Grid>
                            {showMarkdownPreview ? (
                                <div style={{ overflow: 'hidden' }}>
                                    <Grid gridDefinition={[{ colspan: 6 }, { colspan: 6 }]}>
                                        <ChatPromptInput {...promptInputProps} />
                                        <PromptPreview content={userPrompt} isDarkMode={isDarkMode} />
                                    </Grid>
                                </div>
                            ) : (
                                <ChatPromptInput {...promptInputProps} />
                            )}
                            <SpaceBetween direction='vertical' size='xs'>
                                <Grid gridDefinition={[{ colspan: 4 }, { colspan: 4 }, { colspan: 4 }]}>
                                    {selectedModel?.features?.filter((feature) => feature.name === ModelFeatures.TOOL_CALLS)?.length && true
                                        && ((enabledServers && enabledServers.length > 0) || enabledBedrockAgentsForChat.length > 0) ? (
                                            <Box>
                                                <Icon name='gen-ai' variant='success' />{' '}
                                                {enabledServers && enabledServers.length > 0 ? (
                                                    <>{readyMcpServerCount} MCP {readyMcpServerCount === 1 ? 'Server' : 'Servers'} - {mcpTools.length} {mcpTools.length === 1 ? 'tool' : 'tools'}</>
                                                ) : null}
                                                {enabledServers && enabledServers.length > 0 && enabledBedrockAgentsForChat.length > 0 ? ', ' : ''}
                                                {enabledBedrockAgentsForChat.length > 0 ? (
                                                    <>{enabledBedrockAgentsForChat.length} Bedrock {enabledBedrockAgentsForChat.length === 1 ? 'agent' : 'agents'} - {bedrockOpenAiToolFragments.length} {bedrockOpenAiToolFragments.length === 1 ? 'tool' : 'tools'}</>
                                                ) : null}
                                            </Box>
                                        )
                                        : !selectedModel || ((!enabledServers || enabledServers.length === 0) && enabledBedrockAgentsForChat.length === 0) ? (<div></div>)
                                            : (<Box>
                                                <Icon name='gen-ai' variant='disabled' /> This model does not have Tool Calling enabled
                                            </Box>)}
                                    <Box textAlign='center'>
                                        {(() => {
                                            // Look up contextWindow from the model list
                                            const contextWindow = allModelsRaw?.find(
                                                (m) => m.modelId === selectedModel?.modelId
                                            )?.contextWindow;

                                            if (!contextWindow || session.history.length === 0) return null;
                                            // Sum live in-memory tokens for immediate UI updates after
                                            // each response. Fall back to the DDB value on reload.
                                            // Coerce to Number() because DDB Decimal values deserialize
                                            // as strings, which cause string concatenation bugs.
                                            const liveTokens = session.history.reduce((sum, msg) => {
                                                const u = (msg as any).usage;
                                                return sum + (Number(u?.completionTokens) || 0) + (Number(u?.promptTokens) || 0);
                                            }, 0);

                                            const usedTokens = liveTokens > 0
                                                ? liveTokens
                                                : (currentSessionSummary?.totalTokensUsed ?? 0);
                                            if (!usedTokens) return null;

                                            return (
                                                `${formatContextWindow(usedTokens)} - Tokens Used`
                                            );
                                        })()}
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

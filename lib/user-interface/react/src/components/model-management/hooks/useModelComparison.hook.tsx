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

import { useState, useCallback, useMemo, useRef } from 'react';
import { useAuth } from 'react-oidc-context';
import { ChatOpenAI } from '@langchain/openai';
import { SelectProps } from '@cloudscape-design/components';
import { IModel, ModelStatus } from '../../../shared/model/model-management.model';
import { RESTAPI_URI, RESTAPI_VERSION } from '../../utils';
import { useAppDispatch } from '../../../config/store';
import { useNotificationService } from '../../../shared/util/hooks';
import { MODEL_COMPARISON_CONFIG, MESSAGES } from '../config/modelComparison.config';
import { IChatConfiguration } from '../../../shared/model/chat.configurations.model';

export type ComparisonResponse = {
    modelId: string;
    response: string;
    loading: boolean;
    streaming: boolean;
    error?: string;
};

export type ModelSelection = {
    id: string;
    selectedModel: SelectProps.Option | null;
};

export const useModelComparison = (models: IModel[], chatConfig: IChatConfiguration) => {
    const dispatch = useAppDispatch();
    const auth = useAuth();
    const notificationService = useNotificationService(dispatch);

    const [modelSelections, setModelSelections] = useState<ModelSelection[]>([
        { id: '1', selectedModel: null },
        { id: '2', selectedModel: null }
    ]);
    const [prompt, setPrompt] = useState<string>('');
    const [responses, setResponses] = useState<ComparisonResponse[]>([]);
    const [isComparing, setIsComparing] = useState<boolean>(false);
    const stopRequested = useRef(false);

    // Filter models to only show InService text generation models - memoized for performance
    const availableModels = useMemo(() =>
        models
            .filter((model) =>
                model.status === ModelStatus.InService &&
                model.modelType === 'textgen'
            )
            .map((model) => ({
                label: model.modelName,
                value: model.modelId,
                description: model.modelId
            })),
    [models]
    );

    const createOpenAiClient = useCallback((modelId: string, streaming: boolean = false) => {
        const model = models.find((m) => m.modelId === modelId);
        if (!model) return null;

        const sessionConfig = chatConfig.sessionConfiguration;
        const modelArgs = sessionConfig.modelArgs;

        const modelConfig = {
            modelName: model.modelId,
            openAIApiKey: auth.user?.id_token,
            maxRetries: 0,
            configuration: {
                baseURL: `${RESTAPI_URI}/${RESTAPI_VERSION}/serve`,
            },
            streaming,
            maxTokens: sessionConfig.max_tokens || MODEL_COMPARISON_CONFIG.DEFAULT_MAX_TOKENS,
            temperature: modelArgs.temperature,
            topP: modelArgs.top_p,
            frequencyPenalty: modelArgs.frequency_penalty,
            presencePenalty: modelArgs.presence_penalty,
            n: modelArgs.n,
            seed: modelArgs.seed,
            stop: modelArgs.stop,
        };

        return new ChatOpenAI(modelConfig);
    }, [models, auth, chatConfig]);

    const generateModelResponse = async (
        modelId: string, 
        userPrompt: string, 
        updateCallback: (modelId: string, update: Partial<ComparisonResponse>) => void
    ): Promise<void> => {
        const useStreaming = chatConfig.sessionConfiguration.streaming || false;
        const llmClient = createOpenAiClient(modelId, useStreaming);
        
        if (!llmClient) {
            throw new Error(`Failed to create client for model ${modelId}`);
        }

        // Create messages similar to Chat.tsx
        const systemMessage = chatConfig.promptConfiguration.promptTemplate || MODEL_COMPARISON_CONFIG.DEFAULT_SYSTEM_MESSAGE;
        const messages = [
            {
                role: 'system',
                content: systemMessage
            },
            {
                role: 'user',
                content: userPrompt
            }
        ];

        try {
            if (useStreaming) {
                // Set streaming state
                updateCallback(modelId, { streaming: true });
                
                const stream = await llmClient.stream(messages);
                const responseChunks: string[] = [];

                for await (const chunk of stream) {
                    // Check if stop was requested
                    if (stopRequested.current) {
                        updateCallback(modelId, {
                            response: responseChunks.join(''),
                            loading: false,
                            streaming: false
                        });
                        return;
                    }

                    const content = chunk.content as string;
                    responseChunks.push(content);
                    
                    // Update response with accumulated content
                    updateCallback(modelId, {
                        response: responseChunks.join(''),
                        streaming: true
                    });
                }

                // Finalize streaming
                updateCallback(modelId, {
                    response: responseChunks.join(''),
                    loading: false,
                    streaming: false
                });
            } else {
                // Check if stop was requested before non-streaming call
                if (stopRequested.current) {
                    updateCallback(modelId, {
                        response: '',
                        loading: false,
                        streaming: false
                    });
                    return;
                }

                // Non-streaming response
                const response = await llmClient.invoke(messages);
                updateCallback(modelId, {
                    response: response.content as string,
                    loading: false,
                    streaming: false
                });
            }
        } catch (error) {
            console.error(`Error generating response for model ${modelId}:`, error);
            throw new Error(`Failed to generate response: ${error.message || 'Unknown error'}`);
        }
    };

    const addModelComparison = useCallback(() => {
        setModelSelections((prev) => {
            if (prev.length < MODEL_COMPARISON_CONFIG.MAX_MODELS) {
                const newId = (prev.length + 1).toString();
                return [...prev, { id: newId, selectedModel: null }];
            }
            return prev;
        });
    }, []);

    const removeModelComparison = useCallback((idToRemove: string) => {
        setModelSelections((prev) => {
            if (prev.length > MODEL_COMPARISON_CONFIG.MIN_MODELS) {
                return prev.filter((selection) => selection.id !== idToRemove);
            }
            return prev;
        });
    }, []);

    const updateModelSelection = useCallback((id: string, selectedModel: SelectProps.Option | null) => {
        setModelSelections((prev) =>
            prev.map((selection) =>
                selection.id === id ? { ...selection, selectedModel } : selection
            )
        );
    }, []);

    // Get available models for a specific dropdown, excluding already selected models - memoized
    const getAvailableModelsForSelection = useCallback((currentSelectionId: string) => {
        const selectedModelIds = modelSelections
            .filter((selection) => selection.id !== currentSelectionId && selection.selectedModel)
            .map((selection) => selection.selectedModel!.value);

        return availableModels.filter((model) => !selectedModelIds.includes(model.value));
    }, [modelSelections, availableModels]);

    const handleCompare = async () => {
        const selectedModels = modelSelections
            .filter((selection) => selection.selectedModel)
            .map((selection) => selection.selectedModel!);

        if (selectedModels.length < MODEL_COMPARISON_CONFIG.MIN_MODELS) {
            return;
        }

        setIsComparing(true);
        stopRequested.current = false;
        const initialResponses = selectedModels.map((model) => ({
            modelId: model.value!,
            response: '',
            loading: true,
            streaming: false
        }));
        setResponses(initialResponses);

        // Update individual responses as they complete
        const updateResponse = (modelId: string, update: Partial<ComparisonResponse>) => {
            setResponses((prevResponses) =>
                prevResponses.map((response) =>
                    response.modelId === modelId
                        ? { ...response, ...update }
                        : response
                )
            );
        };

        // Make API calls to all selected models and update each as it completes
        const responsePromises = selectedModels.map(async (model) => {
            try {
                await generateModelResponse(model.value!, prompt, updateResponse);
            } catch (error) {
                updateResponse(model.value!, {
                    response: '',
                    loading: false,
                    streaming: false,
                    error: error.message || MESSAGES.FAILED_TO_GET_RESPONSE
                });
            }
        });

        // Wait for all requests to complete before setting isComparing to false
        try {
            await Promise.all(responsePromises);
        } catch (error) {
            console.error('Error in model comparison:', error);
            notificationService.generateNotification(
                MESSAGES.FAILED_TO_COMPARE_MODELS,
                'error',
                undefined,
                error.message ? <p>{error.message}</p> : undefined
            );
        } finally {
            setIsComparing(false);
        }
    };

    const stopComparison = useCallback(() => {
        stopRequested.current = true;
        setIsComparing(false);
        notificationService.generateNotification('Model comparison stopped by user', 'info');
        
        // Update any still-loading responses to stopped state
        setResponses((prevResponses) =>
            prevResponses.map((response) =>
                response.loading || response.streaming
                    ? { ...response, loading: false, streaming: false }
                    : response
            )
        );
    }, [notificationService]);

    const resetComparison = useCallback(() => {
        setModelSelections([
            { id: '1', selectedModel: null },
            { id: '2', selectedModel: null }
        ]);
        setPrompt('');
        setResponses([]);
        setIsComparing(false);
        stopRequested.current = false;
    }, []);

    // Memoize expensive calculations
    const selectedModelsCount = useMemo(() =>
        modelSelections.filter((selection) => selection.selectedModel).length,
    [modelSelections]
    );

    const canCompare = useMemo(() =>
        selectedModelsCount >= MODEL_COMPARISON_CONFIG.MIN_MODELS && !isComparing,
    [selectedModelsCount, isComparing]
    );

    // Determine if we should show stop button - simplified like Chat.tsx
    const shouldShowStopButton = isComparing;

    return {
        // State
        modelSelections,
        prompt,
        responses,
        isComparing,
        availableModels,
        canCompare,
        shouldShowStopButton,

        // Actions
        setPrompt,
        addModelComparison,
        removeModelComparison,
        updateModelSelection,
        getAvailableModelsForSelection,
        handleCompare,
        stopComparison,
        resetComparison
    };
};

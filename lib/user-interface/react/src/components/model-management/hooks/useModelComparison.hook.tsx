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

import { useState, useCallback, useMemo } from 'react';
import { useAuth } from 'react-oidc-context';
import { ChatOpenAI } from '@langchain/openai';
import { SelectProps } from '@cloudscape-design/components';
import { IModel, ModelStatus } from '../../../shared/model/model-management.model';
import { RESTAPI_URI, RESTAPI_VERSION } from '../../utils';
import { useAppDispatch } from '../../../config/store';
import { useNotificationService } from '../../../shared/util/hooks';
import { MODEL_COMPARISON_CONFIG, MESSAGES } from '../config/modelComparison.config';

export interface ComparisonResponse {
    modelId: string;
    response: string;
    loading: boolean;
    error?: string;
}

export interface ModelSelection {
    id: string;
    selectedModel: SelectProps.Option | null;
}

export const useModelComparison = (models: IModel[]) => {
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

    // Filter models to only show InService text generation models - memoized for performance
    const availableModels = useMemo(() =>
        models
            .filter(model =>
                model.status === ModelStatus.InService &&
                model.modelType === 'textgen'
            )
            .map(model => ({
                label: model.modelName,
                value: model.modelId,
                description: model.modelId
            })),
        [models]
    );

    const createOpenAiClient = useCallback((modelId: string) => {
        const model = models.find(m => m.modelId === modelId);
        if (!model) return null;

        const modelConfig = {
            modelName: model.modelId,
            openAIApiKey: auth.user?.id_token,
            maxRetries: 0,
            configuration: {
                baseURL: `${RESTAPI_URI}/${RESTAPI_VERSION}/serve`,
            },
            streaming: false,
            maxTokens: MODEL_COMPARISON_CONFIG.DEFAULT_MAX_TOKENS,
        };

        return new ChatOpenAI(modelConfig);
    }, [models, auth]);

    const generateModelResponse = async (modelId: string, userPrompt: string): Promise<string> => {
        const llmClient = createOpenAiClient(modelId);
        if (!llmClient) {
            throw new Error(`Failed to create client for model ${modelId}`);
        }

        // Create messages similar to Chat.tsx
        const messages = [
            {
                role: 'system',
                content: MODEL_COMPARISON_CONFIG.DEFAULT_SYSTEM_MESSAGE
            },
            {
                role: 'user',
                content: userPrompt
            }
        ];

        try {
            const response = await llmClient.invoke(messages);
            return response.content as string;
        } catch (error) {
            console.error(`Error generating response for model ${modelId}:`, error);
            throw new Error(`Failed to generate response: ${error.message || 'Unknown error'}`);
        }
    };

    const addModelComparison = useCallback(() => {
        setModelSelections(prev => {
            if (prev.length < MODEL_COMPARISON_CONFIG.MAX_MODELS) {
                const newId = (prev.length + 1).toString();
                return [...prev, { id: newId, selectedModel: null }];
            }
            return prev;
        });
    }, []);

    const removeModelComparison = useCallback((idToRemove: string) => {
        setModelSelections(prev => {
            if (prev.length > MODEL_COMPARISON_CONFIG.MIN_MODELS) {
                return prev.filter(selection => selection.id !== idToRemove);
            }
            return prev;
        });
    }, []);

    const updateModelSelection = useCallback((id: string, selectedModel: SelectProps.Option | null) => {
        setModelSelections(prev =>
            prev.map(selection =>
                selection.id === id ? { ...selection, selectedModel } : selection
            )
        );
    }, []);

    // Get available models for a specific dropdown, excluding already selected models - memoized
    const getAvailableModelsForSelection = useCallback((currentSelectionId: string) => {
        const selectedModelIds = modelSelections
            .filter(selection => selection.id !== currentSelectionId && selection.selectedModel)
            .map(selection => selection.selectedModel!.value);

        return availableModels.filter(model => !selectedModelIds.includes(model.value));
    }, [modelSelections, availableModels]);

    const handleCompare = async () => {
        const selectedModels = modelSelections
            .filter(selection => selection.selectedModel)
            .map(selection => selection.selectedModel!);

        if (selectedModels.length < MODEL_COMPARISON_CONFIG.MIN_MODELS) {
            return;
        }

        setIsComparing(true);
        const initialResponses = selectedModels.map(model => ({
            modelId: model.value!,
            response: '',
            loading: true
        }));
        setResponses(initialResponses);

        // Make real API calls to all selected models
        try {
            const responsePromises = selectedModels.map(async (model) => {
                try {
                    const response = await generateModelResponse(model.value!, prompt);
                    return {
                        modelId: model.value!,
                        response,
                        loading: false
                    };
                } catch (error) {
                    return {
                        modelId: model.value!,
                        response: '',
                        loading: false,
                        error: error.message || MESSAGES.FAILED_TO_GET_RESPONSE
                    };
                }
            });

            const modelResponses = await Promise.all(responsePromises);
            setResponses(modelResponses);
        } catch (error) {
            console.error('Error in model comparison:', error);
            notificationService.generateNotification(
                MESSAGES.FAILED_TO_COMPARE_MODELS,
                'error',
                undefined,
                error.message ? <p>{error.message}</p> : undefined
            );

            const errorResponses = selectedModels.map(model => ({
                modelId: model.value!,
                response: '',
                loading: false,
                error: MESSAGES.FAILED_TO_GET_RESPONSE
            }));
            setResponses(errorResponses);
        } finally {
            setIsComparing(false);
        }
    };

    const resetComparison = useCallback(() => {
        setModelSelections([
            { id: '1', selectedModel: null },
            { id: '2', selectedModel: null }
        ]);
        setPrompt('');
        setResponses([]);
        setIsComparing(false);
    }, []);

    // Memoize expensive calculations
    const selectedModelsCount = useMemo(() =>
        modelSelections.filter(selection => selection.selectedModel).length,
        [modelSelections]
    );

    const canCompare = useMemo(() =>
        selectedModelsCount >= MODEL_COMPARISON_CONFIG.MIN_MODELS && !isComparing,
        [selectedModelsCount, isComparing]
    );

    return {
        // State
        modelSelections,
        prompt,
        responses,
        isComparing,
        availableModels,
        canCompare,

        // Actions
        setPrompt,
        addModelComparison,
        removeModelComparison,
        updateModelSelection,
        getAvailableModelsForSelection,
        handleCompare,
        resetComparison
    };
};
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

import { useMemo } from 'react';
import { IModel, ModelType } from '@/shared/model/model-management.model';
import { IChatConfiguration } from '@/shared/model/chat.configurations.model';
import { ModelFeatures } from '@/components/types';

export const useModels = (
    allModels: IModel[] | undefined,
    chatConfiguration: IChatConfiguration,
    setChatConfiguration: (config: IChatConfiguration) => void
) => {
    const modelsOptions = useMemo(() =>
        (allModels || []).map((model) => ({
            label: model.modelId,
            value: model.modelId
        })),
    [allModels]
    );

    const handleModelChange = (value: string, selectedModel: IModel | undefined, setSelectedModel: (model: IModel | undefined) => void) => {
        if (!value || value.length === 0) {
            setSelectedModel(undefined);
        } else {
            const model = allModels?.find((model) => model.modelId === value);
            if (model) {
                // Auto-adjust streaming configuration based on model capabilities
                if (!model.streaming && chatConfiguration.sessionConfiguration.streaming) {
                    setChatConfiguration({
                        ...chatConfiguration,
                        sessionConfiguration: {
                            ...chatConfiguration.sessionConfiguration,
                            streaming: false
                        }
                    });
                } else if (model.streaming && !chatConfiguration.sessionConfiguration.streaming) {
                    setChatConfiguration({
                        ...chatConfiguration,
                        sessionConfiguration: {
                            ...chatConfiguration.sessionConfiguration,
                            streaming: true
                        }
                    });
                }
                if (model.features?.find((feature) => feature.name === ModelFeatures.REASONING) && !chatConfiguration.sessionConfiguration.modelArgs.reasoning_effort) {
                    setChatConfiguration({
                        ...chatConfiguration,
                        sessionConfiguration: {
                            ...chatConfiguration.sessionConfiguration,
                            modelArgs :{
                                ...chatConfiguration.sessionConfiguration.modelArgs,
                                reasoning_effort: 'medium',
                                top_p: 0.95
                            }
                        }
                    });
                } else if (!model.features?.find((feature) => feature.name === ModelFeatures.REASONING) && chatConfiguration.sessionConfiguration.modelArgs.reasoning_effort) {
                    setChatConfiguration({
                        ...chatConfiguration,
                        sessionConfiguration: {
                            ...chatConfiguration.sessionConfiguration,
                            modelArgs: {
                                ...chatConfiguration.sessionConfiguration.modelArgs,
                                reasoning_effort: null,
                                top_p: 0.01
                            }
                        }
                    });
                }

                setSelectedModel(model);
            }
        }
    };

    const isImageGenerationMode = (selectedModel: IModel | undefined) =>
        selectedModel?.modelType === ModelType.imagegen;

    return {
        modelsOptions,
        handleModelChange,
        isImageGenerationMode,
    };
};

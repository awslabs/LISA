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

import { Autosuggest, Grid, SpaceBetween } from '@cloudscape-design/components';
import { useEffect, useMemo, useState, useRef } from 'react';
import { useGetAllModelsQuery } from '@/shared/reducers/model-management.reducer';
import { IModel, ModelStatus, ModelType } from '@/shared/model/model-management.model';
import { useListRagRepositoriesQuery } from '@/shared/reducers/rag.reducer';

export type RagConfig = {
    embeddingModel: IModel;
    repositoryId: string;
    repositoryType: string;
};

type RagControlProps = {
    isRunning: boolean;
    setUseRag: React.Dispatch<React.SetStateAction<boolean>>;
    setRagConfig: React.Dispatch<React.SetStateAction<RagConfig>>;
    ragConfig: RagConfig;
};

export default function RagControls ({isRunning, setUseRag, setRagConfig, ragConfig }: RagControlProps) {
    const { data: repositories, isLoading: isLoadingRepositories } = useListRagRepositoriesQuery(undefined, {
        refetchOnMountOrArgChange: 5
    });
    const { data: allModels, isLoading: isLoadingModels } = useGetAllModelsQuery(undefined, {refetchOnMountOrArgChange: 5,
        selectFromResult: (state) => ({
            isLoading: state.isLoading,
            data: (state.data || []).filter((model) => model.modelType === ModelType.embedding && model.status === ModelStatus.InService),
        })});

    const [userHasSelectedModel, setUserHasSelectedModel] = useState<boolean>(false);

    const lastRepositoryIdRef = useRef<string>(undefined);

    const selectedRepositoryOption = ragConfig?.repositoryId ?? '';
    const selectedEmbeddingOption = ragConfig?.embeddingModel?.modelId ?? '';

    const embeddingOptions = useMemo(() => {
        if (!allModels || !selectedRepositoryOption) return [];

        const repository = repositories?.find((repo) => repo.repositoryId === selectedRepositoryOption);
        const defaultModelId = repository?.embeddingModelId;

        return allModels.map((model) => ({
            value: model.modelId,
            label: model.modelId + (model.modelId === defaultModelId ? ' (default)' : '')
        }));
    }, [allModels, repositories, selectedRepositoryOption]);

    useEffect(() => {
        setUseRag(!!selectedEmbeddingOption && !!selectedRepositoryOption);
    }, [selectedRepositoryOption, selectedEmbeddingOption, setUseRag]);

    // Effect for handling repository changes and auto-selection
    useEffect(() => {
        const currentRepositoryId = ragConfig?.repositoryId;
        const repositoryHasChanged = currentRepositoryId !== lastRepositoryIdRef.current;

        // Update tracking and reset user selection flag when repository changes
        if (repositoryHasChanged) {
            lastRepositoryIdRef.current = currentRepositoryId;
            setUserHasSelectedModel(false);
        }

        // Auto-select default model when repository changes or no model is set
        if (currentRepositoryId && repositories && allModels) {
            const repository = repositories.find((repo) => repo.repositoryId === currentRepositoryId);

            if (repository?.embeddingModelId) {
                const defaultModel = allModels.find((model) => model.modelId === repository.embeddingModelId);

                if (defaultModel) {
                    const shouldAutoSwitch = repositoryHasChanged ||
                        (!ragConfig?.embeddingModel && !userHasSelectedModel);

                    if (shouldAutoSwitch) {
                        setRagConfig((config) => ({
                            ...config,
                            embeddingModel: defaultModel,
                        }));
                    }
                }
            }
        }
    }, [ragConfig?.repositoryId, ragConfig?.embeddingModel, repositories, allModels, userHasSelectedModel, setRagConfig]);

    const handleRepositoryChange = ({ detail }) => {
        const newRepositoryId = detail.value;
        setUserHasSelectedModel(false); // Reset when repository changes

        if (newRepositoryId) {
            const repository = repositories?.find((repo) => repo.repositoryId === newRepositoryId);
            setRagConfig((config) => ({
                ...config,
                repositoryId: newRepositoryId,
                repositoryType: repository?.type || 'unknown',
                embeddingModel: undefined, // Clear current model so useEffect can set default
            }));
        } else {
            setRagConfig((config) => ({
                ...config,
                repositoryId: undefined,
                repositoryType: undefined,
                embeddingModel: undefined,
            }));
        }
    };

    const handleModelChange = ({ detail }) => {
        const newModelId = detail.value;
        setUserHasSelectedModel(true); // Mark that user has made an explicit choice

        if (newModelId) {
            const model = allModels.find((model) => model.modelId === newModelId);
            if (model) {
                setRagConfig((config) => ({
                    ...config,
                    embeddingModel: model,
                }));
            }
        } else {
            setRagConfig((config) => ({
                ...config,
                embeddingModel: undefined,
            }));
        }
    };

    return (
        <SpaceBetween size='l' direction='vertical'>
            <Grid
                gridDefinition={[
                    { colspan: { default: 6 } },
                    { colspan: { default: 6 } },
                ]}
            >
                <Autosuggest
                    disabled={isRunning}
                    statusType={isLoadingRepositories ? 'loading' : 'finished'}
                    loadingText='Loading repositories (might take few seconds)...'
                    placeholder='Select a RAG Repository'
                    empty={<div className='text-gray-500'>No repositories available.</div>}
                    filteringType='auto'
                    value={selectedRepositoryOption}
                    enteredTextLabel={(text) => `Use: "${text}"`}
                    onChange={handleRepositoryChange}
                    options={repositories?.map((repository) => ({
                        value: repository.repositoryId,
                        label: repository?.repositoryName?.length ? repository?.repositoryName : repository.repositoryId
                    })) || []}
                />
                <Autosuggest
                    disabled={!selectedRepositoryOption || isRunning}
                    statusType={isLoadingModels ? 'loading' : 'finished'}
                    loadingText='Loading embedding models (might take few seconds)...'
                    placeholder='Select an embedding model'
                    empty={<div className='text-gray-500'>No embedding models available.</div>}
                    filteringType='auto'
                    value={selectedEmbeddingOption}
                    enteredTextLabel={(text) => `Use: "${text}"`}
                    onChange={handleModelChange}
                    options={embeddingOptions}
                />
            </Grid>
        </SpaceBetween>
    );
}

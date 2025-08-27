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
import { useEffect, useMemo, useState } from 'react';
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
    const { data: repositories, isFetching: isLoadingRepositories } = useListRagRepositoriesQuery(undefined, {refetchOnMountOrArgChange: true});
    const [selectedEmbeddingOption, setSelectedEmbeddingOption] = useState<string>(undefined);
    const [selectedRepositoryOption, setSelectedRepositoryOption] = useState<string>(undefined);
    const { data: allModels, isFetching: isFetchingModels } = useGetAllModelsQuery(undefined, {refetchOnMountOrArgChange: 5,
        selectFromResult: (state) => ({
            isFetching: state.isFetching,
            data: (state.data || []).filter((model) => model.modelType === ModelType.embedding && model.status === ModelStatus.InService),
        })});
    const embeddingOptions = useMemo(() => {
        return allModels?.map((model) => ({value: model.modelId})) || [];
    }, [allModels]);

    useEffect(() => {
        setUseRag(!!selectedEmbeddingOption && !!selectedRepositoryOption);
    // setUseRag is never going to change as it's just a setState function
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [selectedRepositoryOption, selectedEmbeddingOption]);

    // Sync local state with external ragConfig changes and handle defaults
    useEffect(() => {
        // Sync repository selection
        if (ragConfig?.repositoryId !== selectedRepositoryOption) {
            setSelectedRepositoryOption(ragConfig?.repositoryId ?? undefined);
        }

        // Sync embedding model selection
        if (ragConfig?.embeddingModel?.modelId !== selectedEmbeddingOption) {
            setSelectedEmbeddingOption(ragConfig?.embeddingModel?.modelId ?? undefined);
        }

        // Handle default embedding model when repository changes
        if (ragConfig?.repositoryId && !ragConfig?.embeddingModel) {
            const repository = repositories?.find((repo) => repo.repositoryId === ragConfig.repositoryId);
            if (repository?.embeddingModelId) {
                const model = allModels?.find((model) => model.modelId === repository.embeddingModelId);
                if (model) {
                    setRagConfig((config) => ({
                        ...config,
                        embeddingModel: model,
                    }));
                }
            }
        }

        // Handle switching to repository with different default embedding model
        if (ragConfig?.repositoryId) {
            const repository = repositories?.find((repo) => repo.repositoryId === ragConfig.repositoryId);
            if (repository?.embeddingModelId) {
                const defaultModel = allModels?.find((model) => model.modelId === repository.embeddingModelId);
                if (defaultModel && (!ragConfig?.embeddingModel || ragConfig.embeddingModel.modelId !== defaultModel.modelId)) {
                    // Auto-switch to the repository's default embedding model
                    setRagConfig((config) => ({
                        ...config,
                        embeddingModel: defaultModel,
                    }));
                }
            }
        }
    }, [ragConfig?.repositoryId, ragConfig?.embeddingModel, repositories, allModels, selectedEmbeddingOption, selectedRepositoryOption, setRagConfig]);

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
                    value={selectedRepositoryOption ?? ''}
                    enteredTextLabel={(text) => `Use: "${text}"`}
                    onChange={({ detail }) => {
                        const newRepositoryId = detail.value;
                        setSelectedRepositoryOption(newRepositoryId);

                        if (newRepositoryId) {
                            const repository = repositories?.find((repo) => repo.repositoryId === newRepositoryId);
                            setRagConfig((config) => ({
                                ...config,
                                repositoryId: newRepositoryId,
                                repositoryType: repository?.type || 'unknown',
                            }));
                        } else {
                            // Clear repository selection
                            setRagConfig((config) => ({
                                ...config,
                                repositoryId: undefined,
                                repositoryType: undefined,
                                embeddingModel: undefined,
                            }));
                        }
                    }}
                    options={repositories?.map((repository) => ({value: repository.repositoryId, label: repository?.repositoryName?.length ? repository?.repositoryName : repository.repositoryId})) || []}
                />
                <Autosuggest
                    disabled={!selectedRepositoryOption || isRunning}
                    statusType={isFetchingModels ? 'loading' : 'finished'}
                    loadingText='Loading embedding models (might take few seconds)...'
                    placeholder='Select an embedding model'
                    empty={<div className='text-gray-500'>No embedding models available.</div>}
                    filteringType='auto'
                    value={selectedEmbeddingOption ?? ''}
                    enteredTextLabel={(text) => `Use: "${text}"`}
                    onChange={({ detail }) => {
                        const newModelId = detail.value;
                        setSelectedEmbeddingOption(newModelId);

                        if (newModelId) {
                            const model = allModels.find((model) => model.modelId === newModelId);
                            if (model) {
                                setRagConfig((config) => ({
                                    ...config,
                                    embeddingModel: model,
                                }));
                            }
                        } else {
                            // Clear embedding model selection
                            setRagConfig((config) => ({
                                ...config,
                                embeddingModel: undefined,
                            }));
                        }
                    }}
                    options={embeddingOptions}
                />
            </Grid>
        </SpaceBetween>
    );
}

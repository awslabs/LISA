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
import { useListRagRepositoriesQuery, useListCollectionsQuery, RagCollectionConfig } from '@/shared/reducers/rag.reducer';
import { VectorStoreStatus } from '#root/lib/schema';

export type RagConfig = {
    collection?: RagCollectionConfig;
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

export default function RagControls ({ isRunning, setUseRag, setRagConfig, ragConfig }: RagControlProps) {
    const { data: repositories, isLoading: isLoadingRepositories } = useListRagRepositoriesQuery(undefined, {
        refetchOnMountOrArgChange: 5
    });

    const { data: collections, isLoading: isLoadingCollections } = useListCollectionsQuery(
        { repositoryId: ragConfig?.repositoryId },
        {
            skip: !ragConfig?.repositoryId,
            refetchOnMountOrArgChange: 5
        }
    );

    const { data: allModels } = useGetAllModelsQuery(undefined, {
        refetchOnMountOrArgChange: 5,
        selectFromResult: (state) => ({
            isLoading: state.isLoading,
            data: (state.data || []).filter((model) => model.modelType === ModelType.embedding && model.status === ModelStatus.InService),
        })
    });

    const [userHasSelectedCollection, setUserHasSelectedCollection] = useState<boolean>(false);

    const lastRepositoryIdRef = useRef<string>(undefined);

    const selectedRepositoryOption = ragConfig?.repositoryId ?? '';
    const selectedCollectionOption = ragConfig?.collection?.name ?? '';

    const filteredRepositories = useMemo(() => {
        if (!repositories) return [];
        return repositories.filter((repo) =>
            repo.status === VectorStoreStatus.CREATE_COMPLETE || repo.status === VectorStoreStatus.UPDATE_COMPLETE
        );
    }, [repositories]);

    const collectionOptions = useMemo(() => {
        if (!collections) return [];
        return collections.map((collection) => ({
            value: collection.collectionId,
            label: collection.name,
        }));
    }, [collections]);

    // Update useRag flag based on repository and embedding model availability
    useEffect(() => {
        const hasRepository = !!ragConfig?.repositoryId;
        const hasEmbeddingModel = !!ragConfig?.embeddingModel;
        setUseRag(hasRepository && hasEmbeddingModel);
    }, [ragConfig?.repositoryId, ragConfig?.embeddingModel, setUseRag]);

    // Effect for handling repository changes and default embedding model selection
    useEffect(() => {
        const currentRepositoryId = ragConfig?.repositoryId;
        const repositoryHasChanged = currentRepositoryId !== lastRepositoryIdRef.current;

        // Update tracking and reset user selection flag when repository changes
        if (repositoryHasChanged) {
            lastRepositoryIdRef.current = currentRepositoryId;
            setUserHasSelectedCollection(false);
        }

        // Set default embedding model when no collection is selected
        if (currentRepositoryId && filteredRepositories && allModels && !userHasSelectedCollection) {
            const repository = filteredRepositories.find((repo) => repo.repositoryId === currentRepositoryId);

            if (repository?.embeddingModelId && !ragConfig?.collection) {
                const defaultModel = allModels.find((model) => model.modelId === repository.embeddingModelId);

                if (defaultModel && !ragConfig?.embeddingModel) {
                    setRagConfig((config) => ({
                        ...config,
                        embeddingModel: defaultModel,
                    }));
                }
            }
        }
    }, [
        ragConfig?.repositoryId,
        ragConfig?.collection,
        ragConfig?.embeddingModel,
        filteredRepositories,
        allModels,
        userHasSelectedCollection,
        setRagConfig
    ]);

    const handleRepositoryChange = ({ detail }) => {
        const newRepositoryId = detail.value;
        setUserHasSelectedCollection(false); // Reset collection selection flag

        if (newRepositoryId) {
            const repository = filteredRepositories?.find((repo) => repo.repositoryId === newRepositoryId);
            setRagConfig((config) => ({
                ...config,
                repositoryId: newRepositoryId,
                repositoryType: repository?.type || 'unknown',
                collection: undefined, // Clear collection when repository changes
                embeddingModel: undefined, // Clear current model so useEffect can set default
            }));
        } else {
            setRagConfig((config) => ({
                ...config,
                repositoryId: undefined,
                repositoryType: undefined,
                collection: undefined,
                embeddingModel: undefined,
            }));
        }
    };

    const handleCollectionChange = ({ detail }) => {
        const newCollectionId = detail.value;
        setUserHasSelectedCollection(true);

        if (newCollectionId) {
            const collection = collections?.find(
                (c) => c.collectionId === newCollectionId
            );
            if (collection) {
                // Find the embedding model from allModels
                const embeddingModel = allModels?.find(
                    (model) => model.modelId === collection.embeddingModel
                );

                setRagConfig((config) => ({
                    ...config,
                    collection: collection,
                    embeddingModel: embeddingModel,
                }));
            }
        } else {
            // User cleared collection - fall back to repository default
            const repository = filteredRepositories?.find(
                (repo) => repo.repositoryId === ragConfig?.repositoryId
            );
            const defaultModel = allModels?.find(
                (model) => model.modelId === repository?.embeddingModelId
            );

            setRagConfig((config) => ({
                ...config,
                collection: undefined,
                embeddingModel: defaultModel,
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
                    options={filteredRepositories?.map((repository) => ({
                        value: repository.repositoryId,
                        label: repository?.repositoryName?.length ? repository?.repositoryName : repository.repositoryId
                    })) || []}
                />
                <Autosuggest
                    disabled={!selectedRepositoryOption || isRunning}
                    statusType={isLoadingCollections ? 'loading' : 'finished'}
                    loadingText='Loading collections...'
                    placeholder='Select a collection (optional)'
                    empty={<div className='text-gray-500'>No collections available. Using repository default.</div>}
                    filteringType='auto'
                    value={selectedCollectionOption}
                    enteredTextLabel={(text) => `Use: "${text}"`}
                    onChange={handleCollectionChange}
                    options={collectionOptions}
                />
            </Grid>
        </SpaceBetween>
    );
}

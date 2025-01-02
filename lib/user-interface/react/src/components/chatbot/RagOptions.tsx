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
import { AuthContextProps } from 'react-oidc-context';
import { useGetAllModelsQuery } from '../../shared/reducers/model-management.reducer';
import { IModel, ModelStatus, ModelType } from '../../shared/model/model-management.model';
import { useListRagRepositoriesQuery } from '../../shared/reducers/rag.reducer';

export type RagConfig = {
    embeddingModel: IModel;
    repositoryId: string;
    repositoryType: string;
};

type RagControlProps = {
    isRunning: boolean;
    setUseRag: React.Dispatch<React.SetStateAction<boolean>>;
    auth: AuthContextProps;
    setRagConfig: React.Dispatch<React.SetStateAction<RagConfig>>;
};

export default function RagControls ({isRunning, setUseRag, setRagConfig }: RagControlProps) {
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
                    onChange={({ detail }) => {
                        setSelectedRepositoryOption(detail.value);
                        setRagConfig((config) => ({
                            ...config,
                            repositoryId: detail.value,
                            repositoryType: detail.value,
                        }));
                    }}
                    options={repositories?.map((repository) => ({value: repository.repositoryId})) || []}
                />
                <Autosuggest
                    disabled={!selectedRepositoryOption || isRunning}
                    statusType={isFetchingModels ? 'loading' : 'finished'}
                    loadingText='Loading embedding models (might take few seconds)...'
                    placeholder='Select an embedding model'
                    empty={<div className='text-gray-500'>No embedding models available.</div>}
                    filteringType='auto'
                    value={selectedEmbeddingOption ?? ''}
                    onChange={({ detail }) => {
                        setSelectedEmbeddingOption(detail.value);

                        const model = allModels.find((model) => model.modelId === detail.value);
                        if (model) {
                            setRagConfig((config) => ({
                                ...config,
                                embeddingModel: model,
                            }));
                        }
                    }}
                    options={embeddingOptions}
                />
            </Grid>
        </SpaceBetween>
    );
}

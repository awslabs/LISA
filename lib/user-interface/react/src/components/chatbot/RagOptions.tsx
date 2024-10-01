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

import { Button, Grid, Select, SelectProps, SpaceBetween } from '@cloudscape-design/components';
import { useEffect, useMemo, useState } from 'react';
import { listRagRepositories } from '../utils';
import { AuthContextProps } from 'react-oidc-context';
import { useGetAllModelsQuery } from '../../shared/reducers/model-management.reducer';
import { IModel, ModelStatus, ModelType } from '../../shared/model/model-management.model';

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

export default function RagControls ({ auth, isRunning, setUseRag, setRagConfig }: RagControlProps) {
    const [isLoadingRepositories, setIsLoadingRepositories] = useState(false);
    const [repositoryOptions, setRepositoryOptions] = useState<SelectProps.Options>([]);
    const [selectedEmbeddingOption, setSelectedEmbeddingOption] = useState<SelectProps.Option | undefined>(undefined);
    const [selectedRepositoryOption, setSelectedRepositoryOption] = useState<SelectProps.Option | undefined>(undefined);
    const [repositoryMap, setRepositoryMap] = useState(new Map());
    const { data: allModels, isFetching: isFetchingModels } = useGetAllModelsQuery(undefined, {selectFromResult: (state) => ({
        isFetching: state.isFetching,
        data: (state.data || []).filter((model) => model.modelType === ModelType.embedding && model.status === ModelStatus.InService),
    })});
    const embeddingOptions = useMemo(() => {
        return allModels?.map((model) => ({value: model.modelId})) || [];
    }, [allModels]);

    useEffect(() => {
        setIsLoadingRepositories(true);

        listRagRepositories(auth.user?.id_token).then((repositories) => {
            setRepositoryOptions(
                repositories.map((repo) => {
                    setRepositoryMap((map) => new Map(map.set(repo.repositoryId, repo.type)));
                    return {
                        label: `${repo.repositoryId} (${repo.type})`,
                        value: repo.repositoryId,
                    };
                }),
            );
            setIsLoadingRepositories(false);
        });
    // We only want this to run a single time on component mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    useEffect(() => {
        setUseRag(!!selectedEmbeddingOption && !!selectedRepositoryOption);
    // setUseRag is never going to change as it's just a setState function
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [selectedRepositoryOption, selectedEmbeddingOption]);

    return (
        <SpaceBetween size='l' direction='vertical'>
            <Grid
                gridDefinition={[
                    { colspan: { default: 12, xxs: 4 } },
                    { colspan: { default: 2, xxs: 2 } },
                    { colspan: { default: 12, xxs: 4 } },
                    { colspan: { default: 2, xxs: 2 } },
                ]}
            >
                <Select
                    disabled={isRunning}
                    statusType={isLoadingRepositories ? 'loading' : 'finished'}
                    loadingText='Loading repositories (might take few seconds)...'
                    placeholder='Select a RAG Repository'
                    empty={<div className='text-gray-500'>No repositories available.</div>}
                    filteringType='auto'
                    selectedOption={selectedRepositoryOption}
                    onChange={({ detail }) => {
                        setSelectedRepositoryOption(detail.selectedOption);
                        setRagConfig((config) => ({
                            ...config,
                            repositoryId: detail.selectedOption.value,
                            repositoryType: repositoryMap.get(detail.selectedOption.value),
                        }));
                    }}
                    options={repositoryOptions}
                />
                <Button
                    disabled={selectedRepositoryOption === undefined}
                    onClick={() => {
                        setSelectedRepositoryOption(undefined);
                        setRagConfig((config) => {
                            config.repositoryId = undefined;
                            config.repositoryType = undefined;
                            return config;
                        });
                    }}
                >
                    Clear
                </Button>
                <Select
                    disabled={!selectedRepositoryOption || isRunning}
                    statusType={isFetchingModels ? 'loading' : 'finished'}
                    loadingText='Loading embedding models (might take few seconds)...'
                    placeholder='Select an embedding model'
                    empty={<div className='text-gray-500'>No embedding models available.</div>}
                    filteringType='auto'
                    selectedOption={selectedEmbeddingOption}
                    onChange={({ detail }) => {
                        setSelectedEmbeddingOption(detail.selectedOption);

                        const model = allModels.find((model) => model.modelId === detail.selectedOption.value);
                        if (model) {
                            setRagConfig((config) => ({
                                ...config,
                                embeddingModel: model,
                            }));
                        }
                    }}
                    options={embeddingOptions}
                />
                <Button
                    disabled={selectedEmbeddingOption === undefined}
                    onClick={() => {
                        setSelectedEmbeddingOption(undefined);
                        setRagConfig((config) => {
                            config.embeddingModel = undefined;
                            return config;
                        });
                    }}
                >
                    Clear
                </Button>
            </Grid>
        </SpaceBetween>
    );
}

import { Button, Grid, Select, SelectProps, SpaceBetween } from '@cloudscape-design/components';
import { useEffect, useState } from 'react';
import { Model } from '../types';
import {
  createModelMap,
  createModelOptions,
  describeModels,
  listRagRepositories,
  parseDescribeModelsResponse,
} from '../utils';
import { AuthContextProps } from 'react-oidc-context';

export type RagConfig = {
  embeddingModel: Model;
  repositoryId: string;
  repositoryType: string;
};

interface RagControlProps {
  isRunning: boolean;
  setUseRag: React.Dispatch<React.SetStateAction<boolean>>;
  auth: AuthContextProps;
  setRagConfig: React.Dispatch<React.SetStateAction<RagConfig>>;
}

export default function RagControls({ auth, isRunning, setUseRag, setRagConfig }: RagControlProps) {
  const [embeddingOptions, setEmbeddingOptions] = useState<SelectProps.Options>([]);
  const [embeddingModelMap, setEmbeddingModelMap] = useState<Map<string, Model> | undefined>(undefined);
  const [isLoadingEmbeddingModels, setIsLoadingEmbeddingModels] = useState(false);
  const [isLoadingRepositories, setIsLoadingRepositories] = useState(false);
  const [repositoryOptions, setRepositoryOptions] = useState<SelectProps.Options>([]);
  const [selectedEmbeddingOption, setSelectedEmbeddingOption] = useState<SelectProps.Option | undefined>(undefined);
  const [selectedRepositoryOption, setSelectedRepositoryOption] = useState<SelectProps.Option | undefined>(undefined);
  const [repositoryMap, setRepositoryMap] = useState(new Map());

  useEffect(() => {
    setIsLoadingEmbeddingModels(true);
    setIsLoadingRepositories(true);

    describeModels(['embedding'], auth.user?.id_token).then((resp) => {
      const embeddingModelProviders = parseDescribeModelsResponse(resp, 'embedding');
      setEmbeddingOptions(createModelOptions(embeddingModelProviders));
      setEmbeddingModelMap(createModelMap(embeddingModelProviders));
      setIsLoadingEmbeddingModels(false);
    });

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
    <SpaceBetween size="l" direction="vertical">
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
          loadingText="Loading repositories (might take few seconds)..."
          placeholder="Select a RAG Repository"
          empty={<div className="text-gray-500">No repositories available.</div>}
          filteringType="auto"
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
          disabled={isRunning}
          statusType={isLoadingEmbeddingModels ? 'loading' : 'finished'}
          loadingText="Loading embedding models (might take few seconds)..."
          placeholder="Select an embedding model"
          empty={<div className="text-gray-500">No embedding models available.</div>}
          filteringType="auto"
          selectedOption={selectedEmbeddingOption}
          onChange={({ detail }) => {
            setSelectedEmbeddingOption(detail.selectedOption);
            setRagConfig((config) => ({
              ...config,
              embeddingModel: embeddingModelMap[detail.selectedOption.value],
            }));
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

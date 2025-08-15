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

import { ReactElement, useContext, useState } from 'react';
import {
    SpaceBetween,
    Header,
    Button,
    Alert,
    ContentLayout,
    Container,
} from '@cloudscape-design/components';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faArrowLeft } from '@fortawesome/free-solid-svg-icons';
import { useNavigate } from 'react-router-dom';
import { ModelStatus, ModelType } from '@/shared/model/model-management.model';
import { useGetAllModelsQuery } from '@/shared/reducers/model-management.reducer';
import { useModelComparison } from '@/components/model-management/hooks/useModelComparison.hook';
import {
    ModelSelectionSection,
    PromptInputSection,
    ComparisonResults
} from '@/components/model-management/components/ModelComparisonComponents';
import { MESSAGES } from '@/components/model-management/config/modelComparison.config';
import SessionConfiguration from '@/components/chatbot/components/SessionConfiguration';
import { IChatConfiguration, baseConfig } from '@/shared/model/chat.configurations.model';
import ConfigurationContext from '@/shared/configuration.provider';

type ModelComparisonPageProps = {
    setNav: (nav: any) => void;
};

export default function ModelComparisonPage({ setNav }: ModelComparisonPageProps): ReactElement {
    const navigate = useNavigate();
    const config = useContext(ConfigurationContext);

    // Modal state for SessionConfiguration
    const [showSessionConfig, setShowSessionConfig] = useState(false);

    // Basic chat configuration state for SessionConfiguration
    const [modelConfiguration, setModelConfiguration] = useState<IChatConfiguration>(baseConfig);

    // Get available models
    const { data: allModels } = useGetAllModelsQuery(undefined, {
        refetchOnMountOrArgChange: 5,
        selectFromResult: (state) => ({
            data: (state.data || []).filter((model) =>
                (model.modelType === ModelType.textgen || model.modelType === ModelType.imagegen) &&
                model.status === ModelStatus.InService
            ),
        })
    });

    const models = allModels || [];

    const {
        // State
        modelSelections,
        prompt,
        responses,
        availableModels,
        canCompare,
        
        // Actions
        setPrompt,
        addModelComparison,
        removeModelComparison,
        updateModelSelection,
        getAvailableModelsForSelection,
        handleCompare,
    } = useModelComparison(models, modelConfiguration);

    const handleBack = () => {
        navigate('/ai-assistant');
    };

    const handleOpenSettings = () => {
        setShowSessionConfig(true);
    };

    return (
        <>
            <ContentLayout
                header={
                    <Header
                        variant="h1"
                        actions={
                            <SpaceBetween direction="horizontal" size="xs">

                                <Button
                                    variant="normal"
                                    iconAlign="left"
                                    onClick={handleBack}
                                >
                                    <FontAwesomeIcon icon={faArrowLeft} />
                                    Back to Chat
                                </Button>
                            </SpaceBetween>
                        }
                    >
                        Model Comparison
                        <Button
                            variant="icon"
                            onClick={handleOpenSettings}
                            ariaLabel="Open settings"
                            iconName="settings" >
                        </Button>
                    </Header>
                }
            >
                <Container>
                    <SpaceBetween size='l'>
                        <ModelSelectionSection
                            modelSelections={modelSelections}
                            availableModels={availableModels}
                            onAddModel={addModelComparison}
                            onRemoveModel={removeModelComparison}
                            onUpdateSelection={updateModelSelection}
                            getAvailableModelsForSelection={getAvailableModelsForSelection}
                        />

                        <PromptInputSection
                            prompt={prompt}
                            onPromptChange={setPrompt}
                            onCompare={handleCompare}
                            canCompare={canCompare}
                        />

                        {responses.length > 0 && (
                            <ComparisonResults
                                prompt={prompt}
                                responses={responses}
                                models={models}
                                markdownDisplay={modelConfiguration.sessionConfiguration.markdownDisplay}
                            />
                        )}

                        {availableModels.length < 2 && (
                            <Alert type='warning' header='Insufficient Models'>
                                {MESSAGES.INSUFFICIENT_MODELS}
                            </Alert>
                        )}
                    </SpaceBetween>
                </Container>
            </ContentLayout>

            <SessionConfiguration
                chatConfiguration={modelConfiguration}
                setChatConfiguration={setModelConfiguration}
                selectedModel={models[0]} // Use first available model as default
                isRunning={false}
                visible={showSessionConfig}
                setVisible={setShowSessionConfig}
                systemConfig={config}
            />
        </>
    );
}
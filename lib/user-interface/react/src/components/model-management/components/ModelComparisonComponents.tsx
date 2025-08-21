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

import { ReactElement, memo } from 'react';
import {
    Box,
    SpaceBetween,
    Header,
    Select,
    Button,
    Container,
    ColumnLayout,
    Alert,
    SelectProps,
    PromptInput
} from '@cloudscape-design/components';
import { IModel } from '../../../shared/model/model-management.model';
import { ComparisonResponse, ModelSelection } from '../hooks/useModelComparison.hook';
import {
    MODEL_COMPARISON_CONFIG,
    UI_CONFIG,
    PLACEHOLDERS,
    ARIA_LABELS
} from '../config/modelComparison.config';
import { LisaChatMessage, MessageTypes } from '../../types';
import Message from '../../chatbot/components/Message';
import { IChatConfiguration } from '../../../shared/model/chat.configurations.model';

type ModelSelectionSectionProps = {
    modelSelections: ModelSelection[];
    availableModels: SelectProps.Option[];
    onAddModel: () => void;
    onRemoveModel: (id: string) => void;
    onUpdateSelection: (id: string, selectedModel: SelectProps.Option | null) => void;
    getAvailableModelsForSelection: (id: string) => SelectProps.Option[];
};

export const ModelSelectionSection = memo(function ModelSelectionSection ({
    modelSelections,
    onAddModel,
    onRemoveModel,
    onUpdateSelection,
    getAvailableModelsForSelection
}: ModelSelectionSectionProps): ReactElement {
    return (
        <Container
            header={
                <Header
                    variant='h2'
                    actions={
                        <Button
                            variant='icon'
                            iconName='add-plus'
                            onClick={onAddModel}
                            disabled={modelSelections.length >= MODEL_COMPARISON_CONFIG.MAX_MODELS}
                            ariaLabel={ARIA_LABELS.ADD_MODEL}
                        />
                    }
                >
                    Model Selection & Prompt
                </Header>
            }
        >
            <ColumnLayout columns={modelSelections.length <= UI_CONFIG.GRID_BREAKPOINT ? modelSelections.length : UI_CONFIG.GRID_BREAKPOINT}>
                {modelSelections.map((selection, index) => (
                    <SpaceBetween key={selection.id} size='s'>
                        <SpaceBetween direction='horizontal' size='xs' alignItems='center'>
                            <Box variant='h3'>
                                Model {index + 1}
                            </Box>
                            {modelSelections.length > MODEL_COMPARISON_CONFIG.MIN_MODELS && (
                                <Button
                                    variant='icon'
                                    iconName='remove'
                                    onClick={() => onRemoveModel(selection.id)}
                                    ariaLabel={ARIA_LABELS.REMOVE_MODEL(index + 1)}
                                    formAction='none'
                                />
                            )}
                        </SpaceBetween>
                        <Select
                            selectedOption={selection.selectedModel}
                            onChange={({ detail }) => onUpdateSelection(selection.id, detail.selectedOption)}
                            options={getAvailableModelsForSelection(selection.id)}
                            placeholder={PLACEHOLDERS.MODEL_SELECT(index + 1)}
                            filteringType='auto'
                        />
                    </SpaceBetween>
                ))}
            </ColumnLayout>
        </Container>
    );
});

type PromptInputSectionProps = {
    prompt: string;
    onPromptChange: (value: string) => void;
    onCompare: () => void;
    canCompare: boolean;
};

export const PromptInputSection = memo(function PromptInputSection ({
    prompt,
    onPromptChange,
    onCompare,
    canCompare
}: PromptInputSectionProps): ReactElement {
    return (
        <SpaceBetween size='s'>
            <Box variant='h3'>Prompt</Box>
            <PromptInput
                value={prompt}
                onChange={({ detail }) => onPromptChange(detail.value)}
                placeholder={PLACEHOLDERS.PROMPT_INPUT}
                actionButtonIconName='send'
                actionButtonAriaLabel={ARIA_LABELS.SEND_PROMPT}
                onAction={onCompare}
                actionButtonDisabled={!canCompare}
            />
        </SpaceBetween>
    );
});



type ComparisonResultsProps = {
    prompt: string;
    responses: ComparisonResponse[];
    models: IModel[];
    markdownDisplay?: boolean;
    chatConfiguration: IChatConfiguration;
    setChatConfiguration: (config: IChatConfiguration) => void;
};

export const ComparisonResults = memo(function ComparisonResults ({
    prompt,
    responses,
    models,
    markdownDisplay = true,
    chatConfiguration,
    setChatConfiguration
}: ComparisonResultsProps): ReactElement {

    // Create a user message for the prompt
    const userMessage = new LisaChatMessage({
        type: MessageTypes.HUMAN,
        content: prompt,
        metadata: {}
    });

    // Create AI messages for each response
    const aiMessages = responses.map((response) => {
        const model = models.find((m) => m.modelId === response.modelId);
        const modelName = model?.modelName || response.modelId;

        return new LisaChatMessage({
            type: MessageTypes.AI,
            content: response.loading ? '' : response.error ? `Error: ${response.error}` : response.response,
            metadata: {
                modelName: modelName
            }
        });
    });

    // Dummy functions for Message component (not used in comparison context)
    const handleSendGenerateRequest = () => {};
    const setUserPrompt = () => {};

    return (
        <Container header={<Header variant='h2'>Comparison Results</Header>}>
            <SpaceBetween size='m'>
                {/* Display user prompt */}
                {prompt && (
                    <Message
                        message={userMessage}
                        isRunning={false}
                        callingToolName=''
                        showMetadata={false}
                        isStreaming={false}
                        markdownDisplay={markdownDisplay}
                        setChatConfiguration={setChatConfiguration}
                        handleSendGenerateRequest={handleSendGenerateRequest}
                        setUserPrompt={setUserPrompt}
                        chatConfiguration={chatConfiguration}
                    />
                )}

                {/* Display model responses in a grid */}
                <ColumnLayout columns={responses.length <= UI_CONFIG.GRID_BREAKPOINT ? responses.length : UI_CONFIG.GRID_BREAKPOINT}>
                    {responses.map((response, index) => {
                        const model = models.find((m) => m.modelId === response.modelId);
                        const modelName = model?.modelName || response.modelId;

                        return (
                            <Container key={response.modelId} header={<Header variant='h3'>{modelName}</Header>}>
                                <Message
                                    message={aiMessages[index]}
                                    isRunning={response.loading}
                                    callingToolName=''
                                    showMetadata={false}
                                    isStreaming={false}
                                    markdownDisplay={markdownDisplay}
                                    setChatConfiguration={setChatConfiguration}
                                    handleSendGenerateRequest={handleSendGenerateRequest}
                                    setUserPrompt={setUserPrompt}
                                    chatConfiguration={chatConfiguration}
                                />
                                {response.error && (
                                    <Alert type='error' header='Error'>
                                        {response.error}
                                    </Alert>
                                )}
                            </Container>
                        );
                    })}
                </ColumnLayout>
            </SpaceBetween>
        </Container>
    );
});

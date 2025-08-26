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

import { ReactElement, memo, useCallback, useRef } from 'react';
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
import { IModel } from '@/shared/model/model-management.model';
import { ComparisonResponse, ModelSelection } from '@/components/model-management/hooks/useModelComparison.hook';
import {
    MODEL_COMPARISON_CONFIG,
    UI_CONFIG,
    PLACEHOLDERS,
    ARIA_LABELS
} from '../config/modelComparison.config';
import { LisaChatMessage, MessageTypes } from '@/components/types';
import Message from '@/components/chatbot/components/Message';
import { IChatConfiguration } from '@/shared/model/chat.configurations.model';
import { downloadFile } from '@/shared/util/downloader';

type ModelSelectionSectionProps = {
    modelSelections: ModelSelection[];
    availableModels: SelectProps.Option[];
    onAddModel: () => void;
    onRemoveModel: (id: string) => void;
    onUpdateSelection: (id: string, selectedModel: SelectProps.Option | null) => void;
    getAvailableModelsForSelection: (id: string) => SelectProps.Option[];
};

export const ModelSelectionSection = memo(function ModelSelectionSection({
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
    onStopComparison: () => void;
    canCompare: boolean;
    shouldShowStopButton: boolean;
};

export const PromptInputSection = memo(function PromptInputSection({
    prompt,
    onPromptChange,
    onCompare,
    onStopComparison,
    canCompare,
    shouldShowStopButton
}: PromptInputSectionProps): ReactElement {
    // Ref to track if we're processing a keyboard event
    const isKeyboardEventRef = useRef(false);

    // Handle stop functionality similar to Chat.tsx
    const handleStop = useCallback(() => {
        onStopComparison();
    }, [onStopComparison]);

    // Custom action handler that only allows stop on button clicks
    const handleAction = useCallback(() => {
        // If this is a keyboard event, don't process it here (it's handled in handleKeyPress)
        if (isKeyboardEventRef.current) {
            return;
        }

        if (shouldShowStopButton) {
            // Only allow stop action on button clicks (not keyboard events)
            handleStop();
        } else {
            // Normal send functionality - allow both button clicks and Enter key
            if (prompt.length > 0 && canCompare) {
                onCompare();
            }
        }
    }, [shouldShowStopButton, handleStop, prompt.length, canCompare, onCompare]);

    // Handle Enter key press
    const handleKeyPress = useCallback((event: any) => {
        if (event.detail.key === 'Enter' && !event.detail.shiftKey) {
            event.preventDefault();
            isKeyboardEventRef.current = true;

            // Handle the action directly for keyboard events
            if (shouldShowStopButton) {
                // Do nothing for stop button when Enter is pressed
            } else {
                // Normal send functionality for Enter key
                if (prompt.length > 0 && canCompare) {
                    onCompare();
                }
            }

            // Reset the flag after a short delay
            setTimeout(() => {
                isKeyboardEventRef.current = false;
            }, 100);
        }
    }, [shouldShowStopButton, prompt.length, canCompare, onCompare]);

    return (
        <SpaceBetween size='s'>
            <Box variant='h3'>Prompt</Box>
            <PromptInput
                value={prompt}
                onChange={({ detail }) => onPromptChange(detail.value)}
                placeholder={PLACEHOLDERS.PROMPT_INPUT}
                actionButtonIconName={shouldShowStopButton ? 'status-negative' : 'send'}
                actionButtonAriaLabel={shouldShowStopButton ? 'Stop comparison' : ARIA_LABELS.SEND_PROMPT}
                onAction={handleAction}
                onKeyDown={handleKeyPress}
                maxRows={4}
                minRows={2}
                spellcheck={true}
                disabled={!canCompare && !shouldShowStopButton}
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

export const ComparisonResults = memo(function ComparisonResults({
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
    const handleSendGenerateRequest = () => { };
    const setUserPrompt = () => { };

    const handleDownloadResults = (): void => {
        const results = responses.map((response) => {
            const model = models.find((m) => m.modelId === response.modelId);
            return {
                modelId: response.modelId,
                modelName: model?.modelName || response.modelId,
                response: response.response,
                error: response.error,
                loading: response.loading
            };
        });

        const data = {
            prompt: prompt,
            configuration: chatConfiguration,
            results: results
        };

        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
        const filename = `model-comparison-${timestamp}.json`;
        const url = URL.createObjectURL(blob);
        downloadFile(url, filename);
    };

    return (
        <Container header={<Header variant='h2' actions={
            <Button
                iconName='download'
                onClick={handleDownloadResults}
                disabled={responses.length === 0 || responses.some((r) => r.loading || r.streaming)}
            >
                Download Results
            </Button>
        }>Comparison Results</Header>}>
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
                                    isStreaming={response.streaming}
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

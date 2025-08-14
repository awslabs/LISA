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

import { ReactElement, useState, useCallback } from 'react';
import {
    Modal,
    Box,
    SpaceBetween,
    Header,
    Select,
    Button,
    Container,
    ColumnLayout,
    Alert,
    SelectProps,
    PromptInput,
    ButtonGroup,
    StatusIndicator
} from '@cloudscape-design/components';
import ChatBubble from '@cloudscape-design/chat-components/chat-bubble';
import Avatar from '@cloudscape-design/chat-components/avatar';
import ReactMarkdown from 'react-markdown';
import remarkBreaks from 'remark-breaks';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { useAuth } from 'react-oidc-context';
import { ChatOpenAI } from '@langchain/openai';
import { IModel, ModelStatus } from '../../shared/model/model-management.model';
import { RESTAPI_URI, RESTAPI_VERSION } from '../utils';
import { useAppDispatch } from '../../config/store';
import { useNotificationService } from '../../shared/util/hooks';

export interface ModelComparisonModalProps {
    visible: boolean;
    setVisible: (visible: boolean) => void;
    models: IModel[];
}

interface ComparisonResponse {
    modelId: string;
    response: string;
    loading: boolean;
    error?: string;
}

interface ModelSelection {
    id: string;
    selectedModel: SelectProps.Option | null;
}

export function ModelComparisonModal({ visible, setVisible, models }: ModelComparisonModalProps): ReactElement {
    const dispatch = useAppDispatch();
    const auth = useAuth();
    const notificationService = useNotificationService(dispatch);

    const [modelSelections, setModelSelections] = useState<ModelSelection[]>([
        { id: '1', selectedModel: null },
        { id: '2', selectedModel: null }
    ]);
    const [prompt, setPrompt] = useState<string>('');
    const [responses, setResponses] = useState<ComparisonResponse[]>([]);
    const [isComparing, setIsComparing] = useState<boolean>(false);

    // Filter models to only show InService text generation models
    const availableModels = models
        .filter(model =>
            model.status === ModelStatus.InService &&
            model.modelType === 'textgen'
        )
        .map(model => ({
            label: model.modelName,
            value: model.modelId,
            description: model.modelId
        }));

    const addModelComparison = () => {
        if (modelSelections.length < 4) {
            const newId = (modelSelections.length + 1).toString();
            setModelSelections([...modelSelections, { id: newId, selectedModel: null }]);
        }
    };

    const removeModelComparison = (idToRemove: string) => {
        if (modelSelections.length > 2) {
            setModelSelections(modelSelections.filter(selection => selection.id !== idToRemove));
        }
    };

    const updateModelSelection = (id: string, selectedModel: SelectProps.Option | null) => {
        setModelSelections(modelSelections.map(selection =>
            selection.id === id ? { ...selection, selectedModel } : selection
        ));
    };

    // Get available models for a specific dropdown, excluding already selected models
    const getAvailableModelsForSelection = (currentSelectionId: string) => {
        const selectedModelIds = modelSelections
            .filter(selection => selection.id !== currentSelectionId && selection.selectedModel)
            .map(selection => selection.selectedModel!.value);

        return availableModels.filter(model => !selectedModelIds.includes(model.value));
    };

    const createOpenAiClient = useCallback((modelId: string) => {
        const model = models.find(m => m.modelId === modelId);
        if (!model) return null;

        const modelConfig = {
            modelName: model.modelId,
            openAIApiKey: auth.user?.id_token,
            maxRetries: 0,
            configuration: {
                baseURL: `${RESTAPI_URI}/${RESTAPI_VERSION}/serve`,
            },
            streaming: false,
            maxTokens: 2000,
        };

        return new ChatOpenAI(modelConfig);
    }, [models, auth]);

    const generateModelResponse = async (modelId: string, userPrompt: string): Promise<string> => {
        const llmClient = createOpenAiClient(modelId);
        if (!llmClient) {
            throw new Error(`Failed to create client for model ${modelId}`);
        }

        // Create messages similar to Chat.tsx
        const messages = [
            {
                role: 'system',
                content: 'You are a helpful AI assistant. Provide clear, concise, and accurate responses.'
            },
            {
                role: 'user',
                content: userPrompt
            }
        ];

        try {
            const response = await llmClient.invoke(messages);
            return response.content as string;
        } catch (error) {
            console.error(`Error generating response for model ${modelId}:`, error);
            throw new Error(`Failed to generate response: ${error.message || 'Unknown error'}`);
        }
    };

    const handleCompare = async () => {
        const selectedModels = modelSelections
            .filter(selection => selection.selectedModel)
            .map(selection => selection.selectedModel!);

        if (selectedModels.length < 2 || !prompt.trim()) {
            return;
        }

        setIsComparing(true);
        const initialResponses = selectedModels.map(model => ({
            modelId: model.value!,
            response: '',
            loading: true
        }));
        setResponses(initialResponses);

        // Make real API calls to all selected models
        try {
            const responsePromises = selectedModels.map(async (model) => {
                try {
                    const response = await generateModelResponse(model.value!, prompt);
                    return {
                        modelId: model.value!,
                        response,
                        loading: false
                    };
                } catch (error) {
                    return {
                        modelId: model.value!,
                        response: '',
                        loading: false,
                        error: error.message || 'Failed to get response'
                    };
                }
            });

            const modelResponses = await Promise.all(responsePromises);
            setResponses(modelResponses);
        } catch (error) {
            console.error('Error in model comparison:', error);
            notificationService.generateNotification(
                'Failed to compare models',
                'error',
                undefined,
                error.message ? <p>{error.message}</p> : undefined
            );

            const errorResponses = selectedModels.map(model => ({
                modelId: model.value!,
                response: '',
                loading: false,
                error: 'Failed to get response'
            }));
            setResponses(errorResponses);
        } finally {
            setIsComparing(false);
        }
    };



    const handleClose = () => {
        setVisible(false);
        setModelSelections([
            { id: '1', selectedModel: null },
            { id: '2', selectedModel: null }
        ]);
        setPrompt('');
        setResponses([]);
        setIsComparing(false);
    };

    const selectedModelsCount = modelSelections.filter(selection => selection.selectedModel).length;
    const canCompare = selectedModelsCount >= 2 && prompt.trim() && !isComparing;

    return (
        <Modal
            onDismiss={handleClose}
            visible={visible}
            size="max"
            header={
                <Header variant="h1">
                    Model Comparison
                </Header>
            }
            footer={
                <Box float="right">
                    <Button variant="link" onClick={handleClose}>
                        Close
                    </Button>
                </Box>
            }
        >
            <SpaceBetween size="l">
                <Container
                    header={
                        <Header
                            variant="h2"
                            actions={
                                <Button
                                    variant="icon"
                                    iconName="add-plus"
                                    onClick={addModelComparison}
                                    disabled={modelSelections.length >= 4}
                                    ariaLabel="Add model comparison"
                                />
                            }
                        >
                            Model Selection & Prompt
                        </Header>
                    }
                >
                    <SpaceBetween size="m">
                        <ColumnLayout columns={modelSelections.length <= 2 ? modelSelections.length : 2}>
                            {modelSelections.map((selection, index) => (
                                <SpaceBetween key={selection.id} size="s">
                                    <SpaceBetween direction="horizontal" size="xs" alignItems="center">
                                        <Box variant="h3">
                                            Model {index + 1}
                                        </Box>
                                        {modelSelections.length > 2 && (
                                            <Button
                                                variant="icon"
                                                iconName="remove"
                                                onClick={() => removeModelComparison(selection.id)}
                                                ariaLabel={`Remove model ${index + 1}`}
                                                formAction="none"
                                            />
                                        )}
                                    </SpaceBetween>
                                    <Select
                                        selectedOption={selection.selectedModel}
                                        onChange={({ detail }) => updateModelSelection(selection.id, detail.selectedOption)}
                                        options={getAvailableModelsForSelection(selection.id)}
                                        placeholder={`Select model ${index + 1}`}
                                        filteringType="auto"
                                    />
                                </SpaceBetween>
                            ))}
                        </ColumnLayout>

                        <SpaceBetween size="s">
                            <Box variant="h3">Prompt</Box>
                            <PromptInput
                                value={prompt}
                                onChange={({ detail }) => setPrompt(detail.value)}
                                placeholder="Enter your prompt here to compare responses from selected models..."
                                actionButtonIconName="send"
                                actionButtonAriaLabel="Send prompt"
                                onAction={handleCompare}
                            // disabled={!canCompare}
                            />
                        </SpaceBetween>
                    </SpaceBetween>
                </Container>

                {responses.length > 0 && (
                    <Container header={<Header variant="h2">Comparison Results</Header>}>
                        <SpaceBetween size="m">
                            {prompt && (
                                <ChatBubble
                                    ariaLabel="User prompt"
                                    type="outgoing"
                                    avatar={
                                        <Avatar
                                            ariaLabel="User"
                                            tooltipText="User"
                                            initials="U"
                                        />
                                    }
                                >
                                    <Box variant="p">{prompt}</Box>
                                </ChatBubble>
                            )}
                            <ColumnLayout columns={responses.length <= 2 ? responses.length : 2}>
                                {responses.map((response) => {
                                    const modelName = models.find(m => m.modelId === response.modelId)?.modelName || response.modelId;
                                    return (
                                        <SpaceBetween key={response.modelId} size="s">
                                            <Box variant="h4" textAlign="center">{modelName}</Box>
                                            <SpaceBetween direction="horizontal" size="m">
                                                <ChatBubble
                                                    ariaLabel={`Response from ${modelName}`}
                                                    type="incoming"
                                                    showLoadingBar={response.loading}
                                                    avatar={
                                                        <Avatar
                                                            loading={response.loading}
                                                            color="gen-ai"
                                                            iconName="gen-ai"
                                                            ariaLabel={modelName}
                                                            tooltipText={modelName}
                                                        />
                                                    }
                                                >
                                                    {response.loading ? (
                                                        <Box color="text-status-inactive">
                                                            Generating response...
                                                        </Box>
                                                    ) : response.error ? (
                                                        <Alert type="error" header="Error">
                                                            {response.error}
                                                        </Alert>
                                                    ) : (
                                                        <div style={{ maxWidth: '60em' }}>
                                                            <ReactMarkdown
                                                                remarkPlugins={[remarkBreaks]}
                                                                children={response.response}
                                                                components={{
                                                                    code({ className, children, ...props }: any) {
                                                                        const match = /language-(\w+)/.exec(className || '');
                                                                        const codeString = String(children).replace(/\n$/, '');

                                                                        const CodeBlockWithCopyButton = ({ language, code }: { language: string, code: string }) => {
                                                                            return (
                                                                                <div style={{ position: 'relative' }}>
                                                                                    <div
                                                                                        style={{
                                                                                            position: 'absolute',
                                                                                            top: '5px',
                                                                                            right: '5px',
                                                                                            zIndex: 10
                                                                                        }}
                                                                                    >
                                                                                        <ButtonGroup
                                                                                            onItemClick={() =>
                                                                                                navigator.clipboard.writeText(code)
                                                                                            }
                                                                                            ariaLabel='Code actions'
                                                                                            dropdownExpandToViewport
                                                                                            items={[
                                                                                                {
                                                                                                    type: 'icon-button',
                                                                                                    id: 'copy code',
                                                                                                    iconName: 'copy',
                                                                                                    text: 'Copy Code',
                                                                                                    popoverFeedback: (
                                                                                                        <StatusIndicator type='success'>
                                                                                                            Code copied
                                                                                                        </StatusIndicator>
                                                                                                    )
                                                                                                }
                                                                                            ]}
                                                                                            variant='icon'
                                                                                        />
                                                                                    </div>
                                                                                    <SyntaxHighlighter
                                                                                        style={vscDarkPlus}
                                                                                        language={language}
                                                                                        PreTag='div'
                                                                                        {...props}
                                                                                    >
                                                                                        {code}
                                                                                    </SyntaxHighlighter>
                                                                                </div>
                                                                            );
                                                                        };

                                                                        return match ? (
                                                                            <CodeBlockWithCopyButton
                                                                                language={match[1]}
                                                                                code={codeString}
                                                                            />
                                                                        ) : (
                                                                            <code className={className} {...props}>
                                                                                {children}
                                                                            </code>
                                                                        );
                                                                    },
                                                                    ul({ ...props }: any) {
                                                                        return <ul style={{ paddingLeft: '20px', marginTop: '8px', marginBottom: '8px', listStyleType: 'disc' }} {...props} />;
                                                                    },
                                                                    ol({ ...props }: any) {
                                                                        return <ol style={{ paddingLeft: '20px', marginTop: '8px', marginBottom: '8px' }} {...props} />;
                                                                    },
                                                                    li({ ...props }: any) {
                                                                        return <li style={{ marginBottom: '4px', display: 'list-item' }} {...props} />;
                                                                    },
                                                                }}
                                                            />
                                                        </div>
                                                    )}
                                                </ChatBubble>
                                                {!response.loading && !response.error && (
                                                    <div style={{ display: 'flex', alignItems: 'center', height: '100%', justifyContent: 'flex-end' }}>
                                                        <ButtonGroup
                                                            onItemClick={({ detail }) =>
                                                                ['copy'].includes(detail.id) &&
                                                                navigator.clipboard.writeText(response.response)
                                                            }
                                                            ariaLabel='Response actions'
                                                            dropdownExpandToViewport
                                                            items={[
                                                                {
                                                                    type: 'icon-button',
                                                                    id: 'copy',
                                                                    iconName: 'copy',
                                                                    text: 'Copy Response',
                                                                    popoverFeedback: (
                                                                        <StatusIndicator type='success'>
                                                                            Response copied
                                                                        </StatusIndicator>
                                                                    )
                                                                }
                                                            ]}
                                                            variant='icon'
                                                        />
                                                    </div>
                                                )}
                                            </SpaceBetween>
                                        </SpaceBetween>
                                    );
                                })}
                            </ColumnLayout>
                        </SpaceBetween>
                    </Container>
                )}

                {availableModels.length < 2 && (
                    <Alert type="warning" header="Insufficient Models">
                        You need at least 2 InService text generation models to use the comparison feature.
                    </Alert>
                )}
            </SpaceBetween>
        </Modal>
    );
}

export default ModelComparisonModal;

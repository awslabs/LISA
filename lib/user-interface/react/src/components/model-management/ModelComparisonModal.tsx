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

import React, { ReactElement, useState } from 'react';
import {
    Modal,
    Box,
    SpaceBetween,
    Header,
    Select,
    Textarea,
    Button,
    Container,
    ColumnLayout,
    Spinner,
    Alert,
    SelectProps
} from '@cloudscape-design/components';
import { IModel, ModelStatus } from '../../shared/model/model-management.model';

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

export function ModelComparisonModal({ visible, setVisible, models }: ModelComparisonModalProps): ReactElement {
    const [selectedModel1, setSelectedModel1] = useState<SelectProps.Option | null>(null);
    const [selectedModel2, setSelectedModel2] = useState<SelectProps.Option | null>(null);
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

    const handleCompare = async () => {
        if (!selectedModel1 || !selectedModel2 || !prompt.trim()) {
            return;
        }

        setIsComparing(true);
        setResponses([
            { modelId: selectedModel1.value!, response: '', loading: true },
            { modelId: selectedModel2.value!, response: '', loading: true }
        ]);

        // Simulate API calls to both models
        // In a real implementation, you would call your chat API endpoints here
        try {
            const [response1, response2] = await Promise.all([
                simulateModelResponse(selectedModel1.value!, prompt),
                simulateModelResponse(selectedModel2.value!, prompt)
            ]);

            setResponses([
                { modelId: selectedModel1.value!, response: response1, loading: false },
                { modelId: selectedModel2.value!, response: response2, loading: false }
            ]);
        } catch (error) {
            setResponses([
                { modelId: selectedModel1.value!, response: '', loading: false, error: 'Failed to get response' },
                { modelId: selectedModel2.value!, response: '', loading: false, error: 'Failed to get response' }
            ]);
        } finally {
            setIsComparing(false);
        }
    };

    const simulateModelResponse = async (modelId: string, prompt: string): Promise<string> => {
        // Simulate API delay
        await new Promise(resolve => setTimeout(resolve, 2000 + Math.random() * 3000));

        // Simulate different responses from different models
        const responses = [
            `Response from ${modelId}: This is a simulated response to your prompt: "${prompt}". Each model would provide different insights and perspectives based on their training and capabilities.`,
            `${modelId} responds: Here's my analysis of your query: "${prompt}". I would approach this differently than other models, offering unique insights based on my specific training data and architecture.`,
            `From ${modelId}: Your prompt "${prompt}" is interesting. Let me provide a comprehensive response that demonstrates this model's particular strengths and reasoning approach.`
        ];

        return responses[Math.floor(Math.random() * responses.length)];
    };

    const handleClose = () => {
        setVisible(false);
        setSelectedModel1(null);
        setSelectedModel2(null);
        setPrompt('');
        setResponses([]);
        setIsComparing(false);
    };

    const canCompare = selectedModel1 && selectedModel2 && prompt.trim() && !isComparing;

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
                    <SpaceBetween direction="horizontal" size="xs">
                        <Button variant="link" onClick={handleClose}>
                            Close
                        </Button>
                        <Button
                            variant="primary"
                            onClick={handleCompare}
                            disabled={!canCompare}
                            loading={isComparing}
                        >
                            Compare Models
                        </Button>
                    </SpaceBetween>
                </Box>
            }
        >
            <SpaceBetween size="l">
                <Container header={<Header variant="h2">Model Selection & Prompt</Header>}>
                    <SpaceBetween size="m">
                        <ColumnLayout columns={2}>
                            <SpaceBetween size="s">
                                <Box variant="h3">First Model</Box>
                                <Select
                                    selectedOption={selectedModel1}
                                    onChange={({ detail }) => setSelectedModel1(detail.selectedOption)}
                                    options={availableModels}
                                    placeholder="Select first model"
                                    filteringType="auto"
                                />
                            </SpaceBetween>
                            <SpaceBetween size="s">
                                <Box variant="h3">Second Model</Box>
                                <Select
                                    selectedOption={selectedModel2}
                                    onChange={({ detail }) => setSelectedModel2(detail.selectedOption)}
                                    options={availableModels}
                                    placeholder="Select second model"
                                    filteringType="auto"
                                />
                            </SpaceBetween>
                        </ColumnLayout>

                        <SpaceBetween size="s">
                            <Box variant="h3">Prompt</Box>
                            <Textarea
                                value={prompt}
                                onChange={({ detail }) => setPrompt(detail.value)}
                                placeholder="Enter your prompt here to compare responses from both models..."
                                rows={4}
                            />
                        </SpaceBetween>
                    </SpaceBetween>
                </Container>

                {responses.length > 0 && (
                    <Container header={<Header variant="h2">Comparison Results</Header>}>
                        <ColumnLayout columns={2}>
                            {responses.map((response, index) => {
                                const modelName = models.find(m => m.modelId === response.modelId)?.modelName || response.modelId;
                                return (
                                    <Container
                                        key={response.modelId}
                                        header={
                                            <Header variant="h3">
                                                {modelName}
                                            </Header>
                                        }
                                    >
                                        {response.loading ? (
                                            <Box textAlign="center" padding="l">
                                                <SpaceBetween size="m" alignItems="center">
                                                    <Spinner size="large" />
                                                    <Box variant="p">Generating response...</Box>
                                                </SpaceBetween>
                                            </Box>
                                        ) : response.error ? (
                                            <Alert type="error" header="Error">
                                                {response.error}
                                            </Alert>
                                        ) : (
                                            <Box variant="p" padding="s">
                                                {response.response}
                                            </Box>
                                        )}
                                    </Container>
                                );
                            })}
                        </ColumnLayout>
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

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

import { ReactElement, memo, useCallback } from 'react';
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
    PromptInput,
    ButtonGroup,
    StatusIndicator
} from '@cloudscape-design/components';
import ChatBubble from '@cloudscape-design/chat-components/chat-bubble';
import Avatar from '@cloudscape-design/chat-components/avatar';
import ReactMarkdown from 'react-markdown';
import remarkBreaks from 'remark-breaks';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { IModel } from '../../../shared/model/model-management.model';
import { ComparisonResponse, ModelSelection } from '../hooks/useModelComparison.hook';
import {
    MODEL_COMPARISON_CONFIG,
    UI_CONFIG,
    MESSAGES,
    PLACEHOLDERS,
    ARIA_LABELS
} from '../config/modelComparison.config';

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

type UserPromptBubbleProps = {
    prompt: string;
};

export const UserPromptBubble = memo(function UserPromptBubble ({ prompt }: UserPromptBubbleProps): ReactElement {
    return (
        <ChatBubble
            ariaLabel={ARIA_LABELS.USER_PROMPT}
            type='outgoing'
            avatar={
                <Avatar
                    ariaLabel='User'
                    tooltipText='User'
                    initials='U'
                />
            }
        >
            <Box variant='p'>{prompt}</Box>
        </ChatBubble>
    );
});

type ModelResponseBubbleProps = {
    response: ComparisonResponse;
    modelName: string;
};

export const ModelResponseBubble = memo(function ModelResponseBubble ({ response, modelName }: ModelResponseBubbleProps): ReactElement {
    const CodeBlockWithCopyButton = useCallback(({ language, code }: { language: string, code: string }) => {
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
                        onItemClick={() => navigator.clipboard.writeText(code)}
                        ariaLabel={ARIA_LABELS.CODE_ACTIONS}
                        dropdownExpandToViewport
                        items={[
                            {
                                type: 'icon-button',
                                id: 'copy code',
                                iconName: 'copy',
                                text: 'Copy Code',
                                popoverFeedback: (
                                    <StatusIndicator type='success'>
                                        {MESSAGES.COPY_CODE_SUCCESS}
                                    </StatusIndicator>
                                )
                            }
                        ]}
                        variant='icon'
                    />
                </div>
                <SyntaxHighlighter
                    style={UI_CONFIG.CODE_BLOCK_THEME}
                    language={language}
                    PreTag='div'
                >
                    {code}
                </SyntaxHighlighter>
            </div>
        );
    }, []);

    return (
        <SpaceBetween size='s'>
            <Box variant='h4' textAlign='center'>{modelName}</Box>
            <SpaceBetween direction='horizontal' size='m'>
                <ChatBubble
                    ariaLabel={ARIA_LABELS.MODEL_RESPONSE(modelName)}
                    type='incoming'
                    showLoadingBar={response.loading}
                    avatar={
                        <Avatar
                            loading={response.loading}
                            color='gen-ai'
                            iconName='gen-ai'
                            ariaLabel={modelName}
                            tooltipText={modelName}
                        />
                    }
                >
                    {response.loading ? (
                        <Box color='text-status-inactive'>
                            {MESSAGES.GENERATING_RESPONSE}
                        </Box>
                    ) : response.error ? (
                        <Alert type='error' header='Error'>
                            {response.error}
                        </Alert>
                    ) : (
                        <div style={{ maxWidth: UI_CONFIG.RESPONSE_MAX_WIDTH }}>
                            <ReactMarkdown
                                remarkPlugins={[remarkBreaks]}
                                children={response.response}
                                components={{
                                    code ({ className, children, ...props }: any) {
                                        const match = /language-(\w+)/.exec(className || '');
                                        const codeString = String(children).replace(/\n$/, '');

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
                                    ul ({ ...props }: any) {
                                        return <ul style={{ paddingLeft: '20px', marginTop: '8px', marginBottom: '8px', listStyleType: 'disc' }} {...props} />;
                                    },
                                    ol ({ ...props }: any) {
                                        return <ol style={{ paddingLeft: '20px', marginTop: '8px', marginBottom: '8px' }} {...props} />;
                                    },
                                    li ({ ...props }: any) {
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
                            ariaLabel={ARIA_LABELS.RESPONSE_ACTIONS}
                            dropdownExpandToViewport
                            items={[
                                {
                                    type: 'icon-button',
                                    id: 'copy',
                                    iconName: 'copy',
                                    text: 'Copy Response',
                                    popoverFeedback: (
                                        <StatusIndicator type='success'>
                                            {MESSAGES.COPY_RESPONSE_SUCCESS}
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
});

type ComparisonResultsProps = {
    prompt: string;
    responses: ComparisonResponse[];
    models: IModel[];
};

export const ComparisonResults = memo(function ComparisonResults ({ prompt, responses, models }: ComparisonResultsProps): ReactElement {
    return (
        <Container header={<Header variant='h2'>Comparison Results</Header>}>
            <SpaceBetween size='m'>
                {prompt && <UserPromptBubble prompt={prompt} />}
                <ColumnLayout columns={responses.length <= UI_CONFIG.GRID_BREAKPOINT ? responses.length : UI_CONFIG.GRID_BREAKPOINT}>
                    {responses.map((response) => {
                        const modelName = models.find((m) => m.modelId === response.modelId)?.modelName || response.modelId;
                        return (
                            <ModelResponseBubble
                                key={response.modelId}
                                response={response}
                                modelName={modelName}
                            />
                        );
                    })}
                </ColumnLayout>
            </SpaceBetween>
        </Container>
    );
});

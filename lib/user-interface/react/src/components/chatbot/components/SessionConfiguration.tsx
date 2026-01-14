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

import {
    AttributeEditor,
    Container,
    FormField,
    Grid,
    Header,
    Input,
    Modal,
    Select,
    SpaceBetween,
} from '@cloudscape-design/components';

import Toggle from '@cloudscape-design/components/toggle';
import { IChatConfiguration } from '@/shared/model/chat.configurations.model';
import { IModel, ModelType } from '@/shared/model/model-management.model';
import { IConfiguration } from '@/shared/model/configuration.model';
import { LisaChatSession } from '@/components/types';
import { ModelFeatures } from '@/components/types';

export type SessionConfigurationProps = {
    title?: string;
    chatConfiguration: IChatConfiguration;
    setChatConfiguration: (items: IChatConfiguration) => void;
    setVisible: (boolean) => void;
    visible: boolean;
    selectedModel: IModel;
    isRunning: boolean;
    systemConfig: IConfiguration;
    modelOnly?: boolean;
    session?: LisaChatSession;
    updateSession?: (session: LisaChatSession) => void;
    ragConfig?: any;
};

export const SessionConfiguration = ({
    title,
    chatConfiguration,
    setChatConfiguration,
    selectedModel,
    isRunning,
    visible,
    setVisible,
    systemConfig,
    modelOnly = false,
    session,
    updateSession,
    ragConfig
}: SessionConfigurationProps) => {
    // Defaults based on https://huggingface.co/docs/transformers/main_classes/text_generation#transformers.GenerationConfig
    // Default stop sequences based on User/Assistant instruction prompting for Falcon, Mistral, etc.

    const updateSessionConfiguration = (property: string, value: any): void => {
        const updatedConfiguration = {
            ...chatConfiguration,
            sessionConfiguration: { ...chatConfiguration.sessionConfiguration, [property]: value },
        };

        setChatConfiguration(updatedConfiguration);

        // Immediately persist the configuration to the session if available
        if (session && updateSession && session.history.length > 0) {
            updateSession({
                ...session,
                configuration: {
                    ...updatedConfiguration,
                    selectedModel: selectedModel,
                    ragConfig: ragConfig
                }
            });
        }
    };

    const oneThroughTenOptions = [...Array(10).keys()].map((i) => {
        i = i + 1;
        return {
            value: i.toString(),
            label: i.toString(),
        };
    });

    const reasoningEffortOptions = [
        { value: 'none', label: 'None' },
        { value: 'minimal', label: 'Minimal' },
        { value: 'low', label: 'Low' },
        { value: 'medium', label: 'Medium' },
        { value: 'high', label: 'High' },
        { value: 'xhigh', label: 'X-High' },
    ];
    const isImageModel = selectedModel?.modelType === ModelType.imagegen;

    return (
        <Modal
            onDismiss={() => setVisible(false)}
            visible={visible}
            header={<Header variant='h1'>{title || 'Session Configuration'}</Header>}
            footer=''
            size='large'
        >
            <SpaceBetween direction='vertical' size='l'>
                <Grid gridDefinition={[{ colspan: 6 }, { colspan: 6 }, { colspan: 6 }, { colspan: 6 }, { colspan: 6 }, { colspan: 6 }]}>
                    <Toggle
                        onChange={({ detail }) => updateSessionConfiguration('streaming', detail.checked)}
                        checked={chatConfiguration.sessionConfiguration.streaming}
                        disabled={!selectedModel?.streaming || isRunning}
                    >
                        Stream Responses
                    </Toggle>
                    <Toggle
                        onChange={({ detail }) => updateSessionConfiguration('markdownDisplay', detail.checked)}
                        checked={chatConfiguration.sessionConfiguration.markdownDisplay}
                    >
                        Display Responses as Markdown
                    </Toggle>
                    {systemConfig && systemConfig.configuration.enabledComponents.viewMetaData &&
                        <Toggle
                            onChange={({ detail }) => updateSessionConfiguration('showMetadata', detail.checked)}
                            checked={chatConfiguration.sessionConfiguration.showMetadata}
                            disabled={isRunning}
                        >
                            Show Message Metadata
                        </Toggle>}
                    {systemConfig && systemConfig.configuration.enabledComponents.editChatHistoryBuffer && !isImageModel && !modelOnly &&
                        <FormField label='Chat History Buffer Size'>
                            <Select
                                disabled={isRunning}
                                filteringType='auto'
                                selectedOption={{
                                    value: chatConfiguration.sessionConfiguration.chatHistoryBufferSize.toString(),
                                    label: chatConfiguration.sessionConfiguration.chatHistoryBufferSize.toString(),
                                }}
                                onChange={({ detail }) => updateSessionConfiguration('chatHistoryBufferSize', parseInt(detail.selectedOption.value))}
                                options={oneThroughTenOptions}
                            />
                        </FormField>}
                    {systemConfig && systemConfig.configuration.enabledComponents.editNumOfRagDocument && !isImageModel && !modelOnly &&
                        <FormField label='Matching RAG Excerpts'>
                            <Select
                                disabled={isRunning}
                                filteringType='auto'
                                selectedOption={{
                                    value: chatConfiguration.sessionConfiguration.ragTopK.toString(),
                                    label: chatConfiguration.sessionConfiguration.ragTopK.toString(),
                                }}
                                onChange={({ detail }) => updateSessionConfiguration('ragTopK', parseInt(detail.selectedOption.value))}
                                options={oneThroughTenOptions}
                            />
                        </FormField>}
                    {selectedModel?.features?.find((feature) => feature.name === ModelFeatures.REASONING) &&
                        <FormField label='Reasoning Effort'>
                            <Select
                                disabled={isRunning}
                                filteringType='auto'
                                selectedOption={{
                                    value: chatConfiguration.sessionConfiguration.modelArgs.reasoning_effort,
                                    label: chatConfiguration.sessionConfiguration.modelArgs.reasoning_effort,
                                }}
                                onChange={({ detail }) => updateSessionConfiguration('modelArgs', {...chatConfiguration.sessionConfiguration.modelArgs, reasoning_effort: detail.selectedOption.value })}
                                options={reasoningEffortOptions}
                            />
                        </FormField>}
                </Grid>
                {systemConfig && systemConfig.configuration.enabledComponents.editKwargs && !isImageModel &&
                    <Container
                        header={
                            <Header
                                variant='h2'
                            >
                                Model Args
                            </Header>
                        }
                    >
                        <FormField
                            label='Max Tokens'
                            constraintText='Must be greater than or equal to 0 - Defaults to null (no limit) if not specified.'
                            description='The maximum number of tokens that can be generated in the completion.'
                            controlId='max-tokens-input'
                        >
                            <Input
                                value={chatConfiguration.sessionConfiguration.max_tokens?.toString()}
                                type='number'
                                step={1}
                                inputMode='numeric'
                                disableBrowserAutocorrect={true}
                                onChange={(event) => {
                                    const intVal = parseInt(event.detail.value);
                                    if (!isNaN(intVal) && intVal >= 0) {
                                        updateSessionConfiguration('max_tokens', intVal);
                                    } else if (isNaN(intVal)) {
                                        updateSessionConfiguration('max_tokens', null);
                                    }
                                }}
                            />
                        </FormField>
                        <FormField
                            label='N'
                            constraintText='Must be greater than or equal to 1 - Defaults to null if not specified.'
                            description='How many completions to generate for each prompt.'
                        >
                            <Input
                                value={chatConfiguration.sessionConfiguration.modelArgs.n?.toString()}
                                type='number'
                                step={1}
                                inputMode='numeric'
                                disableBrowserAutocorrect={true}
                                onChange={(event) => {
                                    const intVal = parseInt(event.detail.value);
                                    if (!isNaN(intVal) && intVal >= 0) {
                                        updateSessionConfiguration('modelArgs', {
                                            ...chatConfiguration.sessionConfiguration.modelArgs,
                                            n: intVal,
                                        });
                                    } else if (isNaN(intVal)) {
                                        updateSessionConfiguration('modelArgs', {
                                            ...chatConfiguration.sessionConfiguration.modelArgs,
                                            n: null,
                                        });
                                    }
                                }}
                            />
                        </FormField>
                        <FormField
                            label='Top P'
                            constraintText='Must be between 0 and 1 - Defaults to 1 if not specified.'
                            description='An alternative to sampling with temperature,
                    called nucleus sampling, where the model considers
                    the results of the tokens with top_p probability mass.
                    So 0.1 means only the tokens comprising the top 10%
                    probability mass are considered.'
                        >
                            <Input
                                value={chatConfiguration.sessionConfiguration.modelArgs.top_p?.toString()}
                                type='number'
                                step={0.01}
                                inputMode='decimal'
                                disableBrowserAutocorrect={true}
                                onChange={(event) => {
                                    const floatVal = parseFloat(event.detail.value);
                                    if (!isNaN(floatVal) && floatVal >= 0.0 && floatVal <= 1.0) {
                                        updateSessionConfiguration('modelArgs', {
                                            ...chatConfiguration.sessionConfiguration.modelArgs,
                                            top_p: floatVal,
                                        });
                                    } else if (isNaN(floatVal)) {
                                        updateSessionConfiguration('modelArgs', {
                                            ...chatConfiguration.sessionConfiguration.modelArgs,
                                            top_p: null,
                                        });
                                    }
                                }}
                            />
                        </FormField>
                        <FormField
                            label='Frequency Penalty'
                            constraintText='Must be between -2.0 and 2.0 - Defaults to null if not specified.'
                            description="Number between -2.0 and 2.0. Positive values
                    penalize new tokens based on their existing
                    frequency in the text so far, decreasing the model's
                    likelihood to repeat the same line verbatim."
                        >
                            <Input
                                value={chatConfiguration.sessionConfiguration.modelArgs.frequency_penalty?.toString()}
                                type='number'
                                step={0.1}
                                inputMode='decimal'
                                disableBrowserAutocorrect={true}
                                onChange={(event) => {
                                    const floatVal = parseFloat(event.detail.value);
                                    if (!isNaN(floatVal) && floatVal >= -2.0 && floatVal <= 2.0) {
                                        updateSessionConfiguration('modelArgs', {
                                            ...chatConfiguration.sessionConfiguration.modelArgs,
                                            frequency_penalty: floatVal,
                                        });
                                    } else if (isNaN(floatVal)) {
                                        updateSessionConfiguration('modelArgs', {
                                            ...chatConfiguration.sessionConfiguration.modelArgs,
                                            frequency_penalty: null,
                                        });
                                    }
                                }}
                            />
                        </FormField>
                        <FormField
                            label='Presence Penalty'
                            constraintText='Must be between -2.0 and 2.0 - Defaults to null if not specified.'
                            description="Number between -2.0 and 2.0. Positive values
                      penalize new tokens based on whether they appear
                      in the text so far, increasing the model's
                      likelihood to talk about new topics."
                        >
                            <Input
                                value={chatConfiguration.sessionConfiguration.modelArgs.presence_penalty?.toString()}
                                type='number'
                                step={0.1}
                                inputMode='decimal'
                                disableBrowserAutocorrect={true}
                                onChange={(event) => {
                                    const floatVal = parseFloat(event.detail.value);
                                    if (!isNaN(floatVal) && floatVal >= -2.0 && floatVal <= 2.0) {
                                        updateSessionConfiguration('modelArgs', {
                                            ...chatConfiguration.sessionConfiguration.modelArgs,
                                            presence_penalty: floatVal,
                                        });
                                    } else if (isNaN(floatVal)) {
                                        updateSessionConfiguration('modelArgs', {
                                            ...chatConfiguration.sessionConfiguration.modelArgs,
                                            presence_penalty: null,
                                        });
                                    }
                                }}
                            />
                        </FormField>
                        <FormField
                            label='Temperature'
                            constraintText='Must be between 0 and 2.0 - Defaults to null if not specified.'
                            description='What sampling temperature to use, between 0 and 2.
                  Higher values like 0.8 will make the output more random,
                  while lower values like 0.2 will make it more focused
                  and deterministic.'
                        >
                            <Input
                                value={chatConfiguration.sessionConfiguration.modelArgs.temperature?.toString()}
                                type='number'
                                step={0.1}
                                inputMode='decimal'
                                disableBrowserAutocorrect={true}
                                onChange={(event) => {
                                    const floatVal = parseFloat(event.detail.value);
                                    if (!isNaN(floatVal) && floatVal >= 0.0 && floatVal <= 2.0) {
                                        updateSessionConfiguration('modelArgs', {
                                            ...chatConfiguration.sessionConfiguration.modelArgs,
                                            temperature: floatVal,
                                        });
                                    } else if (isNaN(floatVal)) {
                                        updateSessionConfiguration('modelArgs', {
                                            ...chatConfiguration.sessionConfiguration.modelArgs,
                                            temperature: null,
                                        });
                                    }
                                }}
                            />
                        </FormField>
                        {!modelOnly &&
                            <SpaceBetween size='s'>
                                <Header variant='h3' description='Up to 4 sequences where the API will stop generating further tokens.'>
                                    Stop
                                </Header>
                                <AttributeEditor
                                    addButtonText='Add'
                                    onAddButtonClick={() => {
                                        if (chatConfiguration.sessionConfiguration.modelArgs.stop.length < 4) {
                                            updateSessionConfiguration('modelArgs', {
                                                ...chatConfiguration.sessionConfiguration.modelArgs,
                                                stop: chatConfiguration.sessionConfiguration.modelArgs.stop.concat(''),
                                            });
                                        }
                                    }}
                                    removeButtonText='Remove'
                                    onRemoveButtonClick={(event) =>
                                        updateSessionConfiguration('modelArgs', {
                                            ...chatConfiguration.sessionConfiguration.modelArgs,
                                            stop: chatConfiguration.sessionConfiguration.modelArgs.stop.filter((elem, i) => event.detail.itemIndex !== i),
                                        })
                                    }
                                    isItemRemovable={() => true}
                                    items={chatConfiguration.sessionConfiguration.modelArgs.stop}
                                    definition={[
                                        {
                                            control: (item, i) => {
                                                return (
                                                    <Input
                                                        value={item}
                                                        placeholder='null'
                                                        onChange={(event) => {
                                                            updateSessionConfiguration('modelArgs',
                                                                {
                                                                    ...chatConfiguration.sessionConfiguration.modelArgs,
                                                                    stop: chatConfiguration.sessionConfiguration.modelArgs.stop.slice(0, 4)
                                                                        .map((elem, j) => {
                                                                            if (i === j) {
                                                                                return event.detail.value;
                                                                            } else {
                                                                                return elem;
                                                                            }
                                                                        }),
                                                                });
                                                        }}
                                                    />
                                                );
                                            },
                                        },
                                    ]}
                                    empty='No stop sequences provided.'
                                />
                            </SpaceBetween>
                        }
                        {!modelOnly && <FormField
                            label='Seed'
                            description='If specified, our system will make a best
                      effort to sample deterministically, such that
                      repeated requests with the same seed and
                      parameters should return the same result.'
                        >
                            <Input
                                value={chatConfiguration.sessionConfiguration.modelArgs.seed?.toString()}
                                type='number'
                                step={1}
                                inputMode='numeric'
                                disableBrowserAutocorrect={true}
                                onChange={(event) => {
                                    const intVal = parseInt(event.detail.value);
                                    if (!isNaN(intVal) && intVal >= 0) {
                                        updateSessionConfiguration('modelArgs', {
                                            ...chatConfiguration.sessionConfiguration.modelArgs,
                                            seed: intVal,
                                        });
                                    } else if (isNaN(intVal)) {
                                        updateSessionConfiguration('modelArgs', {
                                            ...chatConfiguration.sessionConfiguration.modelArgs,
                                            seed: null,
                                        });
                                    }
                                }}
                            />
                        </FormField>
                        }
                    </Container>}
                {isImageModel && (
                    <Container
                        header={
                            <Header
                                variant='h2'
                            >
                                Image Generation Model Args
                            </Header>
                        }
                    >
                        <FormField label='Image Size'>
                            <Select
                                selectedOption={{ value: chatConfiguration.sessionConfiguration.imageGenerationArgs.size }}
                                onChange={({ detail }) => {
                                    updateSessionConfiguration('imageGenerationArgs', {
                                        ...chatConfiguration.sessionConfiguration.imageGenerationArgs,
                                        size: detail.selectedOption.value,
                                    });
                                }}
                                options={[
                                    { label: '1024x1024 (Square)', value: '1024x1024' },
                                    { label: '1024x1792 (Portrait)', value: '1024x1792' },
                                    { label: '1792x1024 (Landscape)', value: '1792x1024' },
                                ]}
                            />
                        </FormField>
                        <FormField label='Image Quality'>
                            <Select
                                selectedOption={{ value: chatConfiguration.sessionConfiguration.imageGenerationArgs.quality }}
                                onChange={({ detail }) => {
                                    updateSessionConfiguration('imageGenerationArgs', {
                                        ...chatConfiguration.sessionConfiguration.imageGenerationArgs,
                                        quality: detail.selectedOption.value,
                                    });
                                }}
                                options={[
                                    { label: 'Standard', value: 'standard' },
                                    { label: 'HD', value: 'hd' },
                                ]}
                            />
                        </FormField>
                        <FormField label='Number of Images'>
                            <Select
                                selectedOption={{ value: String(chatConfiguration.sessionConfiguration.imageGenerationArgs.numberOfImages) }}
                                onChange={({ detail }) => {
                                    updateSessionConfiguration('imageGenerationArgs', {
                                        ...chatConfiguration.sessionConfiguration.imageGenerationArgs,
                                        numberOfImages: Number(detail.selectedOption.value),
                                    });
                                }}
                                options={
                                    Array.from({ length: 5 }, (_, i) => i + 1).map((i) => {
                                        return { label: String(i), value: String(i) };
                                    })
                                }
                            />
                        </FormField>
                    </Container>
                )}
            </SpaceBetween>
        </Modal>
    );
};

export default SessionConfiguration;

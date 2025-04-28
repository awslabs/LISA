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
    Box,
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
import { IChatConfiguration } from '../../shared/model/chat.configurations.model';
import { IModel, ModelType } from '../../shared/model/model-management.model';
import { IConfiguration } from '../../shared/model/configuration.model';

export type SessionConfigurationProps = {
    chatConfiguration: IChatConfiguration;
    setChatConfiguration: (items: IChatConfiguration) => void;
    setVisible: (boolean) => void;
    visible: boolean;
    selectedModel: IModel;
    isRunning: boolean;
    systemConfig: IConfiguration;
};

export default function SessionConfiguration ({
    chatConfiguration,
    setChatConfiguration,
    selectedModel,
    isRunning,
    visible,
    setVisible,
    systemConfig,
}: SessionConfigurationProps) {
    // Defaults based on https://huggingface.co/docs/transformers/main_classes/text_generation#transformers.GenerationConfig
    // Default stop sequences based on User/Assistant instruction prompting for Falcon, Mistral, etc.

    const updateSessionConfiguration = (property: string, value: any): void => {
        setChatConfiguration({
            ...chatConfiguration,
            sessionConfiguration: { ...chatConfiguration.sessionConfiguration, [property]: value },
        });
    };

    const oneThroughTenOptions = [...Array(10).keys()].map((i) => {
        i = i + 1;
        return {
            value: i.toString(),
            label: i.toString(),
        };
    });

    const isImageModel = selectedModel?.modelType === ModelType.imagegen;

    return (
        <Modal
            onDismiss={() => setVisible(false)}
            visible={visible}
            header={<Header variant='h1'>Session Configuration</Header>}
            footer=''
            size='large'
        >
            <SpaceBetween direction='vertical' size='l'>
                <Grid gridDefinition={[{ colspan: 6 }, { colspan: 6 }, { colspan: 6 }, { colspan: 6 }]}>
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
                    {systemConfig && systemConfig.configuration.enabledComponents.editChatHistoryBuffer && !isImageModel &&
                        <SpaceBetween size={'s'} direction={'horizontal'}>
                            <Box float='left' textAlign='center' variant='awsui-key-label'
                                padding={{ vertical: 'xxs' }}>
                                <label>Chat History Buffer Size:</label>
                            </Box>
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
                        </SpaceBetween>}
                    {systemConfig && systemConfig.configuration.enabledComponents.editNumOfRagDocument && !isImageModel &&
                        <SpaceBetween size={'s'} direction={'horizontal'}>
                            <Box float='left' textAlign='center' variant='awsui-key-label'
                                padding={{ vertical: 'xxs' }}>
                                <label>RAG references:</label>
                            </Box>
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
                        </SpaceBetween>}
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
                        <FormField label='Stop'
                            description='Up to 4 sequences where the API will stop generating further tokens.'>
                            <Container>
                                <AttributeEditor
                                    addButtonText='Add'
                                    onAddButtonClick={() => updateSessionConfiguration('modelArgs', {
                                        ...chatConfiguration.sessionConfiguration.modelArgs,
                                        stop: chatConfiguration.sessionConfiguration.modelArgs.stop.concat(''),
                                    })}
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
                            </Container>
                        </FormField>
                        <FormField
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
                    </Container>}
            </SpaceBetween>
        </Modal>
    );
}

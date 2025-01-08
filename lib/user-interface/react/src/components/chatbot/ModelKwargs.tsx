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

import { useEffect, useState } from 'react';

import {
    AttributeEditor,
    Modal,
    Container,
    SpaceBetween,
    Input,
    Header,
    FormField,
} from '@cloudscape-design/components';
import unraw from 'unraw';

import { ModelConfig } from '../types';

export default function ModelKwargsEditor ({ setModelConfig, visible, setVisible }) {
    // Defaults based on https://huggingface.co/docs/transformers/main_classes/text_generation#transformers.GenerationConfig
    // Default stop sequences based on User/Assistant instruction prompting for Falcon, Mistral, etc.
    const [maxNewTokens, setMaxNewTokens] = useState(null);
    const [n, setN] = useState(null);
    const [topP, setTopP] = useState(0.01);
    const [frequencyPenalty, setFrequencyPenalty] = useState(null);
    const [presencePenalty, setPresencePenalty] = useState(null);
    const [temperature, setTemperature] = useState(null);
    const [seed, setSeed] = useState(null);
    const [stopSequences, setStopSequences] = useState(['\nUser:', '\n User:', 'User:', 'User']);

    useEffect(() => {
        const modelConfig: ModelConfig = {
            max_tokens: maxNewTokens,
            modelKwargs: {
                n: n,
                top_p: topP,
                frequency_penalty: frequencyPenalty,
                presence_penalty: presencePenalty,
                temperature: temperature,
                stop: stopSequences.map((elem) => {
                    try {
                        return unraw(elem);
                    } catch (error) {
                        return elem;
                    }
                }),
                seed,
            },
        };
        setModelConfig(modelConfig);
    //Disabling exhaustive-deps here because we reference and update modelKwargs in the same hook
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [maxNewTokens, n, topP, frequencyPenalty, presencePenalty, temperature, stopSequences, seed]);
    return (
        <Modal
            onDismiss={() => setVisible(false)}
            visible={visible}
            header={<Header variant='h1'>Edit model kwargs</Header>}
            footer=''
            size='large'
        >
            <SpaceBetween direction='vertical' size='l'>
                <FormField
                    label='Max Tokens'
                    constraintText='Must be greater than or equal to 0 - Defaults to null (no limit) if not specified.'
                    description='The maximum number of tokens that can be generated in the completion.'
                >
                    <Input
                        value={maxNewTokens?.toString()}
                        type='number'
                        step={1}
                        inputMode='numeric'
                        disableBrowserAutocorrect={true}
                        onChange={(event) => {
                            const intVal = parseInt(event.detail.value);
                            if (!isNaN(intVal) && intVal >= 0) {
                                setMaxNewTokens(intVal);
                            } else if (isNaN(intVal)) {
                                setMaxNewTokens(null);
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
                        value={n?.toString()}
                        type='number'
                        step={1}
                        inputMode='numeric'
                        disableBrowserAutocorrect={true}
                        onChange={(event) => {
                            const intVal = parseInt(event.detail.value);
                            if (!isNaN(intVal) && intVal >= 0) {
                                setN(intVal);
                            } else if (isNaN(intVal)) {
                                setN(null);
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
                        value={topP?.toString()}
                        type='number'
                        step={0.01}
                        inputMode='decimal'
                        disableBrowserAutocorrect={true}
                        onChange={(event) => {
                            const floatVal = parseFloat(event.detail.value);
                            if (!isNaN(floatVal) && floatVal >= 0.0 && floatVal <= 1.0) {
                                setTopP(floatVal);
                            } else if (isNaN(floatVal)) {
                                setTopP(null);
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
                        value={frequencyPenalty?.toString()}
                        type='number'
                        step={0.1}
                        inputMode='decimal'
                        disableBrowserAutocorrect={true}
                        onChange={(event) => {
                            const floatVal = parseFloat(event.detail.value);
                            if (!isNaN(floatVal) && floatVal >= -2.0 && floatVal <= 2.0) {
                                setFrequencyPenalty(floatVal);
                            } else if (isNaN(floatVal)) {
                                setFrequencyPenalty(null);
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
                        value={presencePenalty?.toString()}
                        type='number'
                        step={0.1}
                        inputMode='decimal'
                        disableBrowserAutocorrect={true}
                        onChange={(event) => {
                            const floatVal = parseFloat(event.detail.value);
                            if (!isNaN(floatVal) && floatVal >= -2.0 && floatVal <= 2.0) {
                                setPresencePenalty(floatVal);
                            } else if (isNaN(floatVal)) {
                                setPresencePenalty(null);
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
                        value={temperature?.toString()}
                        type='number'
                        step={0.1}
                        inputMode='decimal'
                        disableBrowserAutocorrect={true}
                        onChange={(event) => {
                            const floatVal = parseFloat(event.detail.value);
                            if (!isNaN(floatVal) && floatVal >= 0.0 && floatVal <= 2.0) {
                                setTemperature(floatVal);
                            } else if (isNaN(floatVal)) {
                                setTemperature(null);
                            }
                        }}
                    />
                </FormField>
                <FormField label='Stop Word(s)' description='Up to 4 sequences where the API will stop generating further tokens.'>
                    <Container>
                        <AttributeEditor
                            addButtonText='Add'
                            onAddButtonClick={() => setStopSequences((prev) => prev.concat(''))}
                            removeButtonText='Remove'
                            onRemoveButtonClick={(event) =>
                                setStopSequences((prev) => prev.filter((elem, i) => event.detail.itemIndex !== i))
                            }
                            isItemRemovable={() => true}
                            items={stopSequences}
                            definition={[
                                {
                                    control: (item, i) => {
                                        return (
                                            <Input
                                                value={item}
                                                placeholder='null'
                                                onChange={(event) => {
                                                    setStopSequences((prev) =>
                                                        prev.slice(0, 4).map((elem, j) => {
                                                            if (i === j) {
                                                                return event.detail.value;
                                                            } else {
                                                                return elem;
                                                            }
                                                        }),
                                                    );
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
                        value={seed?.toString()}
                        type='number'
                        step={1}
                        inputMode='numeric'
                        disableBrowserAutocorrect={true}
                        onChange={(event) => {
                            const intVal = parseInt(event.detail.value);
                            if (!isNaN(intVal) && intVal >= 0) {
                                setSeed(intVal);
                            } else if (isNaN(intVal)) {
                                setSeed(null);
                            }
                        }}
                    />
                </FormField>
            </SpaceBetween>
        </Modal>
    );
}

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
  Toggle,
  Link,
  Container,
  SpaceBetween,
  Input,
  Header,
  FormField,
} from '@cloudscape-design/components';
import unraw from 'unraw';

import { ModelKwargs } from '../types';

export default function ModelKwargsEditor({ setModelKwargs, visible, setVisible }) {
  // Defaults based on https://huggingface.co/docs/transformers/main_classes/text_generation#transformers.GenerationConfig
  // Default stop sequences based on User/Assistant instruction prompting for Falcon, Mistral, etc.
  const [maxNewTokens, setMaxNewTokens] = useState(1024);
  const [topK, setTopK] = useState(50);
  const [topP, setTopP] = useState(0.99); // TGI client enforces strictly less than 1.0
  const [typicalP, setTypicalP] = useState(0.99); // TGI client enforces strictly less than 1.0
  const [temperature, setTemperature] = useState(1.0);
  const [repetitionPenalty, setRepetitionPenalty] = useState(1.0);
  const [returnFullText, setReturnFullText] = useState(false);
  const [watermark, setWatermark] = useState(false);
  const [doSample, setDoSample] = useState(false);
  const [truncate, setTruncate] = useState(1024);
  const [seed, setSeed] = useState(42);
  const [stopSequences, setStopSequences] = useState(['\nUser:', '\n User:', 'User:', 'User']);

  useEffect(() => {
    const modelKwargs: ModelKwargs = {
      max_new_tokens: maxNewTokens,
      top_k: topK,
      top_p: topP,
      typical_p: typicalP,
      temperature: temperature,
      repetition_penalty: repetitionPenalty,
      return_full_text: returnFullText,
      truncate: truncate,
      stop_sequences: stopSequences.map((elem) => {
        try {
          return unraw(elem);
        } catch (error) {
          return elem;
        }
      }),
      seed: seed,
      do_sample: doSample,
      watermark: watermark,
    };
    setModelKwargs(modelKwargs);
    //Disabling exhaustive-deps here because we reference and update modelKwargs in the same hook
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    maxNewTokens,
    topK,
    topP,
    typicalP,
    temperature,
    repetitionPenalty,
    returnFullText,
    truncate,
    stopSequences,
    seed,
    doSample,
    watermark,
  ]);
  return (
    <Modal
      onDismiss={() => setVisible(false)}
      visible={visible}
      header={<Header variant="h1">Edit model kwargs</Header>}
      footer=""
      size="large"
    >
      <SpaceBetween direction="vertical" size="l">
        <FormField
          label="max_new_tokens"
          constraintText="Must be greater than or equal to 0."
          description="The maximum number of new tokens to generate."
        >
          <Input
            value={maxNewTokens.toString()}
            type="number"
            step={1}
            inputMode="numeric"
            disableBrowserAutocorrect={true}
            onChange={(event) => {
              const intVal = parseInt(event.detail.value);
              if (intVal >= 0) {
                setMaxNewTokens(intVal);
              }
            }}
          />
        </FormField>
        <FormField
          label="top_k"
          constraintText="Must be greater than or equal to 1."
          description="The number of highest probability vocabulary tokens to keep for top-k-filtering. Value of 1 corresponds to greedy strategy."
        >
          <Input
            value={topK.toString()}
            type="number"
            step={1}
            inputMode="numeric"
            disableBrowserAutocorrect={true}
            onChange={(event) => {
              const intVal = parseInt(event.detail.value);
              if (intVal >= 0) {
                setTopK(intVal);
              }
            }}
          />
        </FormField>
        <FormField
          label="top_p"
          constraintText="Must be between 0 and 1"
          description="If set to < 1, only the smallest set of most probable
                    tokens with probabilities that add up to `top_p` or
                    higher are kept for generation"
        >
          <Input
            value={topP.toString()}
            type="number"
            step={0.1}
            inputMode="decimal"
            disableBrowserAutocorrect={true}
            onChange={(event) => {
              const floatVal = parseFloat(event.detail.value);
              if (floatVal >= 0.0 && floatVal <= 1.0) {
                setTopP(floatVal);
              }
            }}
          />
        </FormField>
        <FormField
          label="typical_p"
          constraintText="Must be between 0 and 1"
          description={
            <div>
              <SpaceBetween direction="horizontal" size="xs">
                <span>Typical Decoding Mass</span>
                <Link external variant="info" href="https://arxiv.org/pdf/2202.00666.pdf">
                  Learn more
                </Link>
              </SpaceBetween>
            </div>
          }
        >
          <Input
            value={typicalP.toString()}
            type="number"
            step={0.1}
            inputMode="decimal"
            disableBrowserAutocorrect={true}
            onChange={(event) => {
              const floatVal = parseFloat(event.detail.value);
              if (floatVal >= 0.0 && floatVal <= 1.0) {
                setTypicalP(floatVal);
              }
            }}
          />
        </FormField>
        <FormField
          label="temperature"
          constraintText="Must be greater than 0"
          description="Controls temperature used to modulate token probabilities."
        >
          <Input
            value={temperature.toString()}
            type="number"
            step={0.1}
            inputMode="decimal"
            disableBrowserAutocorrect={true}
            onChange={(event) => {
              const floatVal = parseFloat(event.detail.value);
              if (floatVal >= 0.0) {
                setTemperature(floatVal);
              }
            }}
          />
        </FormField>
        <FormField
          label="repetition_penalty"
          description={
            <div>
              <SpaceBetween direction="horizontal" size="xs">
                <span>The parameter for repetition penalty. 1.0 means no penalty.</span>
                <Link external variant="info" href="https://arxiv.org/pdf/1909.05858.pdf">
                  Learn more
                </Link>
              </SpaceBetween>
            </div>
          }
        >
          <Input
            value={repetitionPenalty.toString()}
            type="number"
            step={0.1}
            inputMode="decimal"
            disableBrowserAutocorrect={true}
            onChange={(event) => {
              setRepetitionPenalty(parseFloat(event.detail.value));
            }}
          />
        </FormField>
        <FormField
          label="truncate"
          constraintText="Must be greater than 0."
          description="Truncate inputs tokens to the given size."
        >
          <Input
            value={truncate.toString()}
            type="number"
            step={1}
            inputMode="numeric"
            disableBrowserAutocorrect={true}
            onChange={(event) => {
              const intVal = parseInt(event.detail.value);
              if (intVal >= 0) {
                setTruncate(intVal);
              }
            }}
          />
        </FormField>
        <FormField
          label="stop_sequences"
          //TODO: this is hardcoded at 4 stop tokens (default in TGI) but maybe this should be a config option?
          description="Stop generating tokens if a member of `stop_sequences` is generated. Maximum of 4."
        >
          <Container>
            <AttributeEditor
              addButtonText="Add"
              onAddButtonClick={() => setStopSequences((prev) => prev.concat(''))}
              removeButtonText="Remove"
              onRemoveButtonClick={(event) =>
                setStopSequences((prev) => prev.filter((elem, i) => event.detail.itemIndex != i))
              }
              isItemRemovable={() => true}
              items={stopSequences}
              definition={[
                {
                  control: (item, i) => {
                    return (
                      <Input
                        value={item}
                        placeholder="null"
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
              empty="No stop sequences provided."
            />
          </Container>
        </FormField>
        <FormField label="seed" description="Random sampling seed">
          <Input
            value={seed.toString()}
            type="number"
            step={1}
            inputMode="numeric"
            disableBrowserAutocorrect={true}
            onChange={(event) => {
              const intVal = parseInt(event.detail.value);
              if (intVal >= 0) {
                setSeed(intVal);
              }
            }}
          />
        </FormField>
        <FormField label="return_full_text" description="Whether to prepend the prompt to the generated text.">
          <Toggle
            checked={returnFullText}
            onChange={(event) => {
              setReturnFullText(event.detail.checked);
            }}
          />
        </FormField>
        <FormField label="do_sample" description="Activate logits sampling">
          <Toggle
            checked={doSample}
            onChange={(event) => {
              setDoSample(event.detail.checked);
            }}
          />
        </FormField>
        <FormField
          label="watermark"
          description={
            <div>
              <SpaceBetween direction="horizontal" size="xs">
                <span>Whether to apply watermarking.</span>
                <Link external variant="info" href="https://arxiv.org/pdf/2301.10226.pdf">
                  Learn more
                </Link>
              </SpaceBetween>
            </div>
          }
        >
          <Toggle
            checked={watermark}
            onChange={(event) => {
              setWatermark(event.detail.checked);
            }}
          />
        </FormField>
      </SpaceBetween>
    </Modal>
  );
}

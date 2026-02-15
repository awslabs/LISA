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

import { ReactElement, useEffect } from 'react';
import { FormProps} from '../../../shared/form/form-props';
import FormField from '@cloudscape-design/components/form-field';
import Input from '@cloudscape-design/components/input';
import Toggle from '@cloudscape-design/components/toggle';
import Select from '@cloudscape-design/components/select';
import { IModelRequest, InferenceContainer, ModelType } from '../../../shared/model/model-management.model';
import { Grid, SpaceBetween } from '@cloudscape-design/components';
import { useGetInstancesQuery } from '../../../shared/reducers/model-management.reducer';
import { ModelFeatures } from '@/components/types';
import { UserGroupsInput } from '@/shared/form/UserGroupsInput';
import { getDisplayName } from '../../../shared/util/branding';

export type BaseModelConfigCustomProps = {
    isEdit: boolean
};

export function BaseModelConfig (props: FormProps<IModelRequest> & BaseModelConfigCustomProps) : ReactElement {
    const {data: instances, isLoading: isLoadingInstances} = useGetInstancesQuery();
    const isEmbeddingModel = props.item.modelType === ModelType.embedding;
    const isImageModel = props.item.modelType === ModelType.imagegen;
    const isVideoModel = props.item.modelType === ModelType.videogen;

    // Enable streaming by default for textgen models when creating a new model
    useEffect(() => {
        if (!props.isEdit && props.item.modelType === ModelType.textgen && props.item.streaming === false) {
            props.setFields({ 'streaming': true });
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [props.isEdit, props.item.modelType]);

    return (
        <SpaceBetween size={'s'}>
            <FormField
                label='Hosting Type'
                description={`Choose whether to host the model on ${getDisplayName()} infrastructure or use a third-party provider.`}
                errorText={props.formErrors?.lisaHostedModel}
            >
                <Select
                    selectedOption={{
                        label: props.item.lisaHostedModel ? 'LISA Hosted' : 'Third Party',
                        value: props.item.lisaHostedModel ? 'true' : 'false'
                    }}
                    onChange={({ detail }) => {
                        const isLisaHosted = detail.selectedOption.value === 'true';
                        const fieldsToUpdate = { 'lisaHostedModel': isLisaHosted };

                        // If switching to Third Party, clear LISA Hosted specific fields
                        if (!isLisaHosted) {
                            fieldsToUpdate['instanceType'] = undefined;
                            fieldsToUpdate['inferenceContainer'] = undefined;
                        }
                        props.setFields(fieldsToUpdate);
                    }}
                    onBlur={() => props.touchFields(['lisaHostedModel'])}
                    options={[
                        { label: 'Third party', value: 'false' },
                        { label: `${getDisplayName()} hosted`, value: 'true' }
                    ]}
                    disabled={props.isEdit}
                />
            </FormField>
            <FormField label='Model ID' errorText={props.formErrors?.modelId} description='The unique model IDs are displayed to users in the "Select a model" drop down. We recommend using a descriptive name like "claude-3-7" or "nova-imagegen"'>
                <Input value={props.item.modelId} inputMode='text' onBlur={() => props.touchFields(['modelId'])} onChange={({ detail }) => {
                    props.setFields({ 'modelId': detail.value });
                }} disabled={props.isEdit} placeholder='mistral-vllm'/>
            </FormField>
            <FormField label='Model Name' errorText={props.formErrors?.modelName}
                description='The full model name is the repository path, or the third party model provider path. The path format typically will be: {ProviderPath}/{ProviderModelName}. Users do not see this value in the chat assistant user interface.'>
                <Input value={props.item.modelName} inputMode='text' onBlur={() => props.touchFields(['modelName'])} onChange={({ detail }) => {
                    props.setFields({ 'modelName': detail.value });
                }} disabled={props.isEdit} placeholder='mistralai/Mistral-7B-Instruct-v0.2'/>
            </FormField>
            <FormField
                label={<span>Model Description <em>- Optional</em></span>}
                description='Brief description of the model capabilities, use cases, and characteristics.'
                errorText={props.formErrors?.modelDescription}
            >
                <Input value={props.item.modelDescription || ''} inputMode='text' onBlur={() => props.touchFields(['modelDescription'])} onChange={({ detail }) => {
                    props.setFields({ 'modelDescription': detail.value });
                }} placeholder='Brief description of the model and its capabilities'/>
            </FormField>
            {!props.item.lisaHostedModel && <FormField
                label={<span>API Key <em>- Optional</em></span>}
                description='API authentication key for accessing third-party model provider services.'
                errorText={props.formErrors?.apiKey}
            >
                <Input value={props.item.apiKey} inputMode='text' onBlur={() => props.touchFields(['apiKey'])} onChange={({ detail }) => {
                    props.setFields({ 'apiKey': detail.value });
                }} disabled={props.isEdit} placeholder='sk-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'/>
            </FormField>}
            <FormField
                label={<span>Model URL <em>- Optional</em></span>}
                description='Custom endpoint URL for the model API (e.g., for self-hosted or third-party services).'
                errorText={props.formErrors?.modelUrl}
            >
                <Input value={props.item.modelUrl} inputMode='text' onBlur={() => props.touchFields(['modelUrl'])} onChange={({ detail }) => {
                    props.setFields({ 'modelUrl': detail.value });
                }} disabled={props.isEdit} placeholder='http://internal-lisa-gptoss20b-123456789.us-west-2.elb.amazonaws.com'/>
            </FormField>
            <FormField
                label='Model Type'
                description='Type of model functionality: text generation, image generation, video generation, or text embeddings.'
                errorText={props.formErrors?.modelType}
            >
                <Select
                    selectedOption={{label: props.item.modelType.toUpperCase(), value: props.item.modelType}}
                    onChange={({ detail }) => {
                        const fields = {
                            'modelType': detail.selectedOption.value,
                        };

                        // enable streaming by default for textgen models
                        if (fields.modelType === ModelType.textgen) {
                            fields['streaming'] = true;
                        } else if (fields.modelType === ModelType.embedding || fields.modelType === ModelType.imagegen || fields.modelType === ModelType.videogen) {
                            fields['streaming'] = false;
                        }

                        // turn off summarization and image input for embedded and imagegen models
                        if ((fields.modelType === ModelType.embedding || fields.modelType === ModelType.imagegen || fields.modelType === ModelType.videogen)) {
                            fields['features'] = props.item.features.filter((feature) => feature.name !== ModelFeatures.SUMMARIZATION && feature.name !== ModelFeatures.IMAGE_INPUT && feature.name !== ModelFeatures.TOOL_CALLS);
                        }

                        props.setFields(fields);
                    }}
                    onBlur={() => props.touchFields(['modelType'])}
                    options={[
                        { label: 'TEXTGEN', value: ModelType.textgen },
                        { label: 'IMAGEGEN', value: ModelType.imagegen },
                        { label: 'VIDEOGEN', value: ModelType.videogen },
                        { label: 'EMBEDDING', value: ModelType.embedding },
                    ]}
                    disabled={props.isEdit}
                />
            </FormField>
            {isEmbeddingModel && (
                <>
                    <FormField
                        label={<span>Embedding Query Prefix <em>- Optional</em></span>}
                        description='Prefix prepended to query text before embedding for retrieval. Common values: "query: " (E5), "Represent this sentence for searching relevant passages: " (BGE).'
                        errorText={props.formErrors?.embeddingQueryPrefix}
                    >
                        <Input
                            value={props.item.embeddingQueryPrefix || ''}
                            inputMode='text'
                            onBlur={() => props.touchFields(['embeddingQueryPrefix'])}
                            onChange={({ detail }) => {
                                props.setFields({ 'embeddingQueryPrefix': detail.value });
                            }}
                            placeholder='e.g. query: '
                        />
                    </FormField>
                    <FormField
                        label={<span>Embedding Document Prefix <em>- Optional</em></span>}
                        description='Prefix prepended to document text before embedding for indexing. Common values: "passage: " (E5). Leave empty if the model does not require a document prefix.'
                        errorText={props.formErrors?.embeddingDocumentPrefix}
                    >
                        <Input
                            value={props.item.embeddingDocumentPrefix || ''}
                            inputMode='text'
                            onBlur={() => props.touchFields(['embeddingDocumentPrefix'])}
                            onChange={({ detail }) => {
                                props.setFields({ 'embeddingDocumentPrefix': detail.value });
                            }}
                            placeholder='e.g. passage: '
                        />
                    </FormField>
                </>
            )}
            {props.item.lisaHostedModel && (
                <>
                    <FormField
                        label='Instance Type'
                        description='EC2 instance type for hosting the model. Choose based on model size and performance requirements.'
                        errorText={props.formErrors?.instanceType}
                    >
                        <Select
                            options={(instances || []).map((instance) => ({value: instance}))}
                            selectedOption={{value: props.item.instanceType}}
                            loadingText='Loading instances'
                            disabled={props.isEdit}
                            onBlur={() => props.touchFields(['instanceType'])}
                            onChange={({ detail }) => {
                                props.setFields({ 'instanceType': detail.selectedOption.value });
                            }}
                            filteringType='auto'
                            statusType={ isLoadingInstances ? 'loading' : 'finished'}
                            virtualScroll
                        />
                    </FormField>
                    <FormField
                        label='Inference Container'
                        description='Container runtime for model inference (TGI for text generation, TEI for embeddings, vLLM for optimized inference).'
                        errorText={props.formErrors?.inferenceContainer}
                    >
                        <Select
                            selectedOption={{label: props.item.inferenceContainer?.toUpperCase(), value: props.item.inferenceContainer}}
                            onBlur={() => props.touchFields(['inferenceContainer'])}
                            onChange={({ detail }) =>
                                props.setFields({
                                    'inferenceContainer': detail.selectedOption.value,
                                })
                            }
                            options={[
                                { label: 'TGI', value: InferenceContainer.TGI },
                                { label: 'TEI', value: InferenceContainer.TEI },
                                { label: 'VLLM', value: InferenceContainer.VLLM },
                            ]}
                            disabled={props.isEdit}
                        />
                    </FormField>
                </>
            )}
            <Grid gridDefinition={[{ colspan: 6 }, { colspan: 6 }, { colspan: 6 }, { colspan: 6 }]}>
                <FormField
                    label='Streaming'
                    description='Enable streaming responses for real-time token-by-token output generation.'
                    errorText={props.formErrors?.streaming}
                >
                    <Toggle
                        data-testid='streaming-toggle'
                        onChange={({ detail }) =>
                            props.setFields({'streaming': detail.checked})
                        }
                        onBlur={() => props.touchFields(['streaming'])}
                        disabled={isEmbeddingModel || isImageModel || isVideoModel}
                        checked={props.item.streaming}
                    />
                </FormField>
                <FormField
                    label='Tool Calls'
                    description='Enable function calling capabilities for the model to use external tools and APIs.'
                    errorText={props.formErrors?.features}
                >
                    <Toggle
                        onChange={({ detail }) => {
                            if (detail.checked && props.item.features.find((feature) => feature.name === ModelFeatures.TOOL_CALLS) === undefined) {
                                props.setFields({'features': props.item.features.concat({name: ModelFeatures.TOOL_CALLS, overview: ''})});
                            } else if (!detail.checked && props.item.features.find((feature) => feature.name === ModelFeatures.TOOL_CALLS) !== undefined) {
                                props.setFields({'features': props.item.features.filter((feature) => feature.name !== ModelFeatures.TOOL_CALLS)});
                            }
                        }}
                        disabled={isEmbeddingModel || isImageModel || isVideoModel}
                        onBlur={() => props.touchFields(['features'])}
                        checked={props.item.features.find((feature) => feature.name === ModelFeatures.TOOL_CALLS) !== undefined}
                    />
                </FormField>
                <FormField
                    label='Reasoning'
                    description='Enable reasoning output capabilities for the model.'
                    errorText={props.formErrors?.features}
                >
                    <Toggle
                        onChange={({ detail }) => {
                            if (detail.checked && props.item.features.find((feature) => feature.name === ModelFeatures.REASONING) === undefined) {
                                props.setFields({'features': props.item.features.concat({name: ModelFeatures.REASONING, overview: ''})});
                            } else if (!detail.checked && props.item.features.find((feature) => feature.name === ModelFeatures.REASONING) !== undefined) {
                                props.setFields({'features': props.item.features.filter((feature) => feature.name !== ModelFeatures.REASONING)});
                            }
                        }}
                        disabled={isEmbeddingModel || isImageModel || isVideoModel}
                        onBlur={() => props.touchFields(['features'])}
                        checked={props.item.features.find((feature) => feature.name === ModelFeatures.REASONING) !== undefined}
                    />
                </FormField>
                <FormField
                    label='Image Input'
                    description='Enable multimodal capabilities to process and analyze image inputs alongside text.'
                    errorText={props.formErrors?.features}
                >
                    <Toggle
                        onChange={({ detail }) => {
                            if (detail.checked && props.item.features.find((feature) => feature.name === ModelFeatures.IMAGE_INPUT) === undefined) {
                                props.setFields({'features': props.item.features.concat({name: ModelFeatures.IMAGE_INPUT, overview: ''})});
                            } else if (!detail.checked && props.item.features.find((feature) => feature.name === ModelFeatures.IMAGE_INPUT) !== undefined) {
                                props.setFields({'features': props.item.features.filter((feature) => feature.name !== ModelFeatures.IMAGE_INPUT)});
                            }
                        }}
                        disabled={isEmbeddingModel || isImageModel || isVideoModel}
                        onBlur={() => props.touchFields(['features'])}
                        checked={props.item.features.find((feature) => feature.name === ModelFeatures.IMAGE_INPUT) !== undefined}
                    />
                </FormField>
                <FormField
                    label='Summarization'
                    description='Enable document summarization capabilities for condensing long text into brief summaries.'
                    errorText={props.formErrors?.features}
                    warningText={props.item.features.find((feature) => feature.name === ModelFeatures.SUMMARIZATION) !== undefined ? 'Ensure model context is large enough to support these requests.' : ''}
                >
                    <Toggle
                        onChange={({ detail }) => {
                            if (detail.checked && props.item.features.find((feature) => feature.name === ModelFeatures.SUMMARIZATION) === undefined) {
                                props.setFields({'features': props.item.features.concat({name: ModelFeatures.SUMMARIZATION, overview: ''})});
                            } else if (!detail.checked && props.item.features.find((feature) => feature.name === ModelFeatures.SUMMARIZATION) !== undefined) {
                                props.setFields({'features': props.item.features.filter((feature) => feature.name !== ModelFeatures.SUMMARIZATION)});
                            }
                        }}
                        disabled={isEmbeddingModel || isImageModel || isVideoModel}
                        onBlur={() => props.touchFields(['features'])}
                        checked={props.item.features.find((feature) => feature.name === ModelFeatures.SUMMARIZATION) !== undefined}
                    />
                </FormField>
            </Grid>
            <FormField
                label={<span>Summarization Capabilities <em>- Optional</em></span>}
                description="Describe the model's summarization strengths, supported document types, and output formats."
                errorText={props.formErrors?.summarizationCapabilities}
            >
                <Input value={props.item.features.find((feature) => feature.name === ModelFeatures.SUMMARIZATION) !== undefined ? props.item.features.filter((feature) => feature.name === 'summarization')[0].overview : ''} inputMode='text' onBlur={() => props.touchFields(['features'])} onChange={({ detail }) => {
                    props.setFields({ 'features': [...props.item.features.filter((feature) => feature.name !== ModelFeatures.SUMMARIZATION), {name: ModelFeatures.SUMMARIZATION, overview: detail.value}] });
                }} disabled={!props.item.features.find((feature) => feature.name === ModelFeatures.SUMMARIZATION)} placeholder='Overview of Summarization for Model'/>
            </FormField>
            <UserGroupsInput
                label='Allowed groups'
                errorText={props.formErrors?.allowedGroups}
                values={props.item.allowedGroups || []}
                onChange={(values) => props.setFields({ 'allowedGroups': values })}
                description='Restrict model access to specific groups. Leave empty to allow access to all users.'
            />
        </SpaceBetween>
    );
}

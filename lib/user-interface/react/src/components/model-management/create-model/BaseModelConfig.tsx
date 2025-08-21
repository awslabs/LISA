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

import { ReactElement } from 'react';
import { FormProps} from '../../../shared/form/form-props';
import FormField from '@cloudscape-design/components/form-field';
import Input from '@cloudscape-design/components/input';
import Toggle from '@cloudscape-design/components/toggle';
import Select from '@cloudscape-design/components/select';
import { IModelRequest, InferenceContainer, ModelType } from '../../../shared/model/model-management.model';
import { Grid, SpaceBetween } from '@cloudscape-design/components';
import { useGetInstancesQuery } from '../../../shared/reducers/model-management.reducer';
import { ModelFeatures } from '@/components/types';
import { ArrayInputField } from '../../../shared/form/array-input';

export type BaseModelConfigCustomProps = {
    isEdit: boolean
};

export function BaseModelConfig (props: FormProps<IModelRequest> & BaseModelConfigCustomProps) : ReactElement {
    const {data: instances, isLoading: isLoadingInstances} = useGetInstancesQuery();
    const isEmbeddingModel = props.item.modelType === ModelType.embedding;
    const isImageModel = props.item.modelType === ModelType.imagegen;

    return (
        <SpaceBetween size={'s'}>
            <FormField label='Hosting Type' errorText={props.formErrors?.lisaHostedModel}>
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
                        { label: 'Third Party', value: 'false' },
                        { label: 'LISA Hosted', value: 'true' }
                    ]}
                    disabled={props.isEdit}
                />
            </FormField>
            <FormField label='Model ID' errorText={props.formErrors?.modelId} description='A unique identifier. This is displayed to users when selecting models.'>
                <Input value={props.item.modelId} inputMode='text' onBlur={() => props.touchFields(['modelId'])} onChange={({ detail }) => {
                    props.setFields({ 'modelId': detail.value });
                }} disabled={props.isEdit} placeholder='mistral-vllm'/>
            </FormField>
            <FormField label='Model Name' errorText={props.formErrors?.modelName} description='The full model identifier, typically the repository path or file system path to the model.'>
                <Input value={props.item.modelName} inputMode='text' onBlur={() => props.touchFields(['modelName'])} onChange={({ detail }) => {
                    props.setFields({ 'modelName': detail.value });
                }} disabled={props.isEdit} placeholder='mistralai/Mistral-7B-Instruct-v0.2'/>
            </FormField>
            <FormField label={<span>Model Description <em>(optional)</em></span>} errorText={props.formErrors?.modelDescription}>
                <Input value={props.item.modelDescription || ''} inputMode='text' onBlur={() => props.touchFields(['modelDescription'])} onChange={({ detail }) => {
                    props.setFields({ 'modelDescription': detail.value });
                }} placeholder='Brief description of the model and its capabilities'/>
            </FormField>
            <FormField label={<span>Model URL <em>(optional)</em></span>} errorText={props.formErrors?.modelUrl}>
                <Input value={props.item.modelUrl} inputMode='text' onBlur={() => props.touchFields(['modelUrl'])} onChange={({ detail }) => {
                    props.setFields({ 'modelUrl': detail.value });
                }} disabled={props.isEdit}/>
            </FormField>
            <FormField label='Model Type' errorText={props.formErrors?.modelType}>
                <Select
                    selectedOption={{label: props.item.modelType.toUpperCase(), value: props.item.modelType}}
                    onChange={({ detail }) => {
                        const fields = {
                            'modelType': detail.selectedOption.value,
                        };

                        // turn off streaming for embedded models
                        if (fields.modelType === ModelType.embedding || fields.modelType === ModelType.imagegen) {
                            fields['streaming'] = false;
                        }

                        // turn off summarization and image input for embedded and imagegen models
                        if ((fields.modelType === ModelType.embedding || fields.modelType === ModelType.imagegen)) {
                            fields['features'] = props.item.features.filter((feature) => feature.name !== ModelFeatures.SUMMARIZATION && feature.name !== ModelFeatures.IMAGE_INPUT && feature.name !== ModelFeatures.TOOL_CALLS);
                        }

                        props.setFields(fields);
                    }}
                    onBlur={() => props.touchFields(['modelType'])}
                    options={[
                        { label: 'TEXTGEN', value: ModelType.textgen },
                        { label: 'IMAGEGEN', value: ModelType.imagegen },
                        { label: 'EMBEDDING', value: ModelType.embedding },
                    ]}
                    disabled={props.isEdit}
                />
            </FormField>
            {props.item.lisaHostedModel && (
                <>
                    <FormField label='Instance Type' errorText={props.formErrors?.instanceType}>
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
                    <FormField label='Inference Container' errorText={props.formErrors?.inferenceContainer}>
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
            <Grid gridDefinition={[{ colspan: 6 }, { colspan: 6 }, { colspan: 6 }]}>
                <FormField label='Streaming' errorText={props.formErrors?.streaming}>
                    <Toggle
                        onChange={({ detail }) =>
                            props.setFields({'streaming': detail.checked})
                        }
                        onBlur={() => props.touchFields(['streaming'])}
                        disabled={isEmbeddingModel || isImageModel}
                        checked={props.item.streaming}
                    />
                </FormField>
                <FormField label='Tool Calls' errorText={props.formErrors?.features}>
                    <Toggle
                        onChange={({ detail }) => {
                            if (detail.checked && props.item.features.find((feature) => feature.name === ModelFeatures.TOOL_CALLS) === undefined) {
                                props.setFields({'features': props.item.features.concat({name: ModelFeatures.TOOL_CALLS, overview: ''})});
                            } else if (!detail.checked && props.item.features.find((feature) => feature.name === ModelFeatures.TOOL_CALLS) !== undefined) {
                                props.setFields({'features': props.item.features.filter((feature) => feature.name !== ModelFeatures.TOOL_CALLS)});
                            }
                        }}
                        disabled={isEmbeddingModel || isImageModel}
                        onBlur={() => props.touchFields(['features'])}
                        checked={props.item.features.find((feature) => feature.name === ModelFeatures.TOOL_CALLS) !== undefined}
                    />
                </FormField>
                <FormField label='Image Input' errorText={props.formErrors?.features}>
                    <Toggle
                        onChange={({ detail }) => {
                            if (detail.checked && props.item.features.find((feature) => feature.name === ModelFeatures.IMAGE_INPUT) === undefined) {
                                props.setFields({'features': props.item.features.concat({name: ModelFeatures.IMAGE_INPUT, overview: ''})});
                            } else if (!detail.checked && props.item.features.find((feature) => feature.name === ModelFeatures.IMAGE_INPUT) !== undefined) {
                                props.setFields({'features': props.item.features.filter((feature) => feature.name !== ModelFeatures.IMAGE_INPUT)});
                            }
                        }}
                        disabled={isEmbeddingModel || isImageModel}
                        onBlur={() => props.touchFields(['features'])}
                        checked={props.item.features.find((feature) => feature.name === ModelFeatures.IMAGE_INPUT) !== undefined}
                    />
                </FormField>
                <FormField label='Summarization' errorText={props.formErrors?.features}
                    warningText={props.item.features.find((feature) => feature.name === ModelFeatures.SUMMARIZATION) !== undefined ? 'Ensure model context is large enough to support these requests.' : ''}>
                    <Toggle
                        onChange={({ detail }) => {
                            if (detail.checked && props.item.features.find((feature) => feature.name === ModelFeatures.SUMMARIZATION) === undefined) {
                                props.setFields({'features': props.item.features.concat({name: ModelFeatures.SUMMARIZATION, overview: ''})});
                            } else if (!detail.checked && props.item.features.find((feature) => feature.name === ModelFeatures.SUMMARIZATION) !== undefined) {
                                props.setFields({'features': props.item.features.filter((feature) => feature.name !== ModelFeatures.SUMMARIZATION)});
                            }
                        }}
                        disabled={isEmbeddingModel || isImageModel}
                        onBlur={() => props.touchFields(['features'])}
                        checked={props.item.features.find((feature) => feature.name === ModelFeatures.SUMMARIZATION) !== undefined}
                    />
                </FormField>
            </Grid>
            <FormField label='Summarization Capabilities' errorText={props.formErrors?.summarizationCapabilities}>
                <Input value={props.item.features.find((feature) => feature.name === ModelFeatures.SUMMARIZATION) !== undefined ? props.item.features.filter((feature) => feature.name === 'summarization')[0].overview : ''} inputMode='text' onBlur={() => props.touchFields(['features'])} onChange={({ detail }) => {
                    props.setFields({ 'features': [...props.item.features.filter((feature) => feature.name !== ModelFeatures.SUMMARIZATION), {name: ModelFeatures.SUMMARIZATION, overview: detail.value}] });
                }} disabled={!props.item.features.find((feature) => feature.name === ModelFeatures.SUMMARIZATION)} placeholder='Optional overview of Summarization for Model'/>
            </FormField>
            <ArrayInputField
                label='Allowed Groups'
                errorText={props.formErrors?.allowedGroups}
                values={props.item.allowedGroups || []}
                onChange={(values) => props.setFields({ 'allowedGroups': values })}
                description='Restrict model access to specific groups. Leave empty to allow access to all users.'
            />
        </SpaceBetween>
    );
}

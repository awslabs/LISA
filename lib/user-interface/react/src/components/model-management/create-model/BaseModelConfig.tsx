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

export type BaseModelConfigCustomProps = {
    isEdit: boolean
};

export function BaseModelConfig (props: FormProps<IModelRequest> & BaseModelConfigCustomProps) : ReactElement {
    const {data: instances, isLoading: isLoadingInstances} = useGetInstancesQuery();

    return (
        <SpaceBetween size={'s'}>
            <FormField label='Model ID' errorText={props.formErrors?.modelId}>
                <Input value={props.item.modelId} inputMode='text' onBlur={() => props.touchFields(['modelId'])} onChange={({ detail }) => {
                    props.setFields({ 'modelId': detail.value });
                }} disabled={props.isEdit} placeholder='mistral-vllm'/>
            </FormField>
            <FormField label='Model Name' errorText={props.formErrors?.modelName}>
                <Input value={props.item.modelName} inputMode='text' onBlur={() => props.touchFields(['modelName'])} onChange={({ detail }) => {
                    props.setFields({ 'modelName': detail.value });
                }} disabled={props.isEdit} placeholder='mistralai/Mistral-7B-Instruct-v0.2'/>
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
                        if (fields.modelType === ModelType.embedding) {
                            fields['streaming'] = false;
                        }

                        // turn off summarization for embedded models
                        if (fields.modelType === ModelType.embedding && props.item.features.includes('summarization')) {
                            fields['features'] = props.item.features.filter((feature) => feature !== 'summarization');
                        }

                        props.setFields(fields);
                    }}
                    onBlur={() => props.touchFields(['modelType'])}
                    options={[
                        { label: 'TEXTGEN', value: ModelType.textgen },
                        { label: 'EMBEDDING', value: ModelType.embedding },
                    ]}
                />
            </FormField>
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
            <Grid gridDefinition={[{ colspan: 6 }, { colspan: 6 }, { colspan: 6 }]}>
                <FormField label='LISA Hosted Model' errorText={props.formErrors?.lisaHostedModel}>
                    <Toggle
                        onChange={({ detail }) =>
                            props.setFields({'lisaHostedModel': detail.checked})
                        }
                        onBlur={() => props.touchFields(['lisaHostedModel', 'instanceType', 'inferenceContainer'])}
                        checked={props.item.lisaHostedModel}
                        disabled={props.isEdit}
                    />
                </FormField>
                <FormField label='Streaming' errorText={props.formErrors?.streaming}>
                    <Toggle
                        onChange={({ detail }) =>
                            props.setFields({'streaming': detail.checked})
                        }
                        onBlur={() => props.touchFields(['streaming'])}
                        disabled={props.item.modelType === ModelType.embedding}
                        checked={props.item.streaming}
                    />
                </FormField>
                <FormField label='Summarization' errorText={props.formErrors?.features}
                    warningText={props.item.features.filter((feature) => feature.name === 'summarization').length > 0 ? 'Ensure model context is large enough to support these requests.' : ''}>
                    <Toggle
                        onChange={({ detail }) => {
                            if (detail.checked && props.item.features.filter((feature) => feature.name === 'summarization').length === 0) {
                                props.setFields({'features': props.item.features.concat({name: 'summarization', overview: ''})});
                            } else if (!detail.checked && props.item.features.filter((feature) => feature.name === 'summarization').length > 0) {
                                props.setFields({'features': props.item.features.filter((feature) => feature.name !== 'summarization')});
                            }
                        }}
                        disabled={props.item.modelType === ModelType.embedding}
                        onBlur={() => props.touchFields(['features'])}
                        checked={props.item.features.filter((feature) => feature.name === 'summarization').length > 0}
                    />
                </FormField>
            </Grid>
            <FormField label='Summarization Capabilities' errorText={props.formErrors?.summarizationCapabilities}>
                <Input value={props.item.features.filter((feature) => feature.name === 'summarization').length > 0 ? props.item.features.filter((feature) => feature.name === 'summarization')[0].overview : ''} inputMode='text' onBlur={() => props.touchFields(['features'])} onChange={({ detail }) => {
                    props.setFields({ 'features': [...props.item.features.filter((feature) => feature.name !== 'summarization'), {name: 'summarization', overview: detail.value}] });
                }} disabled={props.isEdit || props.item.features.filter((feature) => feature.name === 'summarization').length === 0} placeholder='Optional overview of Summarization for Model'/>
            </FormField>
        </SpaceBetween>
    );
}

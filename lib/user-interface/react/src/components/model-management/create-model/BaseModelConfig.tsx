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

export type BaseModelConfigCustomProps = {
    isEdit: boolean
};

export function BaseModelConfig (props: FormProps<IModelRequest> & BaseModelConfigCustomProps) : ReactElement {
    return (
        <SpaceBetween size={'s'}>
            <FormField label='Model ID' errorText={props.formErrors?.ModelId}>
                <Input value={props.item.ModelId} inputMode='text' onBlur={() => props.touchFields(['ModelId'])} onChange={({ detail }) => {
                    props.setFields({ 'ModelId': detail.value });
                }} disabled={props.isEdit}/>
            </FormField>
            <FormField label='Model Name' errorText={props.formErrors?.ModelName}>
                <Input value={props.item.ModelName} inputMode='text' onBlur={() => props.touchFields(['ModelName'])} onChange={({ detail }) => {
                    props.setFields({ 'ModelName': detail.value });
                }}/>
            </FormField>
            <FormField label='Model URL' errorText={props.formErrors?.ModelUrl}>
                <Input value={props.item.ModelUrl} inputMode='text' onBlur={() => props.touchFields(['ModelUrl'])} onChange={({ detail }) => {
                    props.setFields({ 'ModelUrl': detail.value });
                }}/>
            </FormField>
            <FormField label='Model Type' errorText={props.formErrors?.ModelType}>
                <Select
                    selectedOption={{label: props.item.ModelType.toUpperCase(), value: props.item.ModelType}}
                    onChange={({ detail }) =>
                        props.setFields({
                            'ModelType': detail.selectedOption.value,
                        })
                    }
                    onBlur={() => props.touchFields(['ModelType'])}
                    options={[
                        { label: 'TEXTGEN', value: ModelType.textgen },
                        { label: 'EMBEDDING', value: ModelType.embedding },
                    ]}
                />
            </FormField>
            <FormField label='Instance Type' errorText={props.formErrors?.InstanceType}>
                <Input value={props.item.InstanceType} inputMode='text' onBlur={() => props.touchFields(['InstanceType'])} onChange={({ detail }) => {
                    props.setFields({ 'InstanceType': detail.value });
                }}/>
            </FormField>
            <FormField label='Inference Container' errorText={props.formErrors?.InferenceContainer}>
                <Select
                    selectedOption={{label: props.item.InferenceContainer?.toUpperCase(), value: props.item.InferenceContainer}}
                    onBlur={() => props.touchFields(['InferenceContainer'])}
                    onChange={({ detail }) =>
                        props.setFields({
                            'InferenceContainer': detail.selectedOption.value,
                        })
                    }
                    options={[
                        { label: 'TGI', value: InferenceContainer.TGI },
                        { label: 'TEI', value: InferenceContainer.TEI },
                        { label: 'VLLM', value: InferenceContainer.VLLM },
                        { label: 'INSTRUCTOR', value: InferenceContainer.INSTRUCTOR },
                    ]}
                />
            </FormField>
            <Grid gridDefinition={[{ colspan: 6 }, { colspan: 6 }]}>
                <FormField label='LISA Hosted Model' errorText={props.formErrors?.LisaHostedModel}>
                    <Toggle
                        onChange={({ detail }) =>
                            props.setFields({'LisaHostedModel': detail.checked})
                        }
                        onBlur={() => props.touchFields(['LisaHostedModel'])}
                        checked={props.item.LisaHostedModel}
                    />
                </FormField>
                <FormField label='Streaming' errorText={props.formErrors?.Streaming}>
                    <Toggle
                        onChange={({ detail }) =>
                            props.setFields({'Streaming': detail.checked})
                        }
                        onBlur={() => props.touchFields(['Streaming'])}
                        checked={props.item.Streaming}
                    />
                </FormField>
            </Grid>
        </SpaceBetween>
    );
}

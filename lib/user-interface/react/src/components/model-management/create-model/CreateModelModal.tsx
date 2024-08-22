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
import Form from '@cloudscape-design/components/form';
import SpaceBetween from '@cloudscape-design/components/space-between';
import { Button, ExpandableSection, Modal } from '@cloudscape-design/components';
import FormField from '@cloudscape-design/components/form-field';
import Input from '@cloudscape-design/components/input';
import {
    IModel,
    InferenceContainer,
    ModelRequestSchema,
    ModelType,
} from '../../../shared/model/model-management.model';
import { ReactElement, useState } from 'react';
import Select from '@cloudscape-design/components/select';
import Toggle from '@cloudscape-design/components/toggle';

export type CreateModelModalProps = {
    visible: boolean;
    isEdit: boolean;
    setVisible: (boolean) => void;
    selectedItems: IModel[];
};

export function CreateModelModal (props: CreateModelModalProps) : ReactElement {
    console.log(props);
    console.log(ModelRequestSchema.parse({}));

    const [streaming, setStreaming] = useState(true);
    const [
        selectedModelType,
        setSelectedModelType
    ] = useState({ label: 'TEXTGEN', value: ModelType.textgen });
    const [
        selectedInferenceContainer,
        setSelectedInferenceContainer
    ] = useState({ label: 'TGI', value: InferenceContainer.TGI });
    return (
        <Modal onDismiss={() => props.setVisible(false)} visible={props.visible} header={`${props.isEdit ? 'Update' : 'Create'} Model`}>
            <form onSubmit={(e) => e.preventDefault()}>
                <Form
                    actions={
                        <SpaceBetween direction='horizontal' size='xs'>
                            <Button formAction='none' variant='link' onClick={() => props.setVisible(false)}>
                                Cancel
                            </Button>
                            <Button variant='primary'>Submit</Button>
                        </SpaceBetween>
                    }
                >
                    <SpaceBetween direction='vertical' size='xs'>
                        <FormField label='Model ID'>
                            <Input value=''
                                inputMode='text'/>
                        </FormField>
                        <FormField label='Model Name'>
                            <Input value=''
                                inputMode='text'/>
                        </FormField>
                        <FormField label='Streaming'>
                            <Toggle
                                onChange={({ detail }) =>
                                    setStreaming(detail.checked)
                                }
                                checked={streaming}
                            />
                        </FormField>
                        <FormField label='Model Type'>
                            <Select
                                selectedOption={selectedModelType}
                                onChange={({ detail }) =>
                                    setSelectedModelType(detail.selectedOption)
                                }
                                options={[
                                    { label: 'TEXTGEN', value: ModelType.textgen },
                                    { label: 'EMBEDDING', value: ModelType.embedding },
                                ]}
                            />
                        </FormField>
                        <FormField label='Instance Type'>
                            <Input value=''
                                inputMode='text'/>
                        </FormField>
                        <FormField label='Inference Container'>
                            <Select
                                selectedOption={selectedInferenceContainer}
                                onChange={({ detail }) =>
                                    setSelectedInferenceContainer(detail.selectedOption)
                                }
                                options={[
                                    { label: 'TGI', value: InferenceContainer.TGI },
                                    { label: 'TEI', value: InferenceContainer.TEI },
                                    { label: 'VLLM', value: InferenceContainer.VLLM },
                                    { label: 'INSTRUCTOR', value: InferenceContainer.INSTRUCTOR },
                                ]}
                            />
                        </FormField>
                        <ExpandableSection variant='stacked'
                            headerText='Container Config'>
                            <FormField label='Shared Memory Size'>
                                <Input value=''
                                    inputMode='numeric'/>
                            </FormField>
                            <ExpandableSection defaultExpanded
                                headingTagOverride='h3'
                                variant='stacked'
                                headerText='Base Image Config'>
                                <FormField label='Base Image'>
                                    <Input value=''
                                        inputMode='text'/>
                                </FormField>
                                <FormField label='Path'>
                                    <Input value=''
                                        inputMode='text'/>
                                </FormField>
                                <FormField label='Type'>
                                    <Input value=''
                                        inputMode='text'/>
                                </FormField>
                            </ExpandableSection>
                            <ExpandableSection defaultExpanded
                                headingTagOverride='h3'
                                variant='stacked'
                                headerText='Container Health Check Config'>
                                <FormField label='Command'>
                                    <Input value=''
                                        inputMode='text'/>
                                </FormField>
                                <FormField label='Interval'>
                                    <Input value=''
                                        inputMode='numeric'/>
                                </FormField>
                                <FormField label='Start Period'>
                                    <Input value=''
                                        inputMode='numeric'/>
                                </FormField>
                                <FormField label='Timeout'>
                                    <Input value=''
                                        inputMode='numeric'/>
                                </FormField>
                                <FormField label='Retries'>
                                    <Input value=''
                                        inputMode='numeric'/>
                                </FormField>
                            </ExpandableSection>
                        </ExpandableSection>
                        <ExpandableSection variant='stacked'
                            headerText='Auto Scaling Config'>
                            <FormField label='Min Capacity'>
                                <Input value=''
                                    inputMode='numeric'/>
                            </FormField>
                            <FormField label='Max Capacity'>
                                <Input value=''
                                    inputMode='numeric'/>
                            </FormField>
                            <FormField label='Cooldown'>
                                <Input value=''
                                    inputMode='numeric'/>
                            </FormField>
                            <FormField label='Default Instance Warmup'>
                                <Input value=''
                                    inputMode='numeric'/>
                            </FormField>
                            <ExpandableSection defaultExpanded
                                headingTagOverride='h3'
                                variant='stacked'
                                headerText='Metric Config'>
                                <FormField label='ALB Metric Name'>
                                    <Input value=''
                                        inputMode='text'/>
                                </FormField>
                                <FormField label='Target Value'>
                                    <Input value=''
                                        inputMode='text'/>
                                </FormField>
                                <FormField label='Duration'>
                                    <Input value=''
                                        inputMode='numeric'/>
                                </FormField>
                                <FormField label='Estimated Instance Warmup'>
                                    <Input value=''
                                        inputMode='numeric'/>
                                </FormField>
                            </ExpandableSection>
                        </ExpandableSection>
                        <ExpandableSection variant='stacked'
                            headerText='Load Balancer Config'>
                            <ExpandableSection defaultExpanded
                                headingTagOverride='h3'
                                variant='stacked'
                                headerText='Health Check Config'>
                                <FormField label='Path'>
                                    <Input value=''
                                        inputMode='text'/>
                                </FormField>
                                <FormField label='Interval'>
                                    <Input value=''
                                        inputMode='numeric'/>
                                </FormField>
                                <FormField label='Timeout'>
                                    <Input value=''
                                        inputMode='numeric'/>
                                </FormField>
                                <FormField label='Healthy Threshold Count'>
                                    <Input value=''
                                        inputMode='numeric'/>
                                </FormField>
                                <FormField label='Unhealthy Threshold Count'>
                                    <Input value=''
                                        inputMode='numeric'/>
                                </FormField>
                            </ExpandableSection>
                        </ExpandableSection>
                    </SpaceBetween>
                </Form>
            </form>
        </Modal>
    );
}

export default CreateModelModal;

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

import { Button, FormField, Input, Select, SelectProps, SpaceBetween } from '@cloudscape-design/components';
import { useMemo, useState } from 'react';
import { WorkflowTemplate } from '@/shared/model/workflow.model';

type WorkflowFormProps = {
    templates: WorkflowTemplate[];
    isSubmitting?: boolean;
    onSubmit: (payload: { name: string; templateId: string }) => void;
};

export function WorkflowForm ({ templates, isSubmitting, onSubmit }: WorkflowFormProps) {
    const templateOptions = useMemo<SelectProps.Option[]>(() => (
        templates.map((template) => ({ label: template.name, value: template.id }))
    ), [templates]);
    const [selectedTemplate, setSelectedTemplate] = useState<SelectProps.Option | null>(templateOptions[0] ?? null);
    const [name, setName] = useState('');

    const activeTemplate = templates.find((template) => template.id === selectedTemplate?.value);
    const isDisabled = isSubmitting || !name.trim() || !selectedTemplate?.value;

    return (
        <SpaceBetween size='s'>
            <FormField label='Template'>
                <Select
                    selectedOption={selectedTemplate}
                    options={templateOptions}
                    onChange={({ detail }) => setSelectedTemplate(detail.selectedOption)}
                    data-testid='workflow-template-select'
                />
            </FormField>
            <FormField label='Workflow name'>
                <Input
                    value={name}
                    onChange={({ detail }) => setName(detail.value)}
                    placeholder='Enter workflow name'
                    data-testid='workflow-name-input'
                />
            </FormField>
            <FormField label='Template description'>
                <Input value={activeTemplate?.description ?? ''} disabled />
            </FormField>
            <Button
                variant='primary'
                disabled={isDisabled}
                onClick={() => onSubmit({ name, templateId: selectedTemplate?.value ?? '' })}
                data-testid='workflow-create-from-template'
            >
                Create from template
            </Button>
        </SpaceBetween>
    );
}

export default WorkflowForm;

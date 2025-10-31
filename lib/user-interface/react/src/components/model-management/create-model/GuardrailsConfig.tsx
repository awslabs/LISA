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

import React, { ReactElement, useState } from 'react';
import { FormProps } from '../../../shared/form/form-props';
import { IGuardrailsConfig, GuardrailMode } from '../../../shared/model/model-management.model';
import {
    Button,
    Container,
    FormField,
    Grid,
    Header,
    Icon,
    Input,
    Select,
    SpaceBetween,
    Textarea,
    TokenGroup
} from '@cloudscape-design/components';

type GuardrailsConfigProps = FormProps<IGuardrailsConfig> & {
    isEdit: boolean;
};

export function GuardrailsConfig (props: GuardrailsConfigProps): ReactElement {
    const guardrails = props.item?.guardrails || {};
    const guardrailEntries = Object.entries(guardrails);
    const [groupInputValues, setGroupInputValues] = useState<Record<string, string>>({});

    const addGuardrail = () => {
        const newKey = `guardrail-${Date.now()}`;
        const newGuardrails = {
            ...guardrails,
            [newKey]: {
                guardrail_name: '',
                guardrail_identifier: '',
                guardrail_version: 'DRAFT',
                mode: GuardrailMode.PRE_CALL,
                description: '',
                allowed_groups: [],
            }
        };
        props.setFields({ 'guardrailsConfig.guardrails': newGuardrails });
    };

    const removeGuardrail = (key: string) => {
        if (props.isEdit) {
            // Mark for deletion instead of removing
            const updatedGuardrails = {
                ...guardrails,
                [key]: {
                    ...guardrails[key],
                    marked_for_deletion: true
                }
            };
            props.setFields({ 'guardrailsConfig.guardrails': updatedGuardrails });
        } else {
            // Remove completely for new models
            const remainingGuardrails = Object.fromEntries(
                Object.entries(guardrails).filter(([k]) => k !== key)
            );

            props.setFields({ 'guardrailsConfig.guardrails': remainingGuardrails });
        }
        props.touchFields(['guardrailsConfig.guardrails']);
    };

    const updateGuardrail = (key: string, field: string, value: any) => {
        const updatedGuardrails = {
            ...guardrails,
            [key]: {
                ...guardrails[key],
                [field]: value
            }
        };
        props.setFields({ 'guardrailsConfig.guardrails': updatedGuardrails });
    };

    const modeOptions = [
        { label: 'Pre Call', value: GuardrailMode.PRE_CALL, description: 'Execute guardrail before LLM call' },
        { label: 'During Call', value: GuardrailMode.DURING_CALL, description: 'Execute guardrail during LLM call' },
        { label: 'Post Call', value: GuardrailMode.POST_CALL, description: 'Execute guardrail after LLM call' }
    ];

    return (
        <SpaceBetween size={'s'}>
            <Container
                header={
                    <Header
                        variant='h2'
                        description='Configure guardrails for this model. Guardrails help ensure safe and compliant model outputs.'
                        actions={
                            <Button onClick={addGuardrail} ariaLabel='Add guardrail'>
                                Add Guardrail
                            </Button>
                        }
                    >
                        Guardrails Configuration
                    </Header>
                }
            >
                {guardrailEntries.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '2rem', color: '#5f6b7a' }}>
                        No guardrails configured. Click "Add Guardrail" to create one.
                    </div>
                ) : (
                    <SpaceBetween size={'l'}>
                        {guardrailEntries.map(([key, guardrail]) => {
                            // Skip rendering guardrails marked for deletion
                            if (guardrail.marked_for_deletion) {
                                return null;
                            }

                            return (
                                <Container
                                    key={key}
                                    header={
                                        <Grid gridDefinition={[{ colspan: 10 }, { colspan: 2 }]}>
                                            <Header variant='h3'>
                                                {guardrail.guardrail_name || 'New Guardrail'}
                                            </Header>
                                            <div style={{ textAlign: 'right' }}>
                                                <Button
                                                    onClick={() => removeGuardrail(key)}
                                                    ariaLabel='Remove guardrail'
                                                >
                                                    <Icon name='close' />
                                                </Button>
                                            </div>
                                        </Grid>
                                    }
                                >
                                    <SpaceBetween size={'s'}>
                                        <FormField
                                            label='Guardrail Name'
                                            errorText={props.formErrors?.guardrailsConfig?.guardrails?.[key]?.guardrail_name}
                                            constraintText='Required. A friendly name for this guardrail.'
                                        >
                                            <Input
                                                value={guardrail.guardrail_name}
                                                onChange={({ detail }) => updateGuardrail(key, 'guardrail_name', detail.value)}
                                                onBlur={() => props.touchFields([`guardrailsConfig.guardrails.${key}.guardrail_name`])}
                                                placeholder='Enter guardrail name'
                                            />
                                        </FormField>

                                        <FormField
                                            label='Guardrail Identifier'
                                            errorText={props.formErrors?.guardrailsConfig?.guardrails?.[key]?.guardrail_identifier}
                                            constraintText='Required. The ARN or ID of the AWS Bedrock guardrail.'
                                        >
                                            <Input
                                                value={guardrail.guardrail_identifier}
                                                onChange={({ detail }) => updateGuardrail(key, 'guardrail_identifier', detail.value)}
                                                onBlur={() => props.touchFields([`guardrailsConfig.guardrails.${key}.guardrail_identifier`])}
                                                placeholder='Enter guardrail identifier (ARN or ID)'
                                            />
                                        </FormField>

                                        <FormField
                                            label='Guardrail Version'
                                            errorText={props.formErrors?.guardrailsConfig?.guardrails?.[key]?.guardrail_version}
                                            constraintText='The version of the guardrail to use. Default is DRAFT.'
                                        >
                                            <Input
                                                value={guardrail.guardrail_version}
                                                onChange={({ detail }) => updateGuardrail(key, 'guardrail_version', detail.value)}
                                                onBlur={() => props.touchFields([`guardrailsConfig.guardrails.${key}.guardrail_version`])}
                                                placeholder='Enter version (e.g., DRAFT, 1, 2)'
                                            />
                                        </FormField>

                                        <FormField
                                            label='Mode'
                                            errorText={props.formErrors?.guardrailsConfig?.guardrails?.[key]?.mode}
                                            constraintText='When the guardrail should be executed.'
                                        >
                                            <Select
                                                selectedOption={
                                                    modeOptions.find((opt) => opt.value === guardrail.mode) ||
                                                    modeOptions[0]
                                                }
                                                onChange={({ detail }) => updateGuardrail(key, 'mode', detail.selectedOption.value)}
                                                onBlur={() => props.touchFields([`guardrailsConfig.guardrails.${key}.mode`])}
                                                options={modeOptions}
                                            />
                                        </FormField>

                                        <FormField
                                            label='Description'
                                            errorText={props.formErrors?.guardrailsConfig?.guardrails?.[key]?.description}
                                            constraintText='Optional. A description of what this guardrail does.'
                                        >
                                            <Textarea
                                                value={guardrail.description || ''}
                                                onChange={({ detail }) => updateGuardrail(key, 'description', detail.value)}
                                                onBlur={() => props.touchFields([`guardrailsConfig.guardrails.${key}.description`])}
                                                placeholder='Enter description'
                                                rows={3}
                                            />
                                        </FormField>

                                        <FormField
                                            label='Allowed Groups'
                                            errorText={props.formErrors?.guardrailsConfig?.guardrails?.[key]?.allowed_groups}
                                            constraintText='Optional. Groups that are allowed to use this guardrail. Type a group name and click Add.'
                                        >
                                            <SpaceBetween size='xs'>
                                                <TokenGroup
                                                    items={
                                                        (guardrail.allowed_groups || []).map((group) => ({
                                                            label: group,
                                                            dismissLabel: `Remove ${group}`
                                                        }))
                                                    }
                                                    onDismiss={({ detail: { itemIndex } }) => {
                                                        const newGroups = [...(guardrail.allowed_groups || [])];
                                                        newGroups.splice(itemIndex, 1);
                                                        updateGuardrail(key, 'allowed_groups', newGroups);
                                                    }}
                                                    alignment='vertical'
                                                />
                                                <Input
                                                    value={groupInputValues[key] || ''}
                                                    placeholder='Enter group name'
                                                    onChange={({ detail }) => {
                                                        setGroupInputValues((prev) => ({
                                                            ...prev,
                                                            [key]: detail.value
                                                        }));
                                                    }}
                                                    onKeyDown={(event) => {
                                                        if (event.detail.key === 'Enter') {
                                                            const value = (groupInputValues[key] || '').trim();
                                                            if (value && !(guardrail.allowed_groups || []).includes(value)) {
                                                                updateGuardrail(key, 'allowed_groups', [
                                                                    ...(guardrail.allowed_groups || []),
                                                                    value
                                                                ]);
                                                                setGroupInputValues((prev) => ({
                                                                    ...prev,
                                                                    [key]: ''
                                                                }));
                                                            }
                                                            event.preventDefault();
                                                        }
                                                    }}
                                                />
                                                <Button
                                                    onClick={() => {
                                                        const value = (groupInputValues[key] || '').trim();
                                                        if (value && !(guardrail.allowed_groups || []).includes(value)) {
                                                            updateGuardrail(key, 'allowed_groups', [
                                                                ...(guardrail.allowed_groups || []),
                                                                value
                                                            ]);
                                                            setGroupInputValues((prev) => ({
                                                                ...prev,
                                                                [key]: ''
                                                            }));
                                                        }
                                                    }}
                                                >
                                                    Add
                                                </Button>
                                            </SpaceBetween>
                                        </FormField>
                                    </SpaceBetween>
                                </Container>
                            );
                        })}
                    </SpaceBetween>
                )}
            </Container>
        </SpaceBetween>
    );
}

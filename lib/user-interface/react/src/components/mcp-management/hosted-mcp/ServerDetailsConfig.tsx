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

import { ReactElement, useMemo, useState } from 'react';
import {
    FormField,
    Input,
    Select,
    SelectProps,
    SpaceBetween,
    Textarea,
    TokenGroup,
} from '@cloudscape-design/components';
import { KeyCode } from '@cloudscape-design/component-toolkit/internal';
import { SetFieldsFunction, TouchFieldsFunction } from '@/shared/validation';
import { HostedMcpServerRequestForm } from '@/shared/model/hosted-mcp-server.model';

const SERVER_TYPE_OPTIONS: SelectProps.Option[] = [
    { label: 'STDIO', value: 'stdio' },
    { label: 'HTTP', value: 'http' },
    { label: 'SSE', value: 'sse' },
];

type ServerDetailsConfigProps = {
    item: HostedMcpServerRequestForm;
    setFields: SetFieldsFunction;
    touchFields: TouchFieldsFunction;
    formErrors: any;
    isEdit: boolean;
};

export function ServerDetailsConfig({
    item,
    setFields,
    touchFields,
    formErrors,
    isEdit,
}: ServerDetailsConfigProps): ReactElement {
    const [groupInput, setGroupInput] = useState('');

    const serverTypeOption = useMemo(() => {
        return SERVER_TYPE_OPTIONS.find(opt => opt.value === item.serverType) || SERVER_TYPE_OPTIONS[0];
    }, [item.serverType]);

    const tokens = useMemo(() => {
        return (item.groups || []).map((group) => ({
            label: group,
            dismissLabel: `Remove ${group}`,
        }));
    }, [item.groups]);

    const handleAddGroup = () => {
        const value = groupInput.trim();
        if (!value || (item.groups || []).includes(value)) {
            return;
        }
        setFields({ groups: [...(item.groups || []), value] });
        setGroupInput('');
    };

    const handleRemoveGroup = (index: number) => {
        const updatedGroups = (item.groups || []).filter((_, i) => i !== index);
        setFields({ groups: updatedGroups });
    };

    return (
        <SpaceBetween size='s'>
            <FormField
                label='Name'
                description='Unique identifier for the hosted MCP server.'
                errorText={formErrors?.name}
            >
                <Input
                    value={item.name}
                    onChange={({ detail }) => setFields({ name: detail.value })}
                    onBlur={() => touchFields(['name'])}
                    disabled={isEdit}
                />
            </FormField>
            <FormField
                label={<span>Description <em>- Optional</em></span>}
                description='Description of the MCP server.'
            >
                <Textarea
                    value={item.description || ''}
                    rows={3}
                    onChange={({ detail }) => setFields({ description: detail.value })}
                />
            </FormField>
            <FormField
                label='Server type'
                description='Transport protocol for MCP communication.'
            >
                <Select
                    selectedOption={serverTypeOption}
                    onChange={({ detail }) => setFields({ serverType: detail.selectedOption.value as any })}
                    options={SERVER_TYPE_OPTIONS}
                    disabled={isEdit}
                />
            </FormField>
            <FormField
                label={<span>Base Image <em>- Optional</em></span>}
                description='Pre-built image or base image URI.'
                errorText={formErrors?.image}
            >
                <Input
                    value={item.image || ''}
                    onChange={({ detail }) => setFields({ image: detail.value })}
                    placeholder='public.ecr.aws/... or registry/image:tag'
                    disabled={isEdit}
                />
            </FormField>
            <FormField
                label='Start command'
                description='Command executed when the container starts. For STDIO servers include the binary or script to launch.'
                errorText={formErrors?.startCommand}
            >
                <Textarea
                    value={item.startCommand}
                    rows={4}
                    onChange={({ detail }) => setFields({ startCommand: detail.value })}
                    onBlur={() => touchFields(['startCommand'])}
                    disabled={isEdit}
                />
            </FormField>
            <FormField
                label={<span>Container Port <em>- Optional</em></span>}
                description='Defaults to 8000 for HTTP/SSE or 8080 for STDIO proxy.'
                errorText={formErrors?.port}
            >
                <Input
                    value={item.port?.toString() || ''}
                    onChange={({ detail }) => {
                        const value = detail.value ? Number(detail.value) : undefined;
                        setFields({ port: value });
                    }}
                    inputMode='numeric'
                    type='number'
                    placeholder={serverTypeOption.label === 'STDIO' ? '8080' : '8000'}
                    disabled={isEdit}
                />
            </FormField>
            <FormField
                label={<span>Groups <em>- Optional</em></span>}
                description='Restrict access to specific groups. Enter a group name and press return to add it.'
            >
                <SpaceBetween size='xs'>
                    <Input
                        value={groupInput}
                        onChange={({ detail }) => setGroupInput(detail.value)}
                        onKeyDown={(event) => {
                            if (event.detail.keyCode === KeyCode.enter) {
                                handleAddGroup();
                                event.preventDefault();
                            }
                        }}
                        placeholder='Enter group name'
                    />
                    {tokens.length > 0 && (
                        <TokenGroup
                            items={tokens}
                            onDismiss={({ detail }) => handleRemoveGroup(detail.itemIndex)}
                        />
                    )}
                </SpaceBetween>
            </FormField>
        </SpaceBetween>
    );
}

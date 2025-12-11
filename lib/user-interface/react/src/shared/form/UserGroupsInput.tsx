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

import { ReactElement, useState } from 'react';
import { Button, FormField, Input, SpaceBetween, TokenGroup } from '@cloudscape-design/components';
import { FormFieldProps } from '@cloudscape-design/components/form-field';

type UserGroupsInputProps = FormFieldProps & {
    values: string[];
    onChange: (newValues: string[]) => void;
    placeholder?: string;
};

export function UserGroupsInput (props: UserGroupsInputProps): ReactElement {
    const { onChange, values, placeholder = 'Enter group name', ...formFieldProps } = props;
    const [inputValue, setInputValue] = useState('');

    const handleAdd = () => {
        const trimmedValue = inputValue.trim();
        if (trimmedValue && !values.includes(trimmedValue)) {
            onChange([...values, trimmedValue]);
            setInputValue('');
        }
    };

    const handleRemove = (itemIndex: number) => {
        const newValues = [...values];
        newValues.splice(itemIndex, 1);
        onChange(newValues);
    };

    const handleKeyDown = (event: CustomEvent<{ key: string }>) => {
        if (event.detail.key === 'Enter') {
            handleAdd();
            event.preventDefault();
        }
    };

    return (
        <FormField {...formFieldProps}>
            <SpaceBetween size='xs'>
                <TokenGroup
                    items={values.map((group) => ({
                        label: group,
                        dismissLabel: `Remove ${group}`
                    }))}
                    onDismiss={({ detail: { itemIndex } }) => handleRemove(itemIndex)}
                />
                <Input
                    value={inputValue}
                    placeholder={placeholder}
                    onChange={({ detail }) => setInputValue(detail.value)}
                    onKeyDown={handleKeyDown}
                />
                <Button onClick={handleAdd}>Add</Button>
            </SpaceBetween>
        </FormField>
    );
}

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

import React, { ReactElement } from 'react';
import FormField from '@cloudscape-design/components/form-field';
import Input from '@cloudscape-design/components/input';
import { Button, SpaceBetween } from '@cloudscape-design/components';

type ArrayInputProps = {
    label: string;
    values: string[];
    onChange: (newValues: string[]) => void;
    errorText?: string;
};

export function ArrayInputField ({ label, values, onChange, errorText }: ArrayInputProps): ReactElement {
    const handleInputChange = (index: number, value: string) => {
        const newValues = [...values];
        newValues[index] = value;
        onChange(newValues);
    };

    const addNewInput = () => {
        onChange([...values, '']);
    };

    const removeInput = (index: number) => {
        const newValues = values.filter((_, i) => i !== index);
        onChange(newValues);
    };

    return (
        <FormField
            label={label}
            errorText={errorText}
        >
            <SpaceBetween size='xs'>
                {values.map((value, index) => (
                    <SpaceBetween direction='horizontal' size='xs' key={index}>
                        <Input
                            value={value}
                            onChange={({ detail }) => handleInputChange(index, detail.value)}
                        />
                        <Button
                            variant='icon'
                            iconName='remove'
                            onClick={() => removeInput(index)}
                        />
                    </SpaceBetween>
                ))}
                <Button
                    iconName='add-plus'
                    variant='normal'
                    onClick={addNewInput}
                >
                    Add new
                </Button>
            </SpaceBetween>
        </FormField>
    );
}

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

import {
    AttributeEditor,
    ExpandableSection,
    FormField,
    Input,
    SpaceBetween,
} from '@cloudscape-design/components';
import { Fragment, ReactElement } from 'react';
import { FormProps } from './form-props';
import { duplicateAttributeRefinement } from '../validation';
import { z } from 'zod';
import { ModifyMethod } from '../validation/modify-method';

export const AttributeEditorSchema = z
    .array(
        z.object({
            key: z.string().min(1, { message: 'Empty key not permitted.' }),
            value: z.string().min(1, { message: 'Empty value not permitted.' }),
        })
    )
    .superRefine(duplicateAttributeRefinement('key'))
    .optional();

export type EnvironmentVariablesProps = {
    propertyPath?: string[]
};


export function EnvironmentVariables (props: FormProps<Readonly<any>> & EnvironmentVariablesProps): ReactElement {
    const { item, setFields, touchFields, formErrors, propertyPath } = props;
    const property = props.propertyPath ? propertyPath?.join('.') : 'Environment';

    function findProperty (obj, path) {
        const parts = path.split('.');
        if (parts.length === 1 && obj){
            return obj[parts[0]];
        } else if (!obj){
            return undefined;
        }
        return findProperty(obj[parts[0]], parts.slice(1).join('.'));
    }

    return (
        <ExpandableSection
            headerText={
                <Fragment>
                    Environment variables <i>- optional</i>
                </Fragment>
            }
            headingTagOverride='h3'
            defaultExpanded={true}
        >
            <SpaceBetween direction='vertical' size='xxl'>
                <FormField label='' description=''>
                    <AttributeEditor
                        onAddButtonClick={() => {
                            setFields({ [property]: (item.Environment || []).concat({
                                key: '',
                                value: '',
                            })});
                        }}
                        onRemoveButtonClick={({ detail: { itemIndex } }) => {
                            const toRemove = {} as any;
                            toRemove[`${property}[${itemIndex}]`] = true;
                            setFields(toRemove, ModifyMethod.Unset);
                        }}
                        items={item.Environment}
                        addButtonText='Add environment variable'
                        definition={[
                            {
                                label: 'Key',
                                control: (attribute: any, itemIndex) => (
                                    <FormField
                                        errorText={findProperty(formErrors, property)?.[itemIndex]?.key}
                                    >
                                        <Input
                                            autoFocus
                                            placeholder='Enter key'
                                            value={attribute.key}
                                            onChange={({ detail }) => {
                                                const toChange = {} as any;
                                                toChange[`${property}[${itemIndex}]`] = {
                                                    key: detail.value,
                                                };
                                                setFields(toChange, ModifyMethod.Merge);
                                            }}
                                            onBlur={() =>
                                                touchFields([`${property}[${itemIndex}].key`])
                                            }
                                        />
                                    </FormField>
                                ),
                            },
                            {
                                label: 'Value',
                                control: (attribute: any, itemIndex) => (
                                    <FormField
                                        errorText={findProperty(formErrors, property)?.[itemIndex]?.value}
                                    >
                                        <Input
                                            placeholder='Enter value'
                                            value={attribute.value}
                                            onChange={({ detail }) => {
                                                const toChange = {} as any;
                                                toChange[`${property}[${itemIndex}]`] = {
                                                    value: detail.value,
                                                };
                                                setFields(toChange, ModifyMethod.Merge);
                                            }}
                                            onBlur={() =>
                                                touchFields([`${property}[${itemIndex}].value`])
                                            }
                                        />
                                    </FormField>
                                ),
                            },
                        ]}
                        removeButtonText='Remove'
                        empty='No items associated with the resource.'
                    />
                </FormField>
            </SpaceBetween>
        </ExpandableSection>
    );
}

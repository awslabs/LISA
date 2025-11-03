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
import { Alert, SpaceBetween } from '@cloudscape-design/components';
import { ArrayInputField } from '../../../shared/form/array-input';
import { CommonFieldsForm } from '../../../shared/form/CommonFieldsForm';
import { RagCollectionConfig } from '#root/lib/schema';
import { ModifyMethod } from '../../../shared/form/form-props';

export type AccessControlFormProps = {
    item: RagCollectionConfig;
    setFields(values: { [key: string]: any }, method?: ModifyMethod): void;
    touchFields(fields: string[], method?: ModifyMethod): void;
    formErrors: any;
};

export function AccessControlForm (props: AccessControlFormProps): ReactElement {
    const { item, touchFields, setFields, formErrors } = props;

    return (
        <SpaceBetween size='s'>
            <Alert type='info'>
                Access control is optional. If no groups are specified, the collection will be
                accessible to all users. You can also inherit access controls from the parent repository.
            </Alert>

            {/* Common Fields (Allowed Groups) */}
            <CommonFieldsForm
                item={item}
                setFields={setFields}
                touchFields={touchFields}
                formErrors={formErrors}
                repositoryId={item.repositoryId}
                showEmbeddingModel={false}
                showAllowedGroups={true}
            />

            {/* Metadata Tags */}
            <FormField
                label='Tags (optional)'
                errorText={formErrors?.['metadata.tags'] || formErrors?.metadata?.tags}
                description='Metadata tags for organizing and searching collections (max 50 tags)'
            >
                <ArrayInputField
                    values={item.metadata?.tags || []}
                    onChange={(tags) => setFields({ 'metadata.tags': tags })}
                    placeholder='Add tag'
                />
            </FormField>
        </SpaceBetween>
    );
}

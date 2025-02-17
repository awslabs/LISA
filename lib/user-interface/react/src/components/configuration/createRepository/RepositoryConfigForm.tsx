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
import { FormProps } from '../../../shared/form/form-props';
import FormField from '@cloudscape-design/components/form-field';
import Input from '@cloudscape-design/components/input';
import Select from '@cloudscape-design/components/select';
import { SpaceBetween } from '@cloudscape-design/components';
import {
    OpenSearchNewClusterConfig,
    RagRepositoryConfig,
    RagRepositoryType,
    RdsInstanceConfig,
} from '../../../../../../configSchema';
import { getDefaults } from '../../../shared/util/zodUtil';
import { ArrayInputField } from '../../../shared/form/array-input';
import { RdsConfigForm } from './RdsConfigForm';
import { OpenSearchConfigForm } from './OpenSearchConfigForm';

export type RepositoryConfigProps = {
    isEdit: boolean
};

export function RepositoryConfigForm (props: FormProps<RagRepositoryConfig> & RepositoryConfigProps): ReactElement {
    const { item, touchFields, setFields, formErrors, isEdit } = props;
    return (
        <SpaceBetween size={'s'}>
            <FormField label='Repository ID'
                errorText={formErrors?.repositoryId}
                description={'A unique identifier for the repository, used in API calls and the UI. It must be distinct across all repositories.'}>
                <Input value={item.repositoryId} inputMode='text'
                    onBlur={() => touchFields(['repositoryId'])}
                    onChange={({ detail }) => {
                        setFields({ 'repositoryId': detail.value });
                    }} disabled={isEdit} placeholder='postgres-rag' />
            </FormField>
            <FormField label='Repository Name - optional'
                errorText={formErrors?.repositoryName}
                description={'The user-friendly name displayed in the UI.'}>
                <Input value={item.repositoryName} inputMode='text'
                    onBlur={() => touchFields(['repositoryName'])}
                    onChange={({ detail }) => {
                        setFields({ 'repositoryName': detail.value });
                    }} placeholder='Postgres RAG' />
            </FormField>
            <FormField label='Repository Type'
                errorText={formErrors?.type}
                description={'The vector store designated for this repository.'}>
                <Select
                    selectedOption={{ label: item.type, value: item.type }}
                    onChange={({ detail }) => {
                        if (item.type === detail.selectedOption.value) {
                            return;
                        }
                        if (detail.selectedOption.value === RagRepositoryType.PGVECTOR) {
                            if (item.rdsConfig === undefined) {
                                setFields({ 'rdsConfig': getDefaults(RdsInstanceConfig) });
                            }
                            setFields({ 'opensearchConfig': undefined });
                        }
                        if (detail.selectedOption.value === RagRepositoryType.OPENSEARCH) {
                            if (item.opensearchConfig === undefined) {
                                setFields({ 'opensearchConfig': getDefaults(OpenSearchNewClusterConfig) });
                            }
                            setFields({ 'rdsConfig': undefined });
                        }
                        setFields({ 'type': detail.selectedOption.value });
                    }}
                    onBlur={() => touchFields(['type'])}
                    options={Object.keys(RagRepositoryType).map((key) => ({
                        label: key,
                        value: RagRepositoryType[key],
                    }),
                    )}
                    disabled={isEdit}
                />
            </FormField>
            {item.type === RagRepositoryType.PGVECTOR &&
                <RdsConfigForm item={item.rdsConfig} setFields={setFields} touchFields={touchFields}
                    formErrors={formErrors} isEdit={isEdit}></RdsConfigForm>}

            {item.type === RagRepositoryType.OPENSEARCH &&
                <OpenSearchConfigForm item={item.opensearchConfig} setFields={setFields} touchFields={touchFields}
                    formErrors={formErrors} isEdit={isEdit}></OpenSearchConfigForm>
            }
            <ArrayInputField label='Allowed Groups'
                errorText={formErrors?.allowedGroups}
                values={item.allowedGroups ?? []}
                onChange={(detail) => setFields({ 'allowedGroups': detail })}
                description={'The groups provided by the Identity Provider that have access to this repository. If no groups are specified, access is granted to everyone.'}
            ></ArrayInputField>

        </SpaceBetween>
    );
}

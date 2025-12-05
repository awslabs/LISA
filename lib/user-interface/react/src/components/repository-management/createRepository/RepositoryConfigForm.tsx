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
    RagRepositoryConfigSchema,
    RagRepositoryType,
    RdsInstanceConfig,
    BedrockKnowledgeBaseInstanceConfig
} from '#root/lib/schema';
import { RdsConfigForm } from './RdsConfigForm';
import { OpenSearchConfigForm } from './OpenSearchConfigForm';
import { BedrockKnowledgeBaseConfigForm } from './BedrockKnowledgeBaseConfigForm';
import { CommonFieldsForm } from '../../../shared/form/CommonFieldsForm';

export type RepositoryConfigProps = {
    isEdit: boolean
};

export function RepositoryConfigForm (props: FormProps<RagRepositoryConfig> & RepositoryConfigProps): ReactElement {
    const { item, touchFields, setFields, formErrors, isEdit } = props;
    const shape = RagRepositoryConfigSchema.shape;

    return (
        <SpaceBetween size={'s'}>
            <FormField label='Repository ID'
                errorText={formErrors?.repositoryId}
                description={shape.repositoryId.description}
                constraintText='Required. Only lowercase alphanumeric characters and hyphens allowed.'>
                <Input value={item.repositoryId} inputMode='text'
                    onBlur={() => touchFields(['repositoryId'])}
                    onChange={({ detail }) => {
                        setFields({ 'repositoryId': detail.value });
                    }} disabled={isEdit} placeholder='postgres-rag' />
            </FormField>
            <FormField label='Repository Name - optional'
                errorText={formErrors?.repositoryName}
                description={shape.repositoryName.description}>
                <Input value={item.repositoryName} inputMode='text'
                    onBlur={() => touchFields(['repositoryName'])}
                    onChange={({ detail }) => {
                        setFields({ 'repositoryName': detail.value });
                    }} placeholder='Postgres RAG' />
            </FormField>

            <FormField label='Description - optional'
                errorText={formErrors?.description}
                description={shape.description.description}>
                <Input value={item.description} inputMode='text'
                    onBlur={() => touchFields(['description'])}
                    onChange={({ detail }) => {
                        setFields({ 'description': detail.value });
                    }} placeholder='A repository for storing RAG documents' />
            </FormField>

            {/* Common Fields: Embedding Model */}
            <CommonFieldsForm
                item={item}
                setFields={setFields}
                touchFields={touchFields}
                formErrors={formErrors}
                showEmbeddingModel={item.type !== RagRepositoryType.BEDROCK_KNOWLEDGE_BASE}
                showAllowedGroups={false}
            />

            <FormField label='Repository Type'
                errorText={formErrors?.type}
                description={shape.type.description}>
                <Select
                    selectedOption={{ label: item.type, value: item.type }}
                    onChange={({ detail }) => {
                        if (item.type === detail.selectedOption.value) {
                            return;
                        }
                        if (detail.selectedOption.value === RagRepositoryType.PGVECTOR) {
                            if (item.rdsConfig === undefined) {
                                setFields({ 'rdsConfig': RdsInstanceConfig.parse({}) });
                            }
                            setFields({ 'opensearchConfig': undefined });
                            setFields({ 'bedrockKnowledgeBaseConfig': undefined });
                        }
                        if (detail.selectedOption.value === RagRepositoryType.OPENSEARCH) {
                            if (item.opensearchConfig === undefined) {
                                setFields({ 'opensearchConfig': OpenSearchNewClusterConfig.parse({}) });
                            }
                            setFields({ 'rdsConfig': undefined });
                            setFields({ 'bedrockKnowledgeBaseConfig': undefined });
                        }
                        if (detail.selectedOption.value === RagRepositoryType.BEDROCK_KNOWLEDGE_BASE) {
                            if (item.bedrockKnowledgeBaseConfig === undefined) {
                                setFields({ 'bedrockKnowledgeBaseConfig': BedrockKnowledgeBaseInstanceConfig.parse({}) });
                            }
                            setFields({ 'rdsConfig': undefined });
                            setFields({ 'opensearchConfig': undefined });
                        }

                        // Clear collection IDs from all pipelines when repository type changes
                        if (item.pipelines && item.pipelines.length > 0) {
                            const clearedPipelines = item.pipelines.map((pipeline) => ({
                                ...pipeline,
                                collectionId: undefined
                            }));
                            setFields({ 'pipelines': clearedPipelines });
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
            {item.type === RagRepositoryType.BEDROCK_KNOWLEDGE_BASE &&
                <BedrockKnowledgeBaseConfigForm item={item} setFields={setFields} touchFields={touchFields}
                    formErrors={formErrors} isEdit={isEdit}></BedrockKnowledgeBaseConfigForm>
            }

            {/* Common Fields: Allowed Groups */}
            <CommonFieldsForm
                item={item}
                setFields={setFields}
                touchFields={touchFields}
                formErrors={formErrors}
                showEmbeddingModel={false}
                showAllowedGroups={true}
            />

        </SpaceBetween>
    );
}

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

import React, { ReactElement, useMemo } from 'react';
import { FormProps } from '../../../shared/form/form-props';
import FormField from '@cloudscape-design/components/form-field';
import Input from '@cloudscape-design/components/input';
import Select from '@cloudscape-design/components/select';
import { SpaceBetween, Textarea } from '@cloudscape-design/components';
import { useListRagRepositoriesQuery } from '../../../shared/reducers/rag.reducer';
import { CommonFieldsForm } from '../../../shared/form/CommonFieldsForm';
import { RagCollectionConfig, RagRepositoryType, VectorStoreStatus } from '#root/lib/schema';

export type CollectionConfigProps = {
    isEdit: boolean;
};

export function CollectionConfigForm (
    props: FormProps<RagCollectionConfig> & CollectionConfigProps
): ReactElement {
    const { item, touchFields, setFields, formErrors, isEdit } = props;

    // Fetch repositories for dropdown
    const { data: repositories, isLoading: isLoadingRepos } = useListRagRepositoriesQuery(undefined, {
        refetchOnMountOrArgChange: 5
    });

    // Repository options
    const repositoryOptions = useMemo(() => {
        if (!repositories || !Array.isArray(repositories)) {
            return [];
        }
        return repositories
            .filter((repository) =>
                repository.status && [
                    VectorStoreStatus.CREATE_COMPLETE,
                    VectorStoreStatus.UPDATE_COMPLETE,
                    VectorStoreStatus.UPDATE_COMPLETE_CLEANUP_IN_PROGRESS,
                    VectorStoreStatus.UPDATE_IN_PROGRESS,
                ].includes(repository.status)
            )
            // BRK not supported yet
            .filter((repo) => repo.type !== RagRepositoryType.BEDROCK_KNOWLEDGE_BASE)
            .map((repo) => ({
                label: repo.repositoryName || repo.repositoryId,
                value: repo.repositoryId,
            }));
    }, [repositories]);

    return (
        <SpaceBetween size='s'>
            {/* Collection Name */}
            <FormField
                label='Collection Name'
                errorText={formErrors?.name}
                description='A user-friendly name for the collection'
            >
                <Input
                    value={item.name || ''}
                    onChange={({ detail }) => setFields({ name: detail.value })}
                    onBlur={() => touchFields(['name'])}
                    placeholder='Documents'
                />
            </FormField>

            {/* Description */}
            <FormField
                label='Description (optional)'
                errorText={formErrors?.description}
                description="A brief description of the collection's purpose"
            >
                <Textarea
                    value={item.description || ''}
                    onChange={({ detail }) => setFields({ description: detail.value })}
                    onBlur={() => touchFields(['description'])}
                    placeholder='Collection of documents'
                    rows={3}
                />
            </FormField>

            {/* Repository Selection */}
            <FormField
                label='Repository'
                errorText={formErrors?.repositoryId}
                description='The parent repository that will contain this collection'
            >
                <Select
                    selectedOption={
                        item.repositoryId
                            ? repositoryOptions.find((opt) => opt.value === item.repositoryId) || null
                            : null
                    }
                    onChange={({ detail }) => {
                        setFields({ repositoryId: detail.selectedOption.value });
                    }}
                    onBlur={() => touchFields(['repositoryId'])}
                    options={repositoryOptions}
                    disabled={isEdit}
                    placeholder='Select a repository'
                    statusType={isLoadingRepos ? 'loading' : 'finished'}
                />
            </FormField>

            {/* Common Fields (Embedding Model) */}
            <CommonFieldsForm
                item={item}
                setFields={setFields}
                touchFields={touchFields}
                formErrors={formErrors}
                repositoryId={item.repositoryId}
                showEmbeddingModel={true}
                showAllowedGroups={false}
                isEdit={isEdit}
            />
        </SpaceBetween>
    );
}

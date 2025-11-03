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
import { Checkbox, SpaceBetween, Textarea } from '@cloudscape-design/components';
import { useListRagRepositoriesQuery } from '../../../shared/reducers/rag.reducer';
import { CommonFieldsForm } from '../../../shared/form/CommonFieldsForm';
import { CreateCollectionRequest } from '#root/lib/schema';

export type CollectionConfigProps = {
    isEdit: boolean;
};

type CollectionConfigFormItem = CreateCollectionRequest & { repositoryId: string };

export function CollectionConfigForm(
    props: FormProps<CollectionConfigFormItem> & CollectionConfigProps
): ReactElement {
    const { item, touchFields, setFields, formErrors, isEdit } = props;
    
    // Fetch repositories for dropdown
    const { data: repositories, isLoading: isLoadingRepos } = useListRagRepositoriesQuery(undefined, {
        refetchOnMountOrArgChange: 5
    });
    
    // Repository options
    const repositoryOptions = useMemo(() => {
        return repositories?.map((repo) => ({
            label: repo.repositoryName || repo.repositoryId,
            value: repo.repositoryId,
        })) || [];
    }, [repositories]);
    
    return (
        <SpaceBetween size="s">
            {/* Collection Name */}
            <FormField 
                label="Collection Name"
                errorText={formErrors?.name}
                description="A user-friendly name for the collection"
            >
                <Input
                    value={item.name || ''}
                    onChange={({ detail }) => setFields({ name: detail.value })}
                    onBlur={() => touchFields(['name'])}
                    placeholder="Engineering Documents"
                />
            </FormField>
            
            {/* Description */}
            <FormField 
                label="Description (optional)"
                errorText={formErrors?.description}
                description="A brief description of the collection's purpose"
            >
                <Textarea
                    value={item.description || ''}
                    onChange={({ detail }) => setFields({ description: detail.value })}
                    onBlur={() => touchFields(['description'])}
                    placeholder="Collection of engineering documentation and specifications"
                    rows={3}
                />
            </FormField>
            
            {/* Repository Selection */}
            <FormField 
                label="Repository"
                errorText={formErrors?.repositoryId}
                description="The parent repository that will contain this collection"
            >
                <Select
                    selectedOption={
                        item.repositoryId 
                            ? repositoryOptions.find(opt => opt.value === item.repositoryId) || null
                            : null
                    }
                    onChange={({ detail }) => {
                        setFields({ repositoryId: detail.selectedOption.value });
                    }}
                    onBlur={() => touchFields(['repositoryId'])}
                    options={repositoryOptions}
                    disabled={isEdit}
                    placeholder="Select a repository"
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
            
            {/* Private Checkbox */}
            <FormField
                label="Privacy"
                description="Private collections are only accessible to the creator and administrators"
            >
                <Checkbox
                    checked={item.private || false}
                    onChange={({ detail }) => setFields({ private: detail.checked })}
                    disabled={isEdit}
                >
                    Make this collection private
                </Checkbox>
            </FormField>
            
            {/* Pipeline Configuration */}
            <FormField
                label="Pipeline Configuration"
                description="Optional: Configure automatic ingestion from S3"
            >
                <Checkbox
                    checked={item.pipelines && item.pipelines.length > 0}
                    onChange={({ detail }) => {
                        if (detail.checked) {
                            setFields({ 
                                pipelines: [{ 
                                    s3Bucket: '', 
                                    s3Prefix: '',
                                    trigger: 'event' as const,
                                    autoRemove: true,
                                }] 
                            });
                        } else {
                            setFields({ pipelines: [] });
                        }
                    }}
                >
                    Enable S3 pipeline ingestion
                </Checkbox>
            </FormField>
            
            {/* S3 Bucket - only show if pipeline is enabled */}
            {item.pipelines && item.pipelines.length > 0 && (
                <>
                    <FormField
                        label="S3 Bucket"
                        errorText={formErrors?.pipelines?.[0]?.s3Bucket}
                        description="S3 bucket to monitor for new documents"
                    >
                        <Input
                            value={item.pipelines[0].s3Bucket || ''}
                            onChange={({ detail }) => {
                                const updatedPipelines = [...(item.pipelines || [])];
                                updatedPipelines[0] = {
                                    ...updatedPipelines[0],
                                    s3Bucket: detail.value
                                };
                                setFields({ pipelines: updatedPipelines });
                            }}
                            onBlur={() => touchFields(['pipelines.0.s3Bucket'])}
                            placeholder="my-documents-bucket"
                        />
                    </FormField>
                    
                    <FormField
                        label="S3 Prefix (optional)"
                        errorText={formErrors?.pipelines?.[0]?.s3Prefix}
                        description="Optional: Only monitor objects with this prefix"
                    >
                        <Input
                            value={item.pipelines[0].s3Prefix || ''}
                            onChange={({ detail }) => {
                                const updatedPipelines = [...(item.pipelines || [])];
                                updatedPipelines[0] = {
                                    ...updatedPipelines[0],
                                    s3Prefix: detail.value
                                };
                                setFields({ pipelines: updatedPipelines });
                            }}
                            onBlur={() => touchFields(['pipelines.0.s3Prefix'])}
                            placeholder="documents/engineering/"
                        />
                    </FormField>
                </>
            )}
        </SpaceBetween>
    );
}

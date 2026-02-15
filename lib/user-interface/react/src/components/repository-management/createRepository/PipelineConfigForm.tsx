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

import { ReactElement, useMemo } from 'react';
import {
    Button,
    Container,
    FormField,
    Header,
    Input,
    Select,
    SpaceBetween,
    Toggle,
} from '@cloudscape-design/components';
import { FormProps } from '../../../shared/form/form-props';

import { PipelineConfig, RagRepositoryPipeline, RagRepositoryType, FixedSizeChunkingStrategySchema } from '#root/lib/schema';
import { useListCollectionsQuery } from '@/shared/reducers/rag.reducer';
import { ChunkingConfigForm } from '@/shared/form/ChunkingConfigForm';
import { MetadataForm } from '@/shared/form/MetadataForm';

export type PipelineConfigProps = {
    isEdit: boolean;
    repositoryId?: string;
    repositoryType?: RagRepositoryType;
    existingPipelines?: PipelineConfig[];
};

export function PipelineConfigForm (props: FormProps<PipelineConfig[]> & PipelineConfigProps): ReactElement {
    const { item, touchFields, setFields, formErrors, isEdit, repositoryId, repositoryType, existingPipelines = [] } = props;

    // Build a set of pipeline keys from the original pipelines to identify which are existing vs new.
    // Mirrors _get_pipeline_key from the backend: collectionId:s3Bucket:s3Prefix
    const existingPipelineKeys = useMemo(() => {
        return new Set(
            existingPipelines.map((p) => `${p.collectionId || ''}:${p.s3Bucket || ''}:${p.s3Prefix || ''}`)
        );
    }, [existingPipelines]);

    const isExistingPipeline = (pipeline: PipelineConfig): boolean => {
        const key = `${pipeline.collectionId || ''}:${pipeline.s3Bucket || ''}:${pipeline.s3Prefix || ''}`;
        return existingPipelineKeys.has(key);
    };

    // Only query collections if we have a repositoryId (editing existing repository)
    const { data: collections, isFetching: isFetchingCollections } = useListCollectionsQuery(
        { repositoryId: repositoryId || '' },
        {
            skip: !repositoryId || !isEdit,
            refetchOnMountOrArgChange: 5,
        }
    );

    const collectionOptions = useMemo(() => {
        // For new repositories, show a default option
        if (!isEdit || !repositoryId) {
            return [
                {
                    value: 'default',
                    label: 'Default collection',
                    description: 'Documents will be ingested into the default collection',
                }
            ];
        }

        // For existing repositories, show actual collections
        return collections?.map((collection) => ({
            value: collection.collectionId,
            label: collection.name || collection.collectionId,
            description: collection.description,
        })) || [];
    }, [collections, isEdit, repositoryId]);

    const onChange = (index: number, field: keyof PipelineConfig, value: any) => {
        setFields({ [`pipelines[${index}].${field}`]: value });
    };

    const addConfig = () => {
        const newPipeline = RagRepositoryPipeline.partial().parse({
            chunkingStrategy: FixedSizeChunkingStrategySchema.parse({})
        });
        setFields({ pipelines: [...(item || []), newPipeline] });
    };

    const removeConfig = (index: number) => {
        const pipelines = item.filter((_, i) => i !== index);
        setFields({ pipelines: pipelines });
    };

    // Hide pipeline configuration for Bedrock KB - it's managed automatically
    if (repositoryType === RagRepositoryType.BEDROCK_KNOWLEDGE_BASE) {
        return (
            <Container
                header={
                    <Header variant='h2' info={
                        <span>Pipeline configuration is automatically managed for Bedrock Knowledge Base repositories</span>
                    }>
                        Pipeline Configuration
                    </Header>
                }>
                <SpaceBetween size='s'>
                    <div>
                        <strong>Automatic Configuration:</strong>
                        <ul style={{ marginTop: '8px', marginLeft: '20px' }}>
                            <li>EventBridge rules are created automatically for the KB data source S3 bucket</li>
                            <li>Documents are tracked when uploaded to the data source bucket</li>
                            <li>Document removal is tracked automatically</li>
                            <li>No manual pipeline configuration needed</li>
                        </ul>
                    </div>
                </SpaceBetween>
            </Container>
        );
    }

    return (
        <SpaceBetween size={'s'}>
            {item?.map((pipeline, index) => (
                <Container
                    key={index}
                    header={
                        <Header
                            variant='h2'
                            actions={
                                <Button
                                    variant='icon'
                                    iconName='remove'
                                    ariaLabel='Remove pipeline'
                                    onClick={() => removeConfig(index)} />
                            }>
                            Pipeline {index + 1} {isEdit && !isExistingPipeline(pipeline) ? '(new)' : ''}
                        </Header>
                    }>
                    <SpaceBetween size={'s'}>
                        <ChunkingConfigForm
                            item={pipeline.chunkingStrategy}
                            setFields={(values) => {
                                const updatedFields: Record<string, unknown> = {};
                                // Store using the new chunkingStrategy structure
                                if (values.chunkingStrategy) {
                                    updatedFields[`pipelines[${index}].chunkingStrategy`] = values.chunkingStrategy;
                                }
                                if (values['chunkingStrategy.size'] !== undefined) {
                                    updatedFields[`pipelines[${index}].chunkingStrategy.size`] = values['chunkingStrategy.size'];
                                }
                                if (values['chunkingStrategy.overlap'] !== undefined) {
                                    updatedFields[`pipelines[${index}].chunkingStrategy.overlap`] = values['chunkingStrategy.overlap'];
                                }
                                setFields(updatedFields);
                            }}
                            touchFields={(fields) => {
                                const updatedFields = fields.map((field) => `pipelines[${index}].${field}`);
                                touchFields(updatedFields);
                            }}
                            formErrors={formErrors.pipelines?.[index] || {}}
                            disabled={isEdit && isExistingPipeline(pipeline)}
                        />

                        <MetadataForm
                            tags={pipeline.metadata?.tags || []}
                            onTagsChange={(tags) => {
                                setFields({
                                    [`pipelines[${index}].metadata.tags`]: tags
                                });
                            }}
                            errorText={formErrors.pipelines?.[index]?.metadata?.tags}
                            disabled={isEdit && isExistingPipeline(pipeline)}
                        />

                        <FormField
                            label='Collection'
                            errorText={formErrors.pipelines?.[index]?.collectionId}
                            description='The collection to ingest documents into'
                        >
                            <Select
                                options={collectionOptions}
                                selectedOption={collectionOptions.find((opt) => opt.value === pipeline.collectionId) || null}
                                loadingText='Loading collections'
                                placeholder='Select a collection'
                                onBlur={() => touchFields([`pipelines[${index}].collectionId`])}
                                filteringType='auto'
                                onChange={({ detail }) =>
                                    onChange(index, 'collectionId', detail.selectedOption.value)}
                                statusType={isFetchingCollections ? 'loading' : 'finished'}
                                virtualScroll
                                disabled={isEdit && isExistingPipeline(pipeline)}
                            />
                        </FormField>

                        <FormField
                            label='S3 Bucket'
                            constraintText='Required'
                            errorText={formErrors.pipelines?.[index]?.s3Bucket}
                            description={isEdit && isExistingPipeline(pipeline) ? 'S3 bucket cannot be changed for existing pipelines (requires infrastructure redeployment)' : RagRepositoryPipeline.shape.s3Bucket.description}
                        >
                            <Input
                                value={pipeline.s3Bucket}
                                onChange={({ detail }) =>
                                    onChange(index, 's3Bucket', detail.value)
                                }
                                onBlur={() => touchFields([`pipelines[${index}].s3Bucket`])}
                                placeholder='my-documents-bucket'
                                disabled={isEdit && isExistingPipeline(pipeline)}
                            />
                        </FormField>

                        <FormField
                            label='S3 Prefix (optional)'
                            errorText={formErrors.pipelines?.[index]?.s3Prefix}
                            description={isEdit && isExistingPipeline(pipeline) ? 'S3 prefix cannot be changed for existing pipelines (requires infrastructure redeployment)' : RagRepositoryPipeline.shape.s3Prefix.description}>
                            <Input
                                value={pipeline.s3Prefix}
                                onChange={({ detail }) =>
                                    onChange(index, 's3Prefix', detail.value)
                                }
                                onBlur={() => touchFields([`pipelines[${index}].s3Prefix`])}
                                placeholder='documents/engineering/'
                                disabled={isEdit && isExistingPipeline(pipeline)}
                            />
                        </FormField>

                        <FormField
                            label='Trigger'
                            errorText={formErrors.pipelines?.[index]?.trigger}
                            description={isEdit && isExistingPipeline(pipeline) ? 'Trigger type cannot be changed for existing pipelines (requires infrastructure redeployment)' : RagRepositoryPipeline.shape.trigger.description}>
                            <Select
                                selectedOption={{ label: pipeline.trigger, value: pipeline.trigger }}
                                onChange={({ detail }) =>
                                    onChange(index, 'trigger', detail.selectedOption.value as 'daily' | 'event')
                                }
                                options={[
                                    { label: 'Daily', value: 'daily', description: 'This ingestion pipeline is scheduled to run once per day.' },
                                    { label: 'Event', value: 'event', description: 'This ingestion pipeline runs whenever changes are detected.' },
                                ]}
                                onBlur={() => touchFields([`pipelines[${index}].trigger`])}
                                disabled={isEdit && isExistingPipeline(pipeline)}
                            />
                        </FormField>

                        <FormField
                            label='Auto Remove'
                            errorText={formErrors.pipelines?.[index]?.autoRemove}
                            description={isEdit && isExistingPipeline(pipeline) ? 'Auto remove setting cannot be changed for existing pipelines (requires infrastructure redeployment)' : RagRepositoryPipeline.shape.autoRemove.description}
                        >
                            <Toggle
                                checked={pipeline.autoRemove}
                                onChange={({ detail }) =>
                                    onChange(index, 'autoRemove', detail.checked)
                                }
                                disabled={isEdit && isExistingPipeline(pipeline)}
                            />
                        </FormField>
                    </SpaceBetween>
                </Container>
            ))}

            <Button
                iconName='add-plus'
                variant='normal'
                onClick={addConfig}>
                Add Configuration
            </Button>
            {isEdit && (
                <div style={{ fontSize: '14px', color: '#5f6b7a', marginTop: '8px' }}>
                    <strong>Note:</strong> Adding or removing pipelines requires infrastructure redeployment.
                    Existing pipeline configurations (collection, S3 bucket, S3 prefix, trigger, auto remove) cannot be modified.
                    To change these fields, remove the existing pipeline and add a new one.
                </div>
            )}
        </SpaceBetween>
    );
}

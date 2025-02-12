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

import { PipelineConfig, RagRepositoryPipeline } from '../../../../../../configSchema';
import { getDefaults } from '../../../shared/util/zodUtil';
import { useGetAllModelsQuery } from '../../../shared/reducers/model-management.reducer';
import { ModelStatus, ModelType } from '../../../shared/model/model-management.model';

export type PipelineConfigProps = {
    isEdit: boolean
};

export function PipelineConfigForm (props: FormProps<PipelineConfig[]> & PipelineConfigProps): ReactElement {
    const { item, touchFields, setFields, formErrors, isEdit } = props;

    const { data: allModels, isFetching: isFetchingModels } = useGetAllModelsQuery(undefined, {
        refetchOnMountOrArgChange: 5,
        selectFromResult: (state) => ({
            isFetching: state.isFetching,
            data: (state.data || []).filter((model) => model.modelType === ModelType.embedding && model.status === ModelStatus.InService),
        }),
    });
    const embeddingOptions = useMemo(() => {
        return allModels?.map((model) => ({ value: model.modelId })) || [];
    }, [allModels]);

    const onChange = (index: number, field: keyof PipelineConfig, value: any) => {
        setFields({ [`pipelines[${index}].${field}`]: value });
    };

    const addConfig = () => {
        setFields({ pipelines: [...(item || []), getDefaults(RagRepositoryPipeline)] });
    };

    const removeConfig = (index: number) => {
        const pipelines = item.filter((_, i) => i !== index);
        setFields({ pipelines: pipelines });
    };

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
                                    disabled={isEdit}
                                    onClick={() => removeConfig(index)} />
                            }>
                            Pipeline {index + 1}
                        </Header>
                    }>
                    <SpaceBetween size={'s'}>
                        <FormField
                            label='Chunk Size'
                            errorText={formErrors.pipelines?.[index]?.chunkSize}
                        >
                            <Input
                                type='number' inputMode='numeric'
                                value={pipeline.chunkSize?.toString()}
                                onChange={({ detail }) =>
                                    onChange(index, 'chunkSize', Number(detail.value))
                                }
                                onBlur={() => touchFields([`pipelines[${index}].chunkSize`])}
                            />
                        </FormField>

                        <FormField
                            label='Chunk Overlap'
                            errorText={formErrors.pipelines?.[index]?.chunkOverlap}
                        >
                            <Input
                                type='number' inputMode='numeric'
                                value={pipeline.chunkOverlap?.toString()}
                                onChange={({ detail }) =>
                                    onChange(index, 'chunkOverlap', Number(detail.value))
                                }
                                onBlur={() => touchFields([`pipelines[${index}].chunkOverlap`])}
                            />
                        </FormField>

                        <FormField
                            label='Embedding Model'
                            errorText={formErrors.pipelines?.[index]?.embeddingModel}
                        >
                            <Select
                                options={embeddingOptions}
                                selectedOption={{ value: pipeline.embeddingModel }}
                                loadingText='Loading models'
                                onBlur={() => touchFields([`pipelines[${index}].embeddingModel`])}
                                filteringType='auto'
                                onChange={({ detail }) =>
                                    onChange(index, 'embeddingModel', detail.selectedOption.value)}
                                statusType={isFetchingModels ? 'loading' : 'finished'}
                                virtualScroll
                            />
                        </FormField>

                        <FormField
                            label='S3 Bucket'
                            errorText={formErrors.pipelines?.[index]?.s3Bucket}
                        >
                            <Input
                                value={pipeline.s3Bucket}
                                onChange={({ detail }) =>
                                    onChange(index, 's3Bucket', detail.value)
                                }
                                onBlur={() => touchFields([`pipelines[${index}].s3Bucket`])}
                            />
                        </FormField>

                        <FormField
                            label='S3 Prefix'
                            errorText={formErrors.pipelines?.[index]?.s3Prefix}>
                            <Input
                                value={pipeline.s3Prefix}
                                onChange={({ detail }) =>
                                    onChange(index, 's3Prefix', detail.value)
                                }
                                onBlur={() => touchFields([`pipelines[${index}].s3Prefix`])}
                            />
                        </FormField>

                        <FormField
                            label='Trigger'
                            errorText={formErrors.pipelines?.[index]?.trigger}>
                            <Select
                                selectedOption={{ label: pipeline.trigger, value: pipeline.trigger }}
                                onChange={({ detail }) =>
                                    onChange(index, 'trigger', detail.selectedOption.value as 'daily' | 'event')
                                }
                                options={[
                                    { label: 'Daily', value: 'daily' },
                                    { label: 'Event', value: 'event' },
                                ]}
                                onBlur={() => touchFields([`pipelines[${index}].trigger`])}
                            />
                        </FormField>

                        <FormField
                            label='Auto Remove'
                            errorText={formErrors.pipelines?.[index]?.autoRemove}
                        >
                            <Toggle
                                checked={pipeline.autoRemove}
                                onChange={({ detail }) =>
                                    onChange(index, 'autoRemove', detail.checked)
                                }
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
        </SpaceBetween>
    );
}

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
import FormField from '@cloudscape-design/components/form-field';
import { Autosuggest } from '@cloudscape-design/components';
import { useGetAllModelsQuery } from '../reducers/model-management.reducer';
import { ModelStatus, ModelType } from '../model/model-management.model';

export type EmbeddingModelInputProps = {
    value?: string;
    onChange: (modelId: string) => void;
    onBlur?: () => void;
    errorText?: string;
    disabled?: boolean;
    label?: string;
    description?: string;
    placeholder?: string;
};

export function EmbeddingModelInput (props: EmbeddingModelInputProps): ReactElement {
    const {
        value = '',
        onChange,
        onBlur,
        errorText,
        disabled = false,
        label = 'Embedding model',
        description = 'The model used to generate vector embeddings for documents',
        placeholder = 'Select an embedding model',
    } = props;

    // Fetch embedding models
    const { data: embeddingModels, isFetching: isFetchingEmbeddingModels } =
        useGetAllModelsQuery(undefined, {
            refetchOnMountOrArgChange: 5,
            selectFromResult: (state) => ({
                isFetching: state.isFetching,
                data: (state.data || []).filter(
                    (model) =>
                        model.modelType === ModelType.embedding &&
                        model.status === ModelStatus.InService
                ),
            })
        });

    // Embedding model options
    const embeddingOptions = useMemo(() => {
        return embeddingModels?.map((model) => ({
            value: model.modelId,
            label: model.modelName || model.modelId,
        })) || [];
    }, [embeddingModels]);

    return (
        <FormField
            label={label}
            errorText={errorText}
            description={description}
        >
            <Autosuggest
                statusType={isFetchingEmbeddingModels ? 'loading' : 'finished'}
                loadingText='Loading embedding models...'
                placeholder={placeholder}
                empty={<div className='text-gray-500'>No embedding models available.</div>}
                filteringType='auto'
                value={value}
                enteredTextLabel={(text) => `Use: "${text}"`}
                onChange={({ detail }) => onChange(detail.value)}
                onBlur={onBlur}
                options={embeddingOptions}
                disabled={disabled}
            />
        </FormField>
    );
}

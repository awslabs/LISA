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
import FormField from '@cloudscape-design/components/form-field';
import { Autosuggest, SpaceBetween } from '@cloudscape-design/components';
import { useGetAllModelsQuery } from '../reducers/model-management.reducer';
import { ModelStatus, ModelType } from '../model/model-management.model';
import { ArrayInputField } from './array-input';
import { ModifyMethod } from './form-props';

export type CommonFieldsFormProps = {
    item: any;
    setFields(values: { [key: string]: any }, method?: ModifyMethod): void;
    touchFields(fields: string[], method?: ModifyMethod): void;
    formErrors: any;
    repositoryId?: string;
    showEmbeddingModel?: boolean;
    showAllowedGroups?: boolean;
    isEdit?: boolean;
};

export function CommonFieldsForm(props: CommonFieldsFormProps): ReactElement {
    const {
        item,
        setFields,
        touchFields,
        formErrors,
        showEmbeddingModel = true,
        showAllowedGroups = true,
        isEdit = false,
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

    // Get the current embedding model value (support both field names)
    const embeddingModelValue = item.embeddingModel || item.embeddingModelId || '';

    return (
        <SpaceBetween size="s">
            {/* Embedding Model Selector */}
            {showEmbeddingModel && (
                <FormField
                    label="Embedding Model"
                    errorText={formErrors?.embeddingModel || formErrors?.embeddingModelId}
                    description="The model used to generate vector embeddings for documents"
                >
                    <Autosuggest
                        statusType={isFetchingEmbeddingModels ? 'loading' : 'finished'}
                        loadingText="Loading embedding models..."
                        placeholder="Select an embedding model"
                        empty={<div className="text-gray-500">No embedding models available.</div>}
                        filteringType="auto"
                        value={embeddingModelValue}
                        enteredTextLabel={(text) => `Use: "${text}"`}
                        onChange={({ detail }) => {
                            // Support both embeddingModel (collections) and embeddingModelId (repositories)
                            if ('embeddingModel' in item) {
                                setFields({ embeddingModel: detail.value });
                            } else {
                                setFields({ embeddingModelId: detail.value });
                            }
                        }}
                        onBlur={() => {
                            touchFields(['embeddingModel', 'embeddingModelId']);
                        }}
                        options={embeddingOptions}
                        disabled={isEdit}
                    />
                </FormField>
            )}

            {/* Allowed Groups */}
            {showAllowedGroups && (
                <ArrayInputField
                    label="Allowed Groups"
                    errorText={formErrors?.allowedGroups}
                    values={item.allowedGroups || []}
                    onChange={(groups) => setFields({ allowedGroups: groups })}
                    description="User groups that can access this resource. Leave empty for public access."
                />
            )}
        </SpaceBetween>
    );
}

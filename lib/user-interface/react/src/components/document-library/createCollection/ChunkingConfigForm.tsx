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

import { ReactElement } from 'react';
import FormField from '@cloudscape-design/components/form-field';
import Input from '@cloudscape-design/components/input';
import Select from '@cloudscape-design/components/select';
import { SpaceBetween } from '@cloudscape-design/components';
import { ChunkingStrategy, ChunkingStrategyType } from '#root/lib/schema';
import { ModifyMethod } from '@/shared/form/form-props';

// Utility function to create default chunking strategy
function createDefaultChunkingStrategy () {
    return {
        type: ChunkingStrategyType.FIXED,
        size: 512,
        overlap: 51,
    };
}

export type ChunkingConfigFormProps = {
    item: ChunkingStrategy | undefined;
    setFields(values: { [key: string]: any }, method?: ModifyMethod): void;
    touchFields(fields: string[], method?: ModifyMethod): void;
    formErrors: any;
    disabled?: boolean;
};

export function ChunkingConfigForm (props: ChunkingConfigFormProps): ReactElement {
    const { item, touchFields, setFields, formErrors, disabled = false } = props;

    // Chunking type options
    const chunkingTypeOptions = [
        { label: 'Fixed Size', value: ChunkingStrategyType.FIXED },
        { label: 'None (No Chunking)', value: ChunkingStrategyType.NONE },
        // Future: { label: 'Semantic', value: ChunkingStrategyType.SEMANTIC },
        // Future: { label: 'Recursive', value: ChunkingStrategyType.RECURSIVE },
    ];

    return (
        <SpaceBetween size='s'>
            {/* Chunking Type */}
            <FormField
                label='Chunking Type'
                errorText={formErrors?.['chunkingStrategy.type'] || formErrors?.chunkingStrategy?.type}
                description={disabled
                    ? 'Chunking is managed by Bedrock Knowledge Base'
                    : 'How documents should be split into chunks'}
            >
                <Select
                    selectedOption={
                        item?.type === ChunkingStrategyType.NONE
                            ? { label: 'None (No Chunking)', value: ChunkingStrategyType.NONE }
                            : item?.type
                                ? { label: 'Fixed Size', value: item.type }
                                : { label: 'Fixed Size', value: ChunkingStrategyType.FIXED }
                    }
                    onChange={({ detail }) => {
                        if (detail.selectedOption.value === ChunkingStrategyType.FIXED) {
                            setFields({
                                chunkingStrategy: createDefaultChunkingStrategy()
                            });
                        } else if (detail.selectedOption.value === ChunkingStrategyType.NONE) {
                            setFields({
                                chunkingStrategy: { type: ChunkingStrategyType.NONE }
                            });
                        }
                    }}
                    options={chunkingTypeOptions}
                    placeholder='Select chunking type'
                    disabled={disabled}
                />
            </FormField>

            {/* Fixed Size Configuration */}
            {item?.type === ChunkingStrategyType.FIXED && (
                <>
                    <FormField
                        label='Chunk Size'
                        errorText={formErrors?.['chunkingStrategy.size'] || formErrors?.chunkingStrategy?.size}
                        description='Size of each chunk in characters (100-10000)'
                    >
                        <Input
                            type='number'
                            value={String(item.size || 512)}
                            onChange={({ detail }) => {
                                setFields({
                                    'chunkingStrategy.size': Number(detail.value)
                                });
                            }}
                            onBlur={() => touchFields(['chunkingStrategy.size'])}
                            disabled={disabled}
                        />
                    </FormField>

                    <FormField
                        label='Chunk Overlap'
                        errorText={formErrors?.['chunkingStrategy.overlap'] || formErrors?.chunkingStrategy?.overlap}
                        description='Overlap between chunks in characters (must be ≤ size/2)'
                    >
                        <Input
                            type='number'
                            value={String(item.overlap || 51)}
                            onChange={({ detail }) => {
                                setFields({
                                    'chunkingStrategy.overlap': Number(detail.value)
                                });
                            }}
                            onBlur={() => touchFields(['chunkingStrategy.overlap'])}
                            disabled={disabled}
                        />
                    </FormField>
                </>
            )}
        </SpaceBetween>
    );
}

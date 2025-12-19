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
import { SpaceBetween, FormField, Checkbox } from '@cloudscape-design/components';
import { ChunkingConfigForm } from '@/shared/form/ChunkingConfigForm';
import { MetadataForm } from '@/shared/form/MetadataForm';
import { ChunkingStrategy } from '#root/lib/schema';
import { ModifyMethod } from '@/shared/form/form-props';

export type ChunkingStepFormProps = {
    chunkingStrategy: ChunkingStrategy | undefined;
    metadata?: { tags?: string[] };
    allowChunkingOverride?: boolean;
    setFields(values: { [key: string]: any }, method?: ModifyMethod): void;
    touchFields(fields: string[], method?: ModifyMethod): void;
    formErrors: any;
    disabled?: boolean;
};

export function ChunkingStepForm (props: ChunkingStepFormProps): ReactElement {
    const {
        chunkingStrategy,
        metadata,
        allowChunkingOverride = true,
        setFields,
        touchFields,
        formErrors,
        disabled = false
    } = props;

    return (
        <SpaceBetween size='s'>
            {/* Chunking Configuration */}
            <ChunkingConfigForm
                item={chunkingStrategy}
                setFields={setFields}
                touchFields={touchFields}
                formErrors={formErrors}
                disabled={disabled}
            />

            {/* Metadata */}
            <MetadataForm
                tags={metadata?.tags || []}
                onTagsChange={(tags) => setFields({ 'metadata.tags': tags })}
                errorText={formErrors?.['metadata.tags'] || formErrors?.metadata?.tags}
                disabled={disabled}
            />

            {/* Allow Chunking Override */}
            <FormField
                label='Allow Chunking Override'
                errorText={formErrors?.allowChunkingOverride}
                description='Allow users to override the chunking strategy when ingesting documents into this collection'
            >
                <Checkbox
                    checked={allowChunkingOverride}
                    onChange={({ detail }) => {
                        setFields({
                            allowChunkingOverride: detail.checked
                        });
                    }}
                    onBlur={() => touchFields(['allowChunkingOverride'])}
                    disabled={disabled}
                >
                    Enable chunking strategy override during document ingestion
                </Checkbox>
            </FormField>
        </SpaceBetween>
    );
}

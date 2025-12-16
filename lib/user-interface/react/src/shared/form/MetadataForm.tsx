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
import { SpaceBetween, Header } from '@cloudscape-design/components';
import { TagsInput } from './TagsInput';

export type MetadataFormProps = {
    tags?: string[];
    onTagsChange: (tags: string[]) => void;
    errorText?: string;
    disabled?: boolean;
    showHeader?: boolean;
    headerText?: string;
    headerDescription?: string;
    tagsLabel?: string;
    tagsDescription?: string;
    tagsPlaceholder?: string;
};

export function MetadataForm (props: MetadataFormProps): ReactElement {
    const {
        tags = [],
        onTagsChange,
        errorText,
        disabled = false,
        showHeader = false,
        headerText = 'Metadata',
        headerDescription = 'Configure metadata for better organization and filtering',
        tagsLabel = 'Tags (optional)',
        tagsDescription = 'Metadata tags for further organizing and filtering information (max 50 tags)',
        tagsPlaceholder = 'Add tag',
    } = props;

    const content = (
        <TagsInput
            label={tagsLabel}
            errorText={errorText}
            description={tagsDescription}
            values={tags}
            onChange={onTagsChange}
            placeholder={tagsPlaceholder}
            disabled={disabled}
        />
    );

    if (showHeader) {
        return (
            <SpaceBetween size='s'>
                <Header description={headerDescription}>
                    {headerText}
                </Header>
                {content}
            </SpaceBetween>
        );
    }

    return content;
}

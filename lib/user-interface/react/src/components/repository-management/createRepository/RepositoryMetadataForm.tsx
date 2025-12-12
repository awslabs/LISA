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
import { Container, Header, SpaceBetween } from '@cloudscape-design/components';
import { FormProps } from '@/shared/form/form-props';
import { MetadataForm } from '@/shared/form/MetadataForm';

export type RepositoryMetadata = {
    tags?: string[];
    customFields?: Record<string, any>;
};

export type RepositoryMetadataFormProps = FormProps<RepositoryMetadata> & {
    disabled?: boolean;
};

export function RepositoryMetadataForm (props: RepositoryMetadataFormProps): ReactElement {
    const { item, setFields, formErrors, disabled = false } = props;

    return (
        <Container
            header={
                <Header
                    variant='h2'
                    description='Add metadata tags to help organize and categorize your repository. These will be applied to all documents ingested across the repository, in addition to tags added at other levels.'
                >
                    Repository Metadata
                </Header>
            }
        >
            <SpaceBetween size='s'>
                <MetadataForm
                    tags={item?.tags || []}
                    onTagsChange={(tags) => setFields({ 'metadata.tags': tags })}
                    errorText={formErrors?.tags}
                    tagsDescription='Metadata tags for organizing and filtering repositories (max 50 tags)'
                    disabled={disabled}
                />
            </SpaceBetween>
        </Container>
    );
}

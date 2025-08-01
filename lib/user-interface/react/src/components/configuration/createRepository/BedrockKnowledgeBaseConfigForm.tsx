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

import Container from '@cloudscape-design/components/container';
import { Header, SpaceBetween } from '@cloudscape-design/components';
import FormField from '@cloudscape-design/components/form-field';
import Input from '@cloudscape-design/components/input';
import React, { ReactElement } from 'react';
import { FormProps } from '../../../shared/form/form-props';
import { BedrockKnowledgeBaseConfig as BedrockKnowledgeBaseConfigSchema, BedrockKnowledgeBaseInstanceConfig } from '#root/lib/schema';

 type BedrockKnowledgeBaseConfigProps = {
     isEdit: boolean
 };

export function BedrockKnowledgeBaseConfigForm (props: FormProps<BedrockKnowledgeBaseConfigSchema> & BedrockKnowledgeBaseConfigProps): ReactElement {
    const { item, touchFields, setFields, formErrors, isEdit } = props;

    return (
        <Container header={<Header variant='h2'>Bedrock Knowledge Base Config</Header>}>
            <SpaceBetween direction='vertical' size='s'>
                <FormField label='Knowledge Base ARN' key={'bedrockKnowledgeBaseArn'}
                    errorText={formErrors?.bedrockKnowledgeBaseConfig?.bedrockKnowledgeBaseArn}
                    description={BedrockKnowledgeBaseInstanceConfig.shape.bedrockKnowledgeBaseArn.description}>
                    <Input value={item.bedrockKnowledgeBaseArn} inputMode='text'
                        onBlur={() => touchFields(['bedrockKnowledgeBaseConfig.bedrockKnowledgeBaseArn'])}
                        onChange={({ detail }) => setFields({ 'bedrockKnowledgeBaseConfig.bedrockKnowledgeBaseArn': detail.value })}
                        placeholder='Knowledge Base ARN' disabled={isEdit} />
                </FormField>
                <FormField label='Knowledge Base Datasource Name' key={'bedrockKnowledgeDatasourceName'}
                    errorText={formErrors?.bedrockKnowledgeBaseConfig?.bedrockKnowledgeDatasourceName}
                    description={BedrockKnowledgeBaseInstanceConfig.shape.bedrockKnowledgeDatasourceName.description}>
                    <Input value={item.bedrockKnowledgeDatasourceName} inputMode='text'
                        onBlur={() => touchFields(['bedrockKnowledgeBaseConfig.bedrockKnowledgeDatasourceName'])}
                        onChange={({ detail }) => setFields({ 'bedrockKnowledgeBaseConfig.bedrockKnowledgeDatasourceName': detail.value })}
                        placeholder='Knowledge Base Datasource Name' disabled={isEdit} />
                </FormField>
                <FormField label='Knowledge Base Datasource S3 Bucket' key={'bedrockKnowledgeDatasourcS3Bucket'}
                    errorText={formErrors?.bedrockKnowledgeBaseConfig?.bedrockKnowledgeDatasourcS3Bucket}
                    description={BedrockKnowledgeBaseInstanceConfig.shape.bedrockKnowledgeDatasourcS3Bucket.description}>
                    <Input value={item.bedrockKnowledgeDatasourcS3Bucket} inputMode='text'
                        onBlur={() => touchFields(['bedrockKnowledgeBaseConfig.bedrockKnowledgeDatasourcS3Bucket'])}
                        onChange={({ detail }) => setFields({ 'bedrockKnowledgeBaseConfig.bedrockKnowledgeDatasourcS3Bucket': detail.value })}
                        placeholder='Knowledge Base Datasource S3 Bucket' disabled={isEdit} />
                </FormField>
            </SpaceBetween>
        </Container>
    );
}

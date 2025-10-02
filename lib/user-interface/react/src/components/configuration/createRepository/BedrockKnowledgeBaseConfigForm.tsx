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
                <FormField label='Knowledge Base Name' key={'bedrockKnowledgeBaseName'}
                    errorText={formErrors?.bedrockKnowledgeBaseConfig?.bedrockKnowledgeBaseName}
                    description={BedrockKnowledgeBaseInstanceConfig.shape.bedrockKnowledgeBaseName.description}>
                    <Input value={item.bedrockKnowledgeBaseName} inputMode='text'
                        onBlur={() => touchFields(['bedrockKnowledgeBaseConfig.bedrockKnowledgeBaseName'])}
                        onChange={({ detail }) => setFields({ 'bedrockKnowledgeBaseConfig.bedrockKnowledgeBaseName': detail.value })}
                        placeholder='Knowledge Base Name' disabled={isEdit} />
                </FormField>
                <FormField label='Knowledge Base ID' key={'bedrockKnowledgeBaseId'}
                    errorText={formErrors?.bedrockKnowledgeBaseConfig?.bedrockKnowledgeBaseId}
                    description={BedrockKnowledgeBaseInstanceConfig.shape.bedrockKnowledgeBaseId.description}>
                    <Input value={item.bedrockKnowledgeBaseId} inputMode='text'
                        onBlur={() => touchFields(['bedrockKnowledgeBaseConfig.bedrockKnowledgeBaseId'])}
                        onChange={({ detail }) => setFields({ 'bedrockKnowledgeBaseConfig.bedrockKnowledgeBaseId': detail.value })}
                        placeholder='Knowledge Base ID' disabled={isEdit} />
                </FormField>
                <FormField label='Knowledge Base Datasource Name' key={'bedrockKnowledgeDatasourceName'}
                    errorText={formErrors?.bedrockKnowledgeBaseConfig?.bedrockKnowledgeDatasourceName}
                    description={BedrockKnowledgeBaseInstanceConfig.shape.bedrockKnowledgeDatasourceName.description}>
                    <Input value={item.bedrockKnowledgeDatasourceName} inputMode='text'
                        onBlur={() => touchFields(['bedrockKnowledgeBaseConfig.bedrockKnowledgeDatasourceName'])}
                        onChange={({ detail }) => setFields({ 'bedrockKnowledgeBaseConfig.bedrockKnowledgeDatasourceName': detail.value })}
                        placeholder='Knowledge Base Datasource Name' disabled={isEdit} />
                </FormField>
                <FormField label='Knowledge Base Datasource ID' key={'bedrockKnowledgeDatasourceId'}
                    errorText={formErrors?.bedrockKnowledgeBaseConfig?.bedrockKnowledgeDatasourceId}
                    description={BedrockKnowledgeBaseInstanceConfig.shape.bedrockKnowledgeDatasourceId.description}>
                    <Input value={item.bedrockKnowledgeDatasourceId} inputMode='text'
                        onBlur={() => touchFields(['bedrockKnowledgeBaseConfig.bedrockKnowledgeDatasourceId'])}
                        onChange={({ detail }) => setFields({ 'bedrockKnowledgeBaseConfig.bedrockKnowledgeDatasourceId': detail.value })}
                        placeholder='Knowledge Base Datasource ID' disabled={isEdit} />
                </FormField>
                <FormField label='Knowledge Base Datasource S3 Bucket' key={'bedrockKnowledgeDatasourceS3Bucket'}
                    errorText={formErrors?.bedrockKnowledgeBaseConfig?.bedrockKnowledgeDatasourceS3Bucket}
                    description={BedrockKnowledgeBaseInstanceConfig.shape.bedrockKnowledgeDatasourceS3Bucket.description}>
                    <Input value={item.bedrockKnowledgeDatasourceS3Bucket} inputMode='text'
                        onBlur={() => touchFields(['bedrockKnowledgeBaseConfig.bedrockKnowledgeDatasourceS3Bucket'])}
                        onChange={({ detail }) => setFields({ 'bedrockKnowledgeBaseConfig.bedrockKnowledgeDatasourceS3Bucket': detail.value })}
                        placeholder='Knowledge Base Datasource S3 Bucket' disabled={isEdit} />
                </FormField>
            </SpaceBetween>
        </Container>
    );
}

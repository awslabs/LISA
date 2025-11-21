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
import { Header, SpaceBetween, Alert, Button, Modal } from '@cloudscape-design/components';
import FormField from '@cloudscape-design/components/form-field';
import Input from '@cloudscape-design/components/input';
import React, { ReactElement, useState } from 'react';
import { FormProps } from '@/shared/form/form-props';
import { BedrockKnowledgeBaseConfig as BedrockKnowledgeBaseConfigSchema, BedrockKnowledgeBaseInstanceConfig } from '#root/lib/schema';
import { BedrockKBDiscoveryWizard } from './BedrockKBDiscoveryWizard';
import { DataSourceSelection } from '@/types/bedrock-kb';

type BedrockKnowledgeBaseConfigProps = {
    isEdit: boolean;
    onDataSourcesSelected?: (kbId: string, kbName: string, kbDescription: string, selections: DataSourceSelection[]) => void;
};

export function BedrockKnowledgeBaseConfigForm (props: FormProps<BedrockKnowledgeBaseConfigSchema> & BedrockKnowledgeBaseConfigProps): ReactElement {
    const { item, touchFields, setFields, formErrors, isEdit, onDataSourcesSelected } = props;
    const [wizardVisible, setWizardVisible] = useState(false);

    const handleDiscoveryComplete = (kbId: string, kbName: string, kbDescription: string, selections: DataSourceSelection[]) => {
        // Auto-fill KB fields
        setFields({
            'bedrockKnowledgeBaseConfig.bedrockKnowledgeBaseId': kbId,
            'bedrockKnowledgeBaseConfig.bedrockKnowledgeBaseName': kbName,
        });

        // If first data source exists, auto-fill it
        if (selections.length > 0) {
            const firstDs = selections[0];
            setFields({
                'bedrockKnowledgeBaseConfig.bedrockKnowledgeDatasourceId': firstDs.dataSourceId,
                'bedrockKnowledgeBaseConfig.bedrockKnowledgeDatasourceName': firstDs.dataSourceName,
                'bedrockKnowledgeBaseConfig.bedrockKnowledgeDatasourceS3Bucket': firstDs.s3Bucket,
            });
        }

        setWizardVisible(false);

        // Notify parent if callback provided
        if (onDataSourcesSelected) {
            onDataSourcesSelected(kbId, kbName, kbDescription, selections);
        }
    };

    return (
        <>
            <Modal
                visible={wizardVisible}
                onDismiss={() => setWizardVisible(false)}
                size='large'
                header='Discover Bedrock Knowledge Base'
            >
                <BedrockKBDiscoveryWizard
                    visible={wizardVisible}
                    onDismiss={() => setWizardVisible(false)}
                    onComplete={handleDiscoveryComplete}
                />
            </Modal>

            <Container header={<Header variant='h2'>Bedrock Knowledge Base Config</Header>}>
                <SpaceBetween direction='vertical' size='s'>
                    {!isEdit && (
                        <Alert type='info' header='Auto-discover your Knowledge Base'>
                            Use the discovery wizard to automatically find your Knowledge Base and data sources,
                            or manually enter the details below.
                            <Button
                                variant='primary'
                                onClick={() => setWizardVisible(true)}
                                iconName='search'
                            >
                                Discover Data Sources
                            </Button>
                        </Alert>
                    )}
                    <Alert type='info' header='How LISA manages your Knowledge Base documents'>
                        LISA tracks document ownership to preserve your existing data. Documents already in your Knowledge Base
                        are marked as user-managed and will never be deleted by LISA. Only documents uploaded through LISA
                        (via manual upload or automated pipelines) can be removed when you delete a collection. This ensures
                        LISA only manages its own documents while respecting your pre-existing Knowledge Base content.
                    </Alert>
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
        </>
    );
}

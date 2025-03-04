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

import { Box, Container, Grid, Header, SpaceBetween, Toggle } from '@cloudscape-design/components';
import React from 'react';
import { SetFieldsFunction } from '../../shared/validation';

const ragOptions = {
    uploadRagDocs: 'Upload documents to RAG',
    showRagLibrary: 'Show Document Library',
    editNumOfRagDocument: 'Edit Number of RAG documents',
};

const inContextOptions = {
    uploadContextDocs: 'Upload documents to context',
    documentSummarization: 'Document Summarization',
};

const advancedOptions = {
    editKwargs: 'Edit Kwargs',
    editPromptTemplate: 'Update Prompt Template',
    viewMetaData: 'View Chat Meta Data',
    deleteSessionHistory: 'Delete Session History',
    editChatHistoryBuffer: 'Edit Chat History Buffer',
};

const configurableOperations = [{
    header: 'Rag Components',
    items: ragOptions
},
{
    header: 'In-Context Components',
    items: inContextOptions
},
{
    header: 'Advanced Components',
    items: advancedOptions
}];

export type ActivatedComponentConfigurationProps = {
    setFields: SetFieldsFunction;
    enabledComponents: {[key: string]: boolean};
};

export function ActivatedUserComponents (props: ActivatedComponentConfigurationProps) {
    return (
        <Container
            header={
                <Header variant='h2'>
                    Activated Chat UI Components
                </Header>
            }>
            <SpaceBetween direction='vertical' size='m'>
                <Grid gridDefinition={configurableOperations.map(() => ({colspan: 4}))}>
                    {configurableOperations.map((operation) =>
                        <SpaceBetween size={'xs'}>
                            <Header variant='h3'>
                                {operation.header}
                            </Header>
                            {Object.keys(operation.items).map((item) => {
                                return (
                                    <Box textAlign='center' key={operation}>
                                        <SpaceBetween alignItems='left' size='xs'>
                                            <Toggle
                                                onChange={({detail}) => {
                                                    const updatedField = {};
                                                    updatedField[`enabledComponents.${item}`] = detail.checked;
                                                    props.setFields(updatedField);
                                                }}
                                                checked={props.enabledComponents[item] || false}
                                                data-cy={`Toggle-${item}`}
                                            >
                                                {operation.items[item]}
                                            </Toggle>
                                        </SpaceBetween>
                                    </Box>
                                );
                            })}
                        </SpaceBetween>

                    )}
                </Grid>
            </SpaceBetween>
        </Container>
    );
}

export default ActivatedUserComponents;

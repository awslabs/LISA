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

import {
    Alert,
    Container,
    Grid,
    Header,
    SpaceBetween,
    Toggle,
    Box
} from '@cloudscape-design/components';
import React from 'react';
import {SetFieldsFunction} from '../../shared/validation';

const configurableOperations = {
    deleteSessionHistory: 'Delete Session History',
    viewMetaData: 'View Chat Meta Data',
    editKwargs: 'Edit Kwargs',
    editPromptTemplate: 'Update Prompt Template',
    editNumOfRagDocument: 'Edit Number of RAG documents',
    editChatHistoryBuffer: 'Edit Chat History Buffer',
    uploadRagDocs: 'Upload documents to RAG',
    uploadContextDocs: 'Upload documents to context',
};

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
                <Grid gridDefinition={Object.keys(configurableOperations).map(() => ({colspan: 3}))}>
                    {Object.keys(configurableOperations).map((operation) => {
                        return (
                            <Box textAlign='center'>
                                <SpaceBetween alignItems='center' size='xs'>
                                    <Toggle
                                        onChange={({detail}) => {
                                            const updatedField = {};
                                            updatedField[`enabledComponents.${operation}`] = detail.checked;
                                            props.setFields(updatedField);
                                        }}
                                        checked={props.enabledComponents[operation]}
                                        data-cy={`Toggle-${operation}`}
                                    >
                                    </Toggle>
                                </SpaceBetween>
                                <p>{configurableOperations[operation]}</p>
                            </Box>
                        );
                    })}
                </Grid>
            </SpaceBetween>
        </Container>
    );
}

export default ActivatedUserComponents;
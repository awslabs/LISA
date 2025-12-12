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
import React, { useCallback } from 'react';
import { SetFieldsFunction } from '../../shared/validation';

const ragOptions = {
    uploadRagDocs: 'Allow document upload from Chat',
    editNumOfRagDocument: 'Edit number of referenced documents',
};

const libraryOptions = {
    modelLibrary: 'Show Model Library',
    showRagLibrary: 'Show Document Library',
    showPromptTemplateLibrary: 'Show Prompt Template Library'
};

const inContextOptions = {
    uploadContextDocs: 'Allow document upload to context',
    documentSummarization: 'Allow Document Summarization',
};

const advancedOptions = {
    editKwargs: 'Edit model arguments',
    editPromptTemplate: 'Update Prompt Template',
    viewMetaData: 'View chat meta-data',
    deleteSessionHistory: 'Delete Session History',
    editChatHistoryBuffer: 'Edit chat history buffer',
    enableModelComparisonUtility: 'Model Comparison Utility',
    encryptSession: 'Session Encryption',
};

const mcpOptions = {
    mcpConnections: 'Allow MCP Server Connections',
    showMcpWorkbench: 'Show MCP Workbench'
};

const apiTokenOptions = {
    enableUserApiTokens: 'Allow user managed API tokens'
};

type AllOptionKeys<G extends Record<string, Record<string, unknown>>> = {
    [K in keyof G]: keyof G[K];
}[keyof G];

type DependencyMap<G extends Record<string, Record<string, unknown>>> = {
    [Opt in AllOptionKeys<G>]?: {
        prerequisites?: ReadonlyArray<AllOptionKeys<G>>;
        dependents?: ReadonlyArray<AllOptionKeys<G>>;
    };
};

const dependencies: DependencyMap<{
    mcpOptions: typeof mcpOptions;
    inContextOptions: typeof inContextOptions;
    ragOptions: typeof ragOptions;
    libraryOptions: typeof libraryOptions;
    advancedOptions: typeof advancedOptions;
    apiTokenOptions: typeof apiTokenOptions;
}> = {
    showMcpWorkbench: { prerequisites: ['mcpConnections'] },
    mcpConnections: { dependents: ['showMcpWorkbench'] }
};

const configurableOperations = [{
    header: 'RAG',
    items: ragOptions
},
{
    header: 'Library',
    items: libraryOptions
},
{
    header: 'In-Context',
    items: inContextOptions
},
{
    header: 'Advanced',
    items: advancedOptions
},
{
    header: 'MCP',
    items: mcpOptions
},
{
    header: 'API Tokens',
    items: apiTokenOptions
}];

export type ActivatedComponentConfigurationProps = {
    setFields: SetFieldsFunction;
    enabledComponents: { [key: string]: boolean };
};

export function ActivatedUserComponents (props: ActivatedComponentConfigurationProps) {
    const { setFields } = props;
    // Helper function to check if an option should be disabled based on prerequisites
    const isOptionDisabled = useCallback((optionKey: string): boolean => {
        const dependency = dependencies[optionKey];
        return Boolean(dependency?.prerequisites?.some((prereq) => !props.enabledComponents[prereq]));
    }, [props.enabledComponents]);

    // Helper function to recursively collect all dependents
    const getAllDependents = useCallback((optionKey: string, visited = new Set<string>()): string[] => {
        if (visited.has(optionKey)) return [];
        visited.add(optionKey);

        const dependency = dependencies[optionKey];
        if (!dependency?.dependents) return [];

        const allDependents: string[] = [];
        for (const dependent of dependency.dependents) {
            allDependents.push(dependent);
            allDependents.push(...getAllDependents(dependent, visited));
        }

        return allDependents;
    }, []);

    // Handle toggle changes with dependency management
    const handleToggleChange = useCallback((item: string, checked: boolean) => {
        const updatedFields: Record<string, boolean> = {};
        updatedFields[`enabledComponents.${item}`] = checked;

        // If turning off, also turn off all dependents recursively
        if (!checked) {
            const allDependents = getAllDependents(item);
            for (const dependent of allDependents) {
                updatedFields[`enabledComponents.${dependent}`] = false;
            }
        }

        setFields(updatedFields);
    }, [setFields, getAllDependents]);

    return (
        <Container
            header={
                <Header variant='h2'>
                    Chat Features
                </Header>
            }>
            <SpaceBetween direction='vertical' size='m'>
                <Grid gridDefinition={configurableOperations.map(() => ({ colspan: 4 }))}>
                    {configurableOperations.map((operation) =>
                        <SpaceBetween size={'xs'} key={operation.header}>
                            <Header variant='h3'>
                                {operation.header}
                            </Header>
                            {Object.keys(operation.items).map((item) => {
                                const isDisabled = isOptionDisabled(item);
                                const isChecked = props.enabledComponents[item] || false;

                                return (
                                    <Box textAlign='center' key={item}>
                                        <SpaceBetween alignItems='start' size='xs'>
                                            <Toggle
                                                onChange={({ detail }) => {
                                                    handleToggleChange(item, detail.checked);
                                                }}
                                                checked={isChecked}
                                                disabled={isDisabled}
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

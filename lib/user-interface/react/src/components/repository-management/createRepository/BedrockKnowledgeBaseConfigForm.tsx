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
import {
    Alert,
    Box,
    Button,
    FormField,
    Header,
    Select,
    SpaceBetween,
    Spinner,
    StatusIndicator,
    Table,
} from '@cloudscape-design/components';
import React, { ReactElement, useEffect, useState } from 'react';
import { FormProps } from '@/shared/form/form-props';
import { BedrockKnowledgeBaseConfig as BedrockKnowledgeBaseConfigSchema } from '#root/lib/schema';
import {
    useListBedrockDataSourcesQuery,
    useListBedrockKnowledgeBasesQuery,
} from '@/shared/reducers/rag.reducer';

type BedrockKnowledgeBaseConfigProps = {
    isEdit: boolean;
    item: { bedrockKnowledgeBaseConfig?: BedrockKnowledgeBaseConfigSchema };
    setFields: (fields: Record<string, any>) => void;
};

type DataSourceRow = {
    id: string;
    name: string;
    s3Uri: string;
};

export function BedrockKnowledgeBaseConfigForm (
    props: FormProps<{ bedrockKnowledgeBaseConfig?: BedrockKnowledgeBaseConfigSchema }> &
        BedrockKnowledgeBaseConfigProps
): ReactElement {
    const { item, setFields, isEdit } = props;

    // Initialize state from item to persist across wizard pages
    const [selectedKbId, setSelectedKbId] = useState<string | null>(
        item.bedrockKnowledgeBaseConfig?.knowledgeBaseId || null
    );
    const [selectedDataSources, setSelectedDataSources] = useState<DataSourceRow[]>([]);
    const [hasInitialized, setHasInitialized] = useState(false);

    // Only fetch KBs if not in edit mode
    const { data: kbData, isLoading: kbLoading } = useListBedrockKnowledgeBasesQuery(undefined, {
        skip: isEdit,
    });

    const {
        data: dsData,
        isLoading: dsLoading,
        refetch: refetchDataSources,
    } = useListBedrockDataSourcesQuery({ kbId: selectedKbId || '' }, { skip: !selectedKbId });

    // Initialize KB ID from existing config (only once)
    useEffect(() => {
        if (item.bedrockKnowledgeBaseConfig && !hasInitialized) {
            setSelectedKbId(item.bedrockKnowledgeBaseConfig.knowledgeBaseId);
            setHasInitialized(true);
        }
    }, [item.bedrockKnowledgeBaseConfig, hasInitialized]);

    // Auto-select data sources based on pipelines config
    useEffect(() => {
        if (item.bedrockKnowledgeBaseConfig && dsData?.dataSources && !hasInitialized) {
            // Get collection IDs from pipelines config
            const pipelineCollectionIds = new Set(
                (item as any).pipelines?.map((p: any) => p.collectionId).filter(Boolean) || []
            );

            // Select data sources that match pipeline collection IDs
            const selectedRows: DataSourceRow[] = dsData.dataSources
                .filter((ds) => pipelineCollectionIds.has(ds.dataSourceId))
                .map((ds) => ({
                    id: ds.dataSourceId,
                    name: ds.name,
                    s3Uri: `s3://${ds.s3Bucket}/${ds.s3Prefix || ''}`,
                }));

            setSelectedDataSources(selectedRows);
            setHasInitialized(true);
        }
    }, [item, dsData, hasInitialized]);

    // Update form when selections change
    useEffect(() => {
        if (selectedKbId && selectedDataSources.length > 0) {
            const config: BedrockKnowledgeBaseConfigSchema = {
                knowledgeBaseId: selectedKbId,
                dataSources: selectedDataSources.map((ds) => ({
                    id: ds.id,
                    s3Uri: ds.s3Uri,
                })),
            };
            setFields({ bedrockKnowledgeBaseConfig: config });
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [selectedKbId, selectedDataSources]);

    const handleKbChange = (kbId: string | null) => {
        setSelectedKbId(kbId);
        setSelectedDataSources([]); // Clear selections when KB changes
    };

    const handleDataSourceSelection = (selectedItems: DataSourceRow[]) => {
        setSelectedDataSources(selectedItems);
    };

    const availableDataSources: DataSourceRow[] =
        dsData?.dataSources.map((ds) => ({
            id: ds.dataSourceId,
            name: ds.name,
            s3Uri: `s3://${ds.s3Bucket}/${ds.s3Prefix || ''}`,
        })) || [];

    return (
        <Container header={<Header variant='h2'>Bedrock Knowledge Base Config</Header>}>
            <SpaceBetween direction='vertical' size='m'>
                <Alert type='info' header='How LISA manages your Knowledge Base documents'>
                    LISA tracks document ownership to preserve your existing data. Documents already in your
                    Knowledge Base are marked as user-managed and will never be deleted by LISA. Only documents
                    uploaded through LISA (via manual upload or automated pipelines) can be removed when you delete
                    a collection.
                </Alert>

                {isEdit ? (
                    <FormField
                        label='Knowledge Base ID'
                        description='Knowledge Base cannot be changed after creation'
                    >
                        <Box variant='code' fontSize='body-m' padding={{ vertical: 'xs' }}>
                            {selectedKbId || 'Not set'}
                        </Box>
                    </FormField>
                ) : (
                    <FormField label='Knowledge Base' description='Select a Bedrock Knowledge Base'>
                        {kbLoading ? (
                            <Box textAlign='center' padding={{ vertical: 's' }}>
                                <Spinner />
                            </Box>
                        ) : (
                            <Select
                                selectedOption={
                                    selectedKbId
                                        ? {
                                            label:
                                                  kbData?.knowledgeBases.find(
                                                      (kb) => kb.knowledgeBaseId === selectedKbId
                                                  )?.name || selectedKbId,
                                            value: selectedKbId,
                                        }
                                        : null
                                }
                                onChange={({ detail }) => handleKbChange(detail.selectedOption.value || null)}
                                options={
                                    kbData?.knowledgeBases
                                        .filter((kb) => kb.available !== false) // Only show available KBs
                                        .map((kb) => ({
                                            label: kb.name,
                                            value: kb.knowledgeBaseId,
                                            description: kb.knowledgeBaseId,
                                        })) || []
                                }
                                placeholder='Choose a Knowledge Base'
                                empty='No available Knowledge Bases found'
                            />
                        )}
                    </FormField>
                )}

                {!isEdit && kbData && kbData.knowledgeBases.some((kb) => kb.available === false) && (
                    <Alert type='info' header='Some Knowledge Bases are unavailable'>
                        {kbData.knowledgeBases.filter((kb) => kb.available === false).length} Knowledge Base(s) are
                        already associated with other repositories and cannot be selected. Each Knowledge Base can
                        only be used by one repository.
                    </Alert>
                )}

                {selectedKbId && (
                    <FormField
                        label='Data Sources'
                        description={
                            isEdit
                                ? 'Add or remove data sources to update collections'
                                : 'Select one or more data sources to track as collections'
                        }
                    >
                        {dsLoading ? (
                            <Box textAlign='center' padding={{ vertical: 'm' }}>
                                <Spinner size='large' />
                                <Box variant='p' padding={{ top: 's' }}>
                                    Loading data sources...
                                </Box>
                            </Box>
                        ) : (
                            <Table
                                columnDefinitions={[
                                    {
                                        id: 'name',
                                        header: 'Name',
                                        cell: (item) => item.name,
                                    },
                                    {
                                        id: 'id',
                                        header: 'Data Source ID',
                                        cell: (item) => (
                                            <Box variant='code' fontSize='body-s'>
                                                {item.id}
                                            </Box>
                                        ),
                                    },
                                    {
                                        id: 's3',
                                        header: 'S3 URI',
                                        cell: (item) => (
                                            <Box variant='code' fontSize='body-s'>
                                                {item.s3Uri}
                                            </Box>
                                        ),
                                    },
                                ]}
                                items={availableDataSources}
                                selectionType='multi'
                                trackBy='id'
                                selectedItems={selectedDataSources}
                                onSelectionChange={({ detail }) =>
                                    handleDataSourceSelection(detail.selectedItems as DataSourceRow[])
                                }
                                header={
                                    <Header
                                        actions={
                                            <Button iconName='refresh' onClick={() => refetchDataSources()}>
                                                Refresh
                                            </Button>
                                        }
                                        counter={`(${selectedDataSources.length}/${availableDataSources.length})`}
                                    >
                                        Available Data Sources
                                    </Header>
                                }
                                empty={
                                    <Box textAlign='center' color='inherit'>
                                        <SpaceBetween size='m'>
                                            <b>No data sources available</b>
                                            <Box variant='p'>
                                                Please create a data source in the AWS Bedrock console.
                                            </Box>
                                        </SpaceBetween>
                                    </Box>
                                }
                            />
                        )}

                        {selectedDataSources.length === 0 && availableDataSources.length > 0 && (
                            <Box padding={{ top: 's' }}>
                                <StatusIndicator type='warning'>
                                    Please select at least one data source to continue
                                </StatusIndicator>
                            </Box>
                        )}
                    </FormField>
                )}


            </SpaceBetween>
        </Container>
    );
}

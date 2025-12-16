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

import { ReactElement, useState } from 'react';
import {
    Badge,
    Box,
    Button,
    Container,
    Header,
    Modal,
    SpaceBetween,
    StatusIndicator,
    Table,
} from '@cloudscape-design/components';
import { useListBedrockDataSourcesQuery } from '@/shared/reducers/rag.reducer';
import { DataSourceSelection } from '@/types/bedrock-kb';
import { BedrockKBDiscoveryWizard } from '../createRepository/BedrockKBDiscoveryWizard';

type DataSourceManagementPanelProps = {
    repositoryId: string;
    kbId: string;
    currentDataSources: DataSourceSelection[];
    onUpdate: (selections: DataSourceSelection[]) => void;
};

export function DataSourceManagementPanel ({
    repositoryId,
    kbId,
    currentDataSources,
    onUpdate,
}: DataSourceManagementPanelProps): ReactElement {
    const [wizardVisible, setWizardVisible] = useState(false);
    const { data, isLoading, refetch } = useListBedrockDataSourcesQuery({ kbId, repositoryId });

    const handleAddDataSources = (
        _kbId: string,
        _kbName: string,
        _kbDescription: string,
        newSelections: DataSourceSelection[]
    ) => {
        // Merge with existing selections (avoid duplicates)
        const existingIds = new Set(currentDataSources.map((ds) => ds.dataSourceId));
        const uniqueNewSelections = newSelections.filter((ds) => !existingIds.has(ds.dataSourceId));

        if (uniqueNewSelections.length > 0) {
            onUpdate([...currentDataSources, ...uniqueNewSelections]);
        }

        setWizardVisible(false);
    };

    const handleRemoveDataSource = (dataSourceId: string) => {
        onUpdate(currentDataSources.filter((ds) => ds.dataSourceId !== dataSourceId));
    };

    return (
        <>
            <Modal
                visible={wizardVisible}
                onDismiss={() => setWizardVisible(false)}
                size='large'
                header='Add Data Sources'
            >
                <BedrockKBDiscoveryWizard
                    visible={wizardVisible}
                    onDismiss={() => setWizardVisible(false)}
                    onComplete={handleAddDataSources}
                    repositoryId={repositoryId}
                />
            </Modal>

            <Container
                header={
                    <Header
                        variant='h2'
                        actions={
                            <SpaceBetween direction='horizontal' size='xs'>
                                <Button iconName='refresh' onClick={() => refetch()}>
                                    Refresh
                                </Button>
                                <Button
                                    variant='primary'
                                    iconName='add-plus'
                                    onClick={() => setWizardVisible(true)}
                                    disabled={isLoading}
                                >
                                    Add Data Sources
                                </Button>
                            </SpaceBetween>
                        }
                        description={'Manage data sources for this Bedrock Knowledge Base repository'}
                    >
                        Data Sources ({currentDataSources.length})
                    </Header>
                }
            >
                <SpaceBetween size='m'>
                    {data && (
                        <Box>
                            <SpaceBetween size='xs'>
                                <Box variant='awsui-key-label'>Data Sources</Box>
                                <Box>
                                    {data.dataSources.length} total
                                </Box>
                            </SpaceBetween>
                        </Box>
                    )}

                    <Table
                        columnDefinitions={[
                            {
                                id: 'name',
                                header: 'Name',
                                cell: (item) => item.dataSourceName,
                            },
                            {
                                id: 'id',
                                header: 'Data source ID',
                                cell: (item) => (
                                    <Box variant='code' fontSize='body-s'>
                                        {item.dataSourceId}
                                    </Box>
                                ),
                            },
                            {
                                id: 's3',
                                header: 'S3 location',
                                cell: (item) => (
                                    <Box variant='code' fontSize='body-s'>
                                        s3://{item.s3Bucket}/{item.s3Prefix || ''}
                                    </Box>
                                ),
                            },
                            {
                                id: 'status',
                                header: 'Status',
                                cell: () => <Badge color='green'>Managed</Badge>,
                            },
                            {
                                id: 'actions',
                                header: 'Actions',
                                cell: (item) => (
                                    <Button
                                        variant='inline-icon'
                                        iconName='remove'
                                        onClick={() => handleRemoveDataSource(item.dataSourceId)}
                                        ariaLabel={`Remove ${item.dataSourceName}`}
                                    />
                                ),
                            },
                        ]}
                        items={currentDataSources}
                        loadingText='Loading data sources'
                        loading={isLoading}
                        empty={
                            <Box textAlign='center' color='inherit'>
                                <SpaceBetween size='m'>
                                    <b>No data sources</b>
                                    <Button onClick={() => setWizardVisible(true)}>Add Data Sources</Button>
                                </SpaceBetween>
                            </Box>
                        }
                    />

                    {currentDataSources.length === 0 && (
                        <Box textAlign='center' padding={{ vertical: 'm' }}>
                            <StatusIndicator type='warning'>
                                At least one data source is required for Bedrock KB repositories
                            </StatusIndicator>
                        </Box>
                    )}
                </SpaceBetween>
            </Container>
        </>
    );
}

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
import {
    Badge,
    Box,
    Button,
    Checkbox,
    Container,
    Header,
    SpaceBetween,
    Spinner,
    StatusIndicator,
} from '@cloudscape-design/components';
import { useListBedrockDataSourcesQuery } from '@/shared/reducers/rag.reducer';
import { DataSource } from '@/types/bedrock-kb';

type DataSourceMultiSelectProps = {
    kbId: string;
    repositoryId?: string;
    selectedDataSourceIds: string[];
    onSelectionChange: (dataSourceIds: string[]) => void;
};

export function DataSourceMultiSelect ({
    kbId,
    repositoryId,
    selectedDataSourceIds,
    onSelectionChange,
}: DataSourceMultiSelectProps): ReactElement {
    const { data, isLoading, error, refetch } = useListBedrockDataSourcesQuery(
        { kbId, repositoryId },
        { skip: !kbId }
    );

    const handleSelectAll = () => {
        if (!data) return;
        const allIds = data.dataSources.map((ds) => ds.dataSourceId);
        onSelectionChange(allIds);
    };

    const handleDeselectAll = () => {
        onSelectionChange([]);
    };

    const handleToggleDataSource = (ds: DataSource) => {
        const isSelected = selectedDataSourceIds.includes(ds.dataSourceId);

        if (isSelected) {
            // Remove from selection
            onSelectionChange(selectedDataSourceIds.filter((id) => id !== ds.dataSourceId));
        } else {
            // Add to selection
            onSelectionChange([...selectedDataSourceIds, ds.dataSourceId]);
        }
    };

    if (isLoading) {
        return (
            <Container header={<Header variant='h2'>Select Data Sources</Header>}>
                <Box textAlign='center' padding={{ vertical: 'l' }}>
                    <Spinner size='large' />
                    <Box variant='p' padding={{ top: 's' }}>
                        Loading data sources...
                    </Box>
                </Box>
            </Container>
        );
    }

    if (error) {
        return (
            <Container header={<Header variant='h2'>Select Data Sources</Header>}>
                <Box textAlign='center' padding={{ vertical: 'l' }}>
                    <StatusIndicator type='error'>
                        {(error as any)?.message || 'Failed to load data sources'}
                    </StatusIndicator>
                    <Box padding={{ top: 's' }}>
                        <Button onClick={() => refetch()}>Retry</Button>
                    </Box>
                </Box>
            </Container>
        );
    }

    if (!data) {
        return (
            <Container header={<Header variant='h2'>Select Data Sources</Header>}>
                <Box textAlign='center' padding={{ vertical: 'l' }}>
                    <StatusIndicator type='info'>Select a Knowledge Base to view data sources</StatusIndicator>
                </Box>
            </Container>
        );
    }

    const displayedDataSources = data.dataSources;

    if (displayedDataSources.length === 0) {
        return (
            <Container header={<Header variant='h2'>Select Data Sources</Header>}>
                <Box textAlign='center' padding={{ vertical: 'l' }}>
                    <StatusIndicator type='warning'>No data sources found</StatusIndicator>
                    <Box variant='p' padding={{ top: 's' }}>
                        Please create a data source in the AWS Bedrock console.
                    </Box>
                </Box>
            </Container>
        );
    }

    return (
        <Container
            header={
                <Header
                    variant='h2'
                    actions={
                        <SpaceBetween direction='horizontal' size='xs'>
                            <Button onClick={handleDeselectAll} disabled={selectedDataSourceIds.length === 0}>
                                Deselect All
                            </Button>
                            <Button onClick={handleSelectAll} disabled={displayedDataSources.length === 0}>
                                Select All
                            </Button>
                            <Button iconName='refresh' onClick={() => refetch()}>
                                Refresh
                            </Button>
                        </SpaceBetween>
                    }
                    description={`${selectedDataSourceIds.length} of ${displayedDataSources.length} data sources selected`}
                >
                    Select Data Sources
                </Header>
            }
        >
            <SpaceBetween size='m'>
                <SpaceBetween size='s'>
                    {displayedDataSources.map((ds) => {
                        const isSelected = selectedDataSourceIds.includes(ds.dataSourceId);
                        const isAvailable = ds.status === 'AVAILABLE';

                        return (
                            <Box key={ds.dataSourceId} padding={{ vertical: 'xs' }}>
                                <Checkbox
                                    checked={isSelected}
                                    onChange={() => handleToggleDataSource(ds)}
                                    disabled={!isAvailable}
                                >
                                    <SpaceBetween size='xxs'>
                                        <Box>
                                            <SpaceBetween direction='horizontal' size='xs'>
                                                <strong>{ds.name}</strong>
                                                {!isAvailable && <Badge color='grey'>{ds.status}</Badge>}
                                            </SpaceBetween>
                                        </Box>
                                        <Box variant='small' color='text-body-secondary'>
                                            ID: {ds.dataSourceId}
                                        </Box>
                                        <Box variant='small' color='text-body-secondary'>
                                            S3: s3://{ds.s3Bucket}/{ds.s3Prefix || ''}
                                        </Box>
                                    </SpaceBetween>
                                </Checkbox>
                            </Box>
                        );
                    })}
                </SpaceBetween>

                {selectedDataSourceIds.length === 0 && (
                    <Box textAlign='center' padding={{ vertical: 'm' }}>
                        <StatusIndicator type='warning'>
                            Please select at least one data source to continue
                        </StatusIndicator>
                    </Box>
                )}
            </SpaceBetween>
        </Container>
    );
}

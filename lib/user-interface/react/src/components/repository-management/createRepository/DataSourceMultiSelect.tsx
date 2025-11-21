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
    Checkbox,
    Container,
    ExpandableSection,
    Header,
    SpaceBetween,
    Spinner,
    StatusIndicator,
    Toggle,
} from '@cloudscape-design/components';
import { useListBedrockDataSourcesQuery } from '@/shared/reducers/rag.reducer';
import { DataSource, DataSourceSelection } from '@/types/bedrock-kb';

interface DataSourceMultiSelectProps {
    kbId: string;
    repositoryId?: string;
    selectedDataSources: DataSourceSelection[];
    onSelectionChange: (selections: DataSourceSelection[]) => void;
}

export function DataSourceMultiSelect({
    kbId,
    repositoryId,
    selectedDataSources,
    onSelectionChange,
}: DataSourceMultiSelectProps): ReactElement {
    const [showOnlyAvailable, setShowOnlyAvailable] = useState(false);
    const { data, isLoading, error, refetch } = useListBedrockDataSourcesQuery(
        { kbId, repositoryId },
        { skip: !kbId }
    );

    const handleSelectAll = () => {
        if (!data) return;
        const availableDs = data.availableDataSources;
        const newSelections: DataSourceSelection[] = availableDs.map((ds) => ({
            dataSourceId: ds.dataSourceId,
            dataSourceName: ds.name,
            s3Bucket: ds.s3Bucket,
            s3Prefix: ds.s3Prefix || '',
        }));
        onSelectionChange(newSelections);
    };

    const handleDeselectAll = () => {
        onSelectionChange([]);
    };

    const handleToggleDataSource = (ds: DataSource) => {
        const isSelected = selectedDataSources.some((s) => s.dataSourceId === ds.dataSourceId);

        if (isSelected) {
            // Remove from selection
            onSelectionChange(selectedDataSources.filter((s) => s.dataSourceId !== ds.dataSourceId));
        } else {
            // Add to selection
            const newSelection: DataSourceSelection = {
                dataSourceId: ds.dataSourceId,
                dataSourceName: ds.name,
                s3Bucket: ds.s3Bucket,
                s3Prefix: ds.s3Prefix || '',
            };
            onSelectionChange([...selectedDataSources, newSelection]);
        }
    };

    if (isLoading) {
        return (
            <Container header={<Header variant="h2">Select Data Sources</Header>}>
                <Box textAlign="center" padding={{ vertical: 'l' }}>
                    <Spinner size="large" />
                    <Box variant="p" padding={{ top: 's' }}>
                        Loading data sources...
                    </Box>
                </Box>
            </Container>
        );
    }

    if (error) {
        return (
            <Container header={<Header variant="h2">Select Data Sources</Header>}>
                <Box textAlign="center" padding={{ vertical: 'l' }}>
                    <StatusIndicator type="error">
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
            <Container header={<Header variant="h2">Select Data Sources</Header>}>
                <Box textAlign="center" padding={{ vertical: 'l' }}>
                    <StatusIndicator type="info">Select a Knowledge Base to view data sources</StatusIndicator>
                </Box>
            </Container>
        );
    }

    const { availableDataSources, managedDataSources } = data;
    const displayedDataSources = showOnlyAvailable ? availableDataSources : [...availableDataSources, ...managedDataSources];

    if (displayedDataSources.length === 0) {
        return (
            <Container header={<Header variant="h2">Select Data Sources</Header>}>
                <Box textAlign="center" padding={{ vertical: 'l' }}>
                    <StatusIndicator type="warning">
                        {showOnlyAvailable ? 'No available data sources' : 'No data sources found'}
                    </StatusIndicator>
                    <Box variant="p" padding={{ top: 's' }}>
                        {showOnlyAvailable
                            ? 'All data sources are already managed by collections.'
                            : 'Please create a data source in the AWS Bedrock console.'}
                    </Box>
                </Box>
            </Container>
        );
    }

    return (
        <Container
            header={
                <Header
                    variant="h2"
                    actions={
                        <SpaceBetween direction="horizontal" size="xs">
                            <Button onClick={handleDeselectAll} disabled={selectedDataSources.length === 0}>
                                Deselect All
                            </Button>
                            <Button onClick={handleSelectAll} disabled={availableDataSources.length === 0}>
                                Select All Available
                            </Button>
                            <Button iconName="refresh" onClick={() => refetch()}>
                                Refresh
                            </Button>
                        </SpaceBetween>
                    }
                    description={`${selectedDataSources.length} of ${availableDataSources.length} available data sources selected`}
                >
                    Select Data Sources
                </Header>
            }
        >
            <SpaceBetween size="m">
                <Toggle
                    checked={showOnlyAvailable}
                    onChange={({ detail }) => setShowOnlyAvailable(detail.checked)}
                >
                    Show only available data sources
                </Toggle>

                <SpaceBetween size="s">
                    {displayedDataSources.map((ds) => {
                        const isManaged = managedDataSources.some((m) => m.dataSourceId === ds.dataSourceId);
                        const isSelected = selectedDataSources.some((s) => s.dataSourceId === ds.dataSourceId);
                        const isAvailable = ds.status === 'AVAILABLE';

                        return (
                            <Box key={ds.dataSourceId} padding={{ vertical: 'xs' }}>
                                <Checkbox
                                    checked={isSelected}
                                    onChange={() => handleToggleDataSource(ds)}
                                    disabled={isManaged || !isAvailable}
                                >
                                    <SpaceBetween size="xxs">
                                        <Box>
                                            <SpaceBetween direction="horizontal" size="xs">
                                                <strong>{ds.name}</strong>
                                                {isManaged && <Badge color="blue">Managed</Badge>}
                                                {!isAvailable && <Badge color="grey">{ds.status}</Badge>}
                                            </SpaceBetween>
                                        </Box>
                                        <Box variant="small" color="text-body-secondary">
                                            ID: {ds.dataSourceId}
                                        </Box>
                                        <Box variant="small" color="text-body-secondary">
                                            S3: s3://{ds.s3Bucket}/{ds.s3Prefix || ''}
                                        </Box>
                                        {isManaged && ds.collectionId && (
                                            <Box variant="small" color="text-status-info">
                                                Collection: {ds.collectionId}
                                            </Box>
                                        )}
                                    </SpaceBetween>
                                </Checkbox>
                            </Box>
                        );
                    })}
                </SpaceBetween>

                {selectedDataSources.length === 0 && (
                    <Box textAlign="center" padding={{ vertical: 'm' }}>
                        <StatusIndicator type="warning">
                            Please select at least one data source to continue
                        </StatusIndicator>
                    </Box>
                )}
            </SpaceBetween>
        </Container>
    );
}

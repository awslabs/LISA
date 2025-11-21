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
    Box,
    Button,
    Container,
    FormField,
    Header,
    Input,
    RadioGroup,
    SpaceBetween,
    Spinner,
    StatusIndicator,
} from '@cloudscape-design/components';
import { useListBedrockKnowledgeBasesQuery } from '@/shared/reducers/rag.reducer';
import { KnowledgeBase } from '@/types/bedrock-kb';

type KnowledgeBaseSelectorProps = {
    selectedKbId: string | null;
    onSelect: (kb: KnowledgeBase | null) => void;
};

export function KnowledgeBaseSelector ({ selectedKbId, onSelect }: KnowledgeBaseSelectorProps): ReactElement {
    const [searchText, setSearchText] = useState('');
    const { data, isLoading, error, refetch } = useListBedrockKnowledgeBasesQuery();

    // Filter KBs based on search text
    const filteredKBs = data?.knowledgeBases.filter((kb) => {
        const searchLower = searchText.toLowerCase();
        return (
            kb.name.toLowerCase().includes(searchLower) ||
            kb.knowledgeBaseId.toLowerCase().includes(searchLower) ||
            (kb.description && kb.description.toLowerCase().includes(searchLower))
        );
    });

    const handleRefresh = () => {
        refetch();
    };

    if (isLoading) {
        return (
            <Container header={<Header variant='h2'>Select Knowledge Base</Header>}>
                <Box textAlign='center' padding={{ vertical: 'l' }}>
                    <Spinner size='large' />
                    <Box variant='p' padding={{ top: 's' }}>
                        Loading Knowledge Bases...
                    </Box>
                </Box>
            </Container>
        );
    }

    if (error) {
        return (
            <Container header={<Header variant='h2'>Select Knowledge Base</Header>}>
                <Box textAlign='center' padding={{ vertical: 'l' }}>
                    <StatusIndicator type='error'>
                        {(error as any)?.message || 'Failed to load Knowledge Bases'}
                    </StatusIndicator>
                    <Box padding={{ top: 's' }}>
                        <Button onClick={handleRefresh}>Retry</Button>
                    </Box>
                </Box>
            </Container>
        );
    }

    if (!data?.knowledgeBases || data.knowledgeBases.length === 0) {
        return (
            <Container header={<Header variant='h2'>Select Knowledge Base</Header>}>
                <Box textAlign='center' padding={{ vertical: 'l' }}>
                    <StatusIndicator type='warning'>No ACTIVE Knowledge Bases found</StatusIndicator>
                    <Box variant='p' padding={{ top: 's' }}>
                        Please create a Knowledge Base in the AWS Bedrock console first.
                    </Box>
                    <Box padding={{ top: 's' }}>
                        <Button onClick={handleRefresh}>Refresh</Button>
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
                        <Button iconName='refresh' onClick={handleRefresh}>
                            Refresh
                        </Button>
                    }
                >
                    Select Knowledge Base
                </Header>
            }
        >
            <SpaceBetween size='m'>
                <FormField label='Search' description='Filter by name, ID, or description'>
                    <Input
                        value={searchText}
                        onChange={({ detail }) => setSearchText(detail.value)}
                        placeholder='Search Knowledge Bases...'
                        type='search'
                        clearAriaLabel='Clear search'
                    />
                </FormField>

                {filteredKBs && filteredKBs.length > 0 ? (
                    <FormField
                        label={`Knowledge Bases (${filteredKBs.length} of ${data.knowledgeBases.length})`}
                        description='Select a Knowledge Base to view its data sources'
                    >
                        <RadioGroup
                            value={selectedKbId || ''}
                            onChange={({ detail }) => {
                                const kb = data.knowledgeBases.find((k) => k.knowledgeBaseId === detail.value);
                                onSelect(kb || null);
                            }}
                            items={filteredKBs.map((kb) => ({
                                value: kb.knowledgeBaseId,
                                label: kb.name,
                                description: (
                                    <SpaceBetween size='xxs'>
                                        <Box variant='small'>ID: {kb.knowledgeBaseId}</Box>
                                        {kb.description && <Box variant='small'>{kb.description}</Box>}
                                        <Box variant='small'>
                                            <StatusIndicator type='success'>ACTIVE</StatusIndicator>
                                        </Box>
                                    </SpaceBetween>
                                ),
                            }))}
                        />
                    </FormField>
                ) : (
                    <Box textAlign='center' padding={{ vertical: 'm' }}>
                        <StatusIndicator type='info'>No Knowledge Bases match your search</StatusIndicator>
                    </Box>
                )}
            </SpaceBetween>
        </Container>
    );
}

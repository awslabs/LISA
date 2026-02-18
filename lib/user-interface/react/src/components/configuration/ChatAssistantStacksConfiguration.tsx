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

import React, { useMemo, useState } from 'react';
import {
    Box,
    Button,
    ButtonDropdown,
    Cards,
    Container,
    Header,
    SpaceBetween,
    TextFilter,
} from '@cloudscape-design/components';
import { RefreshButton } from '@/components/common/RefreshButton';

export type ChatAssistantStackPlaceholder = {
    stackId: string;
    name: string;
    description: string;
};

const CARD_DEFINITION = {
    header: (item: ChatAssistantStackPlaceholder) => item.name,
    sections: [
        {
            id: 'description',
            header: 'Description',
            content: (item: ChatAssistantStackPlaceholder) => item.description || '—',
        },
    ],
};

export function ChatAssistantStacksConfiguration (): React.ReactElement {
    const [searchText, setSearchText] = useState('');
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [selectedItems, setSelectedItems] = useState<ChatAssistantStackPlaceholder[]>([]);

    // Placeholder: no API yet – empty list. When API exists, replace with query and filter by name/description.
    const stacks: ChatAssistantStackPlaceholder[] = [];
    const filteredStacks = useMemo(() => {
        if (!searchText.trim()) return stacks;
        const lower = searchText.toLowerCase();
        return stacks.filter(
            (s) =>
                s.name.toLowerCase().includes(lower) ||
                (s.description && s.description.toLowerCase().includes(lower))
        );
    }, [searchText]);

    const handleRefresh = () => {
        setIsRefreshing(true);
        // TODO: refetch stacks when API exists
        setTimeout(() => setIsRefreshing(false), 500);
    };

    const handleCreateStack = () => {
        // TODO: open Create Stack modal (AS-4)
    };

    const actionsDropdownItems = [
        { id: 'update', text: 'Update', disabled: selectedItems.length !== 1 },
        { id: 'delete', text: 'Delete', disabled: selectedItems.length !== 1 },
        { id: 'activate', text: 'Activate', disabled: selectedItems.length !== 1 },
        { id: 'deactivate', text: 'Deactivate', disabled: selectedItems.length !== 1 },
    ];

    return (
        <Container
            header={
                <Header variant='h2'>
                    Chat Assistant Stacks
                </Header>
            }
        >
            <Cards
                variant='full-page'
                trackBy='stackId'
                cardDefinition={CARD_DEFINITION}
                cardsPerRow={[{ cards: 3 }]}
                items={filteredStacks}
                selectedItems={selectedItems}
                onSelectionChange={({ detail }) => setSelectedItems(detail.selectedItems)}
                selectionType='single'
                loading={isRefreshing}
                loadingText='Loading stacks'
                header={
                    <Header
                        counter={filteredStacks.length > 0 ? `(${filteredStacks.length})` : undefined}
                        actions={
                            <SpaceBetween direction='horizontal' size='xs'>
                                <RefreshButton
                                    isLoading={isRefreshing}
                                    onClick={handleRefresh}
                                    ariaLabel='Refresh stacks'
                                />
                                <ButtonDropdown
                                    items={actionsDropdownItems}
                                    variant='primary'
                                    disabled={selectedItems.length === 0}
                                    onItemClick={() => {
                                        // TODO: handle Actions (AS-4–AS-7)
                                    }}
                                >
                                    Actions
                                </ButtonDropdown>
                                <Button variant='primary' onClick={handleCreateStack}>
                                    Create Stack
                                </Button>
                            </SpaceBetween>
                        }
                    >
                        Stacks
                    </Header>
                }
                filter={
                    <TextFilter
                        filteringText={searchText}
                        filteringPlaceholder='Search by name or description'
                        filteringAriaLabel='Search stacks'
                        onChange={({ detail }) => setSearchText(detail.filteringText)}
                    />
                }
                empty={
                    <Box margin={{ vertical: 'xs' }} textAlign='center' color='inherit'>
                        <SpaceBetween size='m'>
                            <b>No stacks</b>
                            <span>Create a stack to bundle models, repos, MCP servers, and prompts for users.</span>
                        </SpaceBetween>
                    </Box>
                }
            />
        </Container>
    );
}

export default ChatAssistantStacksConfiguration;

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
    Badge,
    Box,
    Button,
    ButtonDropdown,
    Cards,
    Header,
    SpaceBetween,
    TextFilter,
} from '@cloudscape-design/components';
import { RefreshButton } from '@/components/common/RefreshButton';
import { useAppDispatch } from '@/config/store';
import { setConfirmationModal } from '@/shared/reducers/modal.reducer';
import { useNotificationService } from '@/shared/util/hooks';
import {
    useListStacksQuery,
    useDeleteStackMutation,
    useUpdateStackStatusMutation,
} from '@/shared/reducers/chat-assistant-stacks.reducer';
import { IChatAssistantStack } from '@/shared/model/chat-assistant-stack.model';
import CreateStackModal from '@/components/chat-assistant-stacks/CreateStackModal';

function listIds (ids: string[] | undefined): string {
    if (!ids?.length) return '—';
    return ids.join(', ');
}

function formatCount (n: number, singular: string, plural: string): string {
    return n === 1 ? `1 ${singular}` : `${n} ${plural}`;
}

export function ChatAssistantStacksManagement (): React.ReactElement {
    const dispatch = useAppDispatch();
    const notificationService = useNotificationService(dispatch);
    const [searchText, setSearchText] = useState('');
    const [createModalVisible, setCreateModalVisible] = useState(false);
    const [isEdit, setIsEdit] = useState(false);
    const [selectedItems, setSelectedItems] = useState<IChatAssistantStack[]>([]);

    const { data: stacks = [], isFetching, refetch } = useListStacksQuery(undefined, { refetchOnMountOrArgChange: true });
    const [deleteStack, { isLoading: isDeleting }] = useDeleteStackMutation();
    const [updateStackStatus, { isLoading: isUpdatingStatus }] = useUpdateStackStatusMutation();

    const cardDefinition = useMemo(
        () => ({
            header: (item: IChatAssistantStack) => (
                <SpaceBetween direction='horizontal' size='xs'>
                    <span>{item.name}</span>
                    {!item.isActive && <Badge color='grey'>Inactive</Badge>}
                </SpaceBetween>
            ),
            sections: [
                {
                    id: 'description',
                    header: 'Description',
                    content: (item: IChatAssistantStack) => item.description || '—',
                },
                {
                    id: 'models',
                    header: 'Models',
                    content: (item: IChatAssistantStack) => listIds(item.modelIds),
                },
                {
                    id: 'rag',
                    header: 'RAG',
                    content: (item: IChatAssistantStack) => {
                        const repos = item.repositoryIds?.length ?? 0;
                        const colls = item.collectionIds?.length ?? 0;
                        if (repos === 0 && colls === 0) return '—';
                        const parts = [];
                        if (repos) parts.push(formatCount(repos, 'repository', 'repositories'));
                        if (colls) parts.push(formatCount(colls, 'collection', 'collections'));
                        return parts.join(', ');
                    },
                },
                {
                    id: 'mcp',
                    header: 'MCP',
                    content: (item: IChatAssistantStack) => {
                        const servers = item.mcpServerIds?.length ?? 0;
                        const tools = item.mcpToolIds?.length ?? 0;
                        if (servers === 0 && tools === 0) return '—';
                        const parts = [];
                        if (servers) parts.push(formatCount(servers, 'server', 'servers'));
                        if (tools) parts.push(formatCount(tools, 'tool', 'tools'));
                        return parts.join(', ');
                    },
                },
                {
                    id: 'prompts',
                    header: 'Prompts',
                    content: (item: IChatAssistantStack) => {
                        const hasPersona = !!item.personaPromptId;
                        const dirCount = item.directivePromptIds?.length ?? 0;
                        if (!hasPersona && dirCount === 0) return '—';
                        const parts = [];
                        if (hasPersona) parts.push('Persona');
                        if (dirCount) parts.push(formatCount(dirCount, 'directive', 'directives'));
                        return parts.join(', ');
                    },
                },
                {
                    id: 'access',
                    header: 'Access',
                    content: (item: IChatAssistantStack) => {
                        const groups = item.allowedGroups ?? [];
                        return groups.length === 0 ? 'Global' : groups.join(', ');
                    },
                },
                {
                    id: 'updated',
                    header: 'Last updated',
                    content: (item: IChatAssistantStack) => {
                        const u = item.updated ?? item.created;
                        if (!u) return '—';
                        try {
                            const d = new Date(u);
                            return d.toLocaleDateString(undefined, { dateStyle: 'medium' });
                        } catch {
                            return u;
                        }
                    },
                },
            ],
        }),
        []
    );

    const filteredStacks = useMemo(() => {
        if (!searchText.trim()) return stacks;
        const lower = searchText.toLowerCase();
        return stacks.filter(
            (s) =>
                s.name.toLowerCase().includes(lower) ||
                (s.description && s.description.toLowerCase().includes(lower))
        );
    }, [stacks, searchText]);

    const handleRefresh = () => {
        refetch();
    };

    const handleCreateStack = () => {
        setIsEdit(false);
        setCreateModalVisible(true);
    };

    const handleActionsClick = (detail: { id: string }) => {
        const stack = selectedItems[0];
        if (!stack) return;
        switch (detail.id) {
            case 'update':
                setIsEdit(true);
                setCreateModalVisible(true);
                break;
            case 'delete':
                dispatch(
                    setConfirmationModal({
                        action: 'Delete',
                        resourceName: 'Chat Assistant Stack',
                        description: `This will delete the stack "${stack.name}".`,
                        onConfirm: () => {
                            deleteStack(stack.stackId)
                                .unwrap()
                                .then(() => {
                                    notificationService.generateNotification(`Deleted stack: ${stack.name}`, 'success');
                                    setSelectedItems([]);
                                })
                                .catch((err) => {
                                    notificationService.generateNotification(err?.message ?? 'Failed to delete stack', 'error');
                                });
                        },
                    })
                );
                break;
            case 'activate':
                updateStackStatus({ stackId: stack.stackId, isActive: true })
                    .unwrap()
                    .then(() => {
                        notificationService.generateNotification(`Activated stack: ${stack.name}`, 'success');
                        setSelectedItems([]);
                    })
                    .catch((err) => {
                        notificationService.generateNotification(err?.message ?? 'Failed to activate stack', 'error');
                    });
                break;
            case 'deactivate':
                updateStackStatus({ stackId: stack.stackId, isActive: false })
                    .unwrap()
                    .then(() => {
                        notificationService.generateNotification(`Deactivated stack: ${stack.name}`, 'success');
                        setSelectedItems([]);
                    })
                    .catch((err) => {
                        notificationService.generateNotification(err?.message ?? 'Failed to deactivate stack', 'error');
                    });
                break;
            default:
                break;
        }
    };

    const actionsDropdownItems = [
        { id: 'update', text: 'Update', disabled: selectedItems.length !== 1 },
        { id: 'delete', text: 'Delete', disabled: selectedItems.length !== 1 },
        { id: 'activate', text: 'Activate', disabled: selectedItems.length !== 1 || selectedItems[0]?.isActive },
        { id: 'deactivate', text: 'Deactivate', disabled: selectedItems.length !== 1 || !selectedItems[0]?.isActive },
    ];

    return (
        <>
            <CreateStackModal
                visible={createModalVisible}
                setVisible={setCreateModalVisible}
                isEdit={isEdit}
                setIsEdit={setIsEdit}
                selectedStack={isEdit ? selectedItems[0] ?? null : null}
                setSelectedItems={setSelectedItems}
            />
            <Cards
                variant='full-page'
                trackBy='stackId'
                cardDefinition={cardDefinition}
                cardsPerRow={[{ cards: 3 }]}
                items={filteredStacks}
                selectedItems={selectedItems}
                onSelectionChange={({ detail }) => setSelectedItems(detail.selectedItems)}
                selectionType='single'
                loading={isFetching}
                loadingText='Loading stacks'
                header={
                    <Header
                        counter={filteredStacks.length > 0 ? `(${filteredStacks.length})` : undefined}
                        actions={
                            <SpaceBetween direction='horizontal' size='xs'>
                                <RefreshButton
                                    isLoading={isFetching}
                                    onClick={handleRefresh}
                                    ariaLabel='Refresh stacks'
                                />
                                <ButtonDropdown
                                    items={actionsDropdownItems}
                                    variant='primary'
                                    disabled={selectedItems.length === 0}
                                    loading={isDeleting || isUpdatingStatus}
                                    onItemClick={({ detail }) => handleActionsClick(detail)}
                                >
                                    Actions
                                </ButtonDropdown>
                                <Button variant='primary' onClick={handleCreateStack}>
                                    Create Stack
                                </Button>
                            </SpaceBetween>
                        }
                    >
                        Chat Assistant Stacks
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
        </>
    );
}

export default ChatAssistantStacksManagement;

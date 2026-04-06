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
    Box,
    Button,
    ButtonDropdown,
    Container,
    FormField,
    Grid,
    Header,
    Input,
    Modal,
    Pagination,
    Select,
    SpaceBetween,
    StatusIndicator,
    Table,
    TextContent,
} from '@cloudscape-design/components';
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useCollection } from '@cloudscape-design/collection-hooks';
import {
    useDeleteBedrockAgentApprovalMutation,
    useLazyListBedrockAgentsDiscoveryQuery,
    useListBedrockAgentApprovalsQuery,
    usePutBedrockAgentApprovalMutation,
} from '@/shared/reducers/mcp-server.reducer';
import type { BedrockAgentApprovalRow, BedrockAgentDiscoveryRow } from '@/types/bedrock-agent';
import { UserGroupsInput } from '@/shared/form/UserGroupsInput';
import { useAppDispatch } from '@/config/store';
import { useNotificationService } from '@/shared/util/hooks';
import { setConfirmationModal } from '@/shared/reducers/modal.reducer';
import { setBreadcrumbs } from '@/shared/reducers/breadcrumbs.reducer';
import { getDisplayName } from '@/shared/util/branding';
import RefreshButton from '../common/RefreshButton';

type CatalogModalState =
    | { mode: 'add'; row: BedrockAgentDiscoveryRow }
    | { mode: 'edit'; row: BedrockAgentApprovalRow };

function catalogGroupsToDisplay (groups?: string[]): string[] {
    if (!groups?.length) {
        return [];
    }
    return groups.map((g) => {
        const s = String(g);
        return s.startsWith('group:') ? s.slice(6) : s;
    });
}

export function BedrockAgentManagementComponent (): React.ReactElement {
    const dispatch = useAppDispatch();
    const notificationService = useNotificationService(dispatch);
    const { data: approvalsData, isFetching: approvalsLoading, refetch: refetchApprovals } =
        useListBedrockAgentApprovalsQuery();
    const [runDiscovery, { data: discoveryData, isFetching: discoveryLoading }] =
        useLazyListBedrockAgentsDiscoveryQuery();
    const [putApproval, { isLoading: putLoading }] = usePutBedrockAgentApprovalMutation();
    const [deleteApproval] = useDeleteBedrockAgentApprovalMutation();

    const [modal, setModal] = useState<CatalogModalState | null>(null);
    const [agentName, setAgentName] = useState('');
    const [agentAliasId, setAgentAliasId] = useState('');
    const [groupTokens, setGroupTokens] = useState<string[]>([]);

    useEffect(() => {
        dispatch(
            setBreadcrumbs([{ text: 'Bedrock agent catalog', href: '/bedrock-agent-management' }])
        );
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const approvals = useMemo(() => approvalsData?.approvals ?? [], [approvalsData?.approvals]);
    const approvalIds = useMemo(() => new Set(approvals.map((a) => a.agentId)), [approvals]);

    const openAdd = useCallback((row: BedrockAgentDiscoveryRow) => {
        setModal({ mode: 'add', row });
        setAgentName(row.agentName);
        const defaultAlias =
            row.suggestedAliasId
            ?? row.aliases.find((a) => a.agentAliasStatus === 'PREPARED')?.agentAliasId
            ?? row.aliases[0]?.agentAliasId
            ?? '';
        setAgentAliasId(defaultAlias);
        setGroupTokens([]);
    }, []);

    const openEdit = useCallback((row: BedrockAgentApprovalRow) => {
        setModal({ mode: 'edit', row });
        setAgentName(row.agentName);
        setAgentAliasId(row.agentAliasId);
        setGroupTokens(catalogGroupsToDisplay(row.groups));
    }, []);

    const saveModal = async () => {
        if (!modal || !agentName.trim() || !agentAliasId.trim()) {
            notificationService.generateNotification('Name and alias ID are required.', 'error');
            return;
        }
        const agentId = modal.mode === 'add' ? modal.row.agentId : modal.row.agentId;
        try {
            await putApproval({
                agentId,
                body: {
                    agentName: agentName.trim(),
                    agentAliasId: agentAliasId.trim(),
                    groups: groupTokens.map((t) => t.trim()).filter(Boolean),
                },
            }).unwrap();
            notificationService.generateNotification('Catalog entry saved.', 'success');
            setModal(null);
            discoveryTableActions.setSelectedItems([]);
            catalogTableActions.setSelectedItems([]);
        } catch (e: unknown) {
            const msg = e && typeof e === 'object' && 'message' in e ? String((e as { message: string }).message) : 'Save failed';
            notificationService.generateNotification(msg, 'error');
        }
    };

    const confirmRemove = (row: BedrockAgentApprovalRow, onRemoved?: () => void) => {
        dispatch(
            setConfirmationModal({
                action: 'Remove',
                resourceName: row.agentName,
                description: 'Users will no longer see this agent in the catalog after removal.',
                onConfirm: async () => {
                    try {
                        await deleteApproval(row.agentId).unwrap();
                        notificationService.generateNotification('Removed from catalog.', 'success');
                        onRemoved?.();
                    } catch (e: unknown) {
                        const msg =
                            e && typeof e === 'object' && 'message' in e
                                ? String((e as { message: string }).message)
                                : 'Remove failed';
                        notificationService.generateNotification(msg, 'error');
                    }
                },
            })
        );
    };

    const notInCatalog = useMemo(() => {
        const discovered = discoveryData?.agents ?? [];
        return discovered.filter((a) => !approvalIds.has(a.agentId));
    }, [discoveryData?.agents, approvalIds]);

    const {
        paginationProps: catalogPaginationProps,
        items: catalogItems,
        collectionProps: catalogCollectionProps,
        actions: catalogTableActions,
    } = useCollection(approvals, {
        selection: {
            defaultSelectedItems: [],
            trackBy: 'agentId',
            keepSelection: false,
        },
        sorting: { defaultState: { sortingColumn: { sortingField: 'agentName' } } },
        pagination: { defaultPage: 1, pageSize: 10 },
    });

    const {
        paginationProps: discoveryPaginationProps,
        items: discoveryItems,
        collectionProps: discoveryCollectionProps,
        actions: discoveryTableActions,
    } = useCollection(notInCatalog, {
        selection: {
            defaultSelectedItems: [],
            trackBy: 'agentId',
            keepSelection: false,
        },
        sorting: { defaultState: { sortingColumn: { sortingField: 'agentName' } } },
        pagination: { defaultPage: 1, pageSize: 10 },
    });

    const selectedDiscovered = discoveryCollectionProps.selectedItems?.[0] as BedrockAgentDiscoveryRow | undefined;
    const selectedCatalog = catalogCollectionProps.selectedItems?.[0] as BedrockAgentApprovalRow | undefined;

    const handleScannedAgentsAction = (detail: { id: string }) => {
        if (detail.id === 'add' && selectedDiscovered?.invokeReady) {
            openAdd(selectedDiscovered);
        }
    };

    const handleLisaCatalogAction = (detail: { id: string }) => {
        if (detail.id === 'edit' && selectedCatalog) {
            openEdit(selectedCatalog);
            return;
        }
        if (detail.id === 'remove' && selectedCatalog) {
            confirmRemove(selectedCatalog, () => catalogTableActions.setSelectedItems([]));
        }
    };

    const aliasSelectOptions =
        modal?.mode === 'add'
            ? modal.row.aliases.map((a) => ({
                label: `${a.agentAliasName ?? a.agentAliasId} (${a.agentAliasId})`,
                value: a.agentAliasId,
            }))
            : [];

    return (
        <SpaceBetween size='l' direction='vertical'>
            <TextContent>
                <p>
                    Scan the AWS account in your Region on the left, then add agents into the {getDisplayName()} catalog on the right.
                    Users only see catalog entries that match their groups (or all users if you leave groups empty).
                </p>
            </TextContent>

            <Grid
                gridDefinition={[
                    { colspan: { default: 12, m: 6 } },
                    { colspan: { default: 12, m: 6 } },
                ]}
            >
                <Container
                    header={(
                        <Header
                            variant='h2'
                            actions={(
                                <SpaceBetween direction='horizontal' size='xs' alignItems='center'>
                                    <ButtonDropdown
                                        items={[
                                            {
                                                id: 'add',
                                                text: 'Add to catalog',
                                                disabled: !selectedDiscovered || !selectedDiscovered.invokeReady,
                                                disabledReason: !selectedDiscovered
                                                    ? 'Select a scanned agent in the table below.'
                                                    : !selectedDiscovered.invokeReady
                                                        ? 'Choose an agent with a prepared alias (invocation ready).'
                                                        : undefined,
                                            },
                                        ]}
                                        variant='primary'
                                        onItemClick={({ detail }) => handleScannedAgentsAction(detail)}
                                    >
                                        Actions
                                    </ButtonDropdown>
                                    <Button
                                        onClick={() => runDiscovery()}
                                        loading={discoveryLoading}
                                        ariaLabel='Scan account for Bedrock agents'
                                    >
                                        Scan account
                                    </Button>
                                </SpaceBetween>
                            )}
                            description='Agents found in this account that are not in the catalog yet.'
                        >
                            Available agents
                        </Header>
                    )}
                >
                    <Table
                        {...discoveryCollectionProps}
                        ariaLabels={{ itemSelectionLabel: (_e, row) => row.agentName }}
                        header={null}
                        loading={discoveryLoading}
                        loadingText='Scanning…'
                        empty={(
                            <TextContent>
                                <small>
                                    Run a scan to list agents in this Region, or every discovered agent is already in the catalog.
                                </small>
                            </TextContent>
                        )}
                        variant='embedded'
                        selectionType='single'
                        selectedItems={discoveryCollectionProps.selectedItems}
                        onSelectionChange={(e) => {
                            discoveryCollectionProps.onSelectionChange?.(e);
                            if ((e.detail.selectedItems ?? []).length > 0) {
                                catalogTableActions.setSelectedItems([]);
                            }
                        }}
                        pagination={<Pagination {...discoveryPaginationProps} />}
                        items={discoveryItems}
                        columnDefinitions={[
                            { id: 'name', header: 'Name', cell: (item) => item.agentName, sortingField: 'agentName' },
                            { id: 'id', header: 'Agent ID', cell: (item) => item.agentId },
                            {
                                id: 'ready',
                                header: 'Invocation ready',
                                cell: (item) =>
                                    item.invokeReady ? (
                                        <StatusIndicator type='success'>Yes</StatusIndicator>
                                    ) : (
                                        <StatusIndicator type='warning'>Check aliases</StatusIndicator>
                                    ),
                            },
                        ]}
                    />
                </Container>

                <Container
                    header={(
                        <Header
                            variant='h2'
                            actions={(
                                <SpaceBetween direction='horizontal' size='xs' alignItems='center'>
                                    <ButtonDropdown
                                        items={[
                                            {
                                                id: 'edit',
                                                text: 'Edit',
                                                disabled: !selectedCatalog,
                                                disabledReason: !selectedCatalog ? 'Select a catalog row below.' : undefined,
                                            },
                                            {
                                                id: 'remove',
                                                text: 'Remove from catalog',
                                                disabled: !selectedCatalog,
                                                disabledReason: !selectedCatalog ? 'Select a catalog row below.' : undefined,
                                            },
                                        ]}
                                        variant='primary'
                                        onItemClick={({ detail }) => handleLisaCatalogAction(detail)}
                                    >
                                        Actions
                                    </ButtonDropdown>
                                    <RefreshButton
                                        onClick={() => refetchApprovals()}
                                        isLoading={approvalsLoading}
                                        ariaLabel='Refresh catalog'
                                    />
                                </SpaceBetween>
                            )}
                            description='Approved agents appear in user Bedrock preferences and chat when visibility rules match.'
                        >
                            {`${getDisplayName()} catalog`}
                        </Header>
                    )}
                >
                    <Table
                        {...catalogCollectionProps}
                        ariaLabels={{ itemSelectionLabel: (_e, row) => row.agentName }}
                        header={null}
                        loading={approvalsLoading}
                        loadingText='Loading catalog'
                        empty={(
                            <TextContent>
                                <small>No catalog entries yet. Add agents from the scanned list on the left.</small>
                            </TextContent>
                        )}
                        variant='embedded'
                        selectionType='single'
                        selectedItems={catalogCollectionProps.selectedItems}
                        onSelectionChange={(e) => {
                            catalogCollectionProps.onSelectionChange?.(e);
                            if ((e.detail.selectedItems ?? []).length > 0) {
                                discoveryTableActions.setSelectedItems([]);
                            }
                        }}
                        pagination={<Pagination {...catalogPaginationProps} />}
                        items={catalogItems}
                        columnDefinitions={[
                            { id: 'name', header: 'Name', cell: (item) => item.agentName, sortingField: 'agentName' },
                            { id: 'id', header: 'Agent ID', cell: (item) => item.agentId },
                            {
                                id: 'visibility',
                                header: 'Visibility',
                                cell: (item) =>
                                    !item.groups?.length ? (
                                        <StatusIndicator type='info'>All users</StatusIndicator>
                                    ) : (
                                        catalogGroupsToDisplay(item.groups).join(', ')
                                    ),
                            },
                        ]}
                    />
                </Container>
            </Grid>

            {modal && (
                <Modal
                    visible
                    onDismiss={() => setModal(null)}
                    header={modal.mode === 'add' ? 'Add agent to catalog' : 'Edit catalog entry'}
                    footer={(
                        <Box float='right'>
                            <SpaceBetween direction='horizontal' size='xs'>
                                <Button variant='link' onClick={() => setModal(null)}>
                                    Cancel
                                </Button>
                                <Button variant='primary' onClick={() => void saveModal()} loading={putLoading}>
                                    Save
                                </Button>
                            </SpaceBetween>
                        </Box>
                    )}
                >
                    <SpaceBetween size='m'>
                        <FormField label='Agent ID'>
                            <Input value={modal.row.agentId} readOnly />
                        </FormField>
                        <FormField label='Display name'>
                            <Input value={agentName} onChange={({ detail }) => setAgentName(detail.value)} />
                        </FormField>
                        {modal.mode === 'add' && aliasSelectOptions.length > 0 ? (
                            <FormField label='Alias' description='Alias ID used when invoking the agent.'>
                                <Select
                                    selectedOption={
                                        aliasSelectOptions.find((o) => o.value === agentAliasId)
                                        ?? aliasSelectOptions[0]
                                    }
                                    onChange={({ detail }) => {
                                        if (detail.selectedOption?.value != null) {
                                            setAgentAliasId(String(detail.selectedOption.value));
                                        }
                                    }}
                                    options={aliasSelectOptions}
                                />
                            </FormField>
                        ) : (
                            <FormField label='Alias ID' description='Must match a prepared alias in Bedrock.'>
                                <Input value={agentAliasId} onChange={({ detail }) => setAgentAliasId(detail.value)} />
                            </FormField>
                        )}
                        <UserGroupsInput
                            label='Allowed groups'
                            description='Users must belong to one of these groups to see the agent. Leave empty to allow all authenticated users.'
                            values={groupTokens}
                            onChange={setGroupTokens}
                        />
                    </SpaceBetween>
                </Modal>
            )}
        </SpaceBetween>
    );
}

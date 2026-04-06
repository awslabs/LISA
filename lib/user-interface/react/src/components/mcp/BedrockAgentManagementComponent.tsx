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

type AddWizardState =
    | { step: 'select' }
    | { step: 'form'; row: BedrockAgentDiscoveryRow };

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

    const [addWizard, setAddWizard] = useState<AddWizardState | null>(null);
    const [editTarget, setEditTarget] = useState<BedrockAgentApprovalRow | null>(null);
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

    const selectedCatalog = catalogCollectionProps.selectedItems?.[0] as BedrockAgentApprovalRow | undefined;
    const selectedDiscovered = discoveryCollectionProps.selectedItems?.[0] as BedrockAgentDiscoveryRow | undefined;

    const populateFormFromDiscoveryRow = useCallback((row: BedrockAgentDiscoveryRow) => {
        setAgentName(row.agentName);
        const defaultAlias =
            row.suggestedAliasId
            ?? row.aliases.find((a) => a.agentAliasStatus === 'PREPARED')?.agentAliasId
            ?? row.aliases[0]?.agentAliasId
            ?? '';
        setAgentAliasId(defaultAlias);
        setGroupTokens([]);
    }, []);

    const closeAddWizard = useCallback(() => {
        setAddWizard(null);
    }, []);

    const closeEdit = useCallback(() => {
        setEditTarget(null);
    }, []);

    const openAddWizard = useCallback(() => {
        discoveryTableActions.setSelectedItems([]);
        setAddWizard({ step: 'select' });
        void runDiscovery();
    }, [discoveryTableActions, runDiscovery]);

    const openEdit = useCallback((row: BedrockAgentApprovalRow) => {
        setEditTarget(row);
        setAgentName(row.agentName);
        setAgentAliasId(row.agentAliasId);
        setGroupTokens(catalogGroupsToDisplay(row.groups));
    }, []);

    const saveCatalogEntry = async (agentId: string, isEdit: boolean) => {
        if (!agentName.trim() || !agentAliasId.trim()) {
            notificationService.generateNotification('Name and alias ID are required.', 'error');
            return;
        }
        try {
            await putApproval({
                agentId,
                body: {
                    agentName: agentName.trim(),
                    agentAliasId: agentAliasId.trim(),
                    groups: groupTokens.map((t) => t.trim()).filter(Boolean),
                },
            }).unwrap();
            notificationService.generateNotification(
                isEdit ? 'Catalog entry saved.' : 'Agent added to catalog.',
                'success'
            );
            if (isEdit) {
                closeEdit();
            } else {
                closeAddWizard();
            }
            catalogTableActions.setSelectedItems([]);
            discoveryTableActions.setSelectedItems([]);
        } catch (e: unknown) {
            const msg = e && typeof e === 'object' && 'message' in e ? String((e as { message: string }).message) : 'Save failed';
            notificationService.generateNotification(msg, 'error');
        }
    };

    const saveAddForm = () => {
        if (addWizard?.step !== 'form') return;
        void saveCatalogEntry(addWizard.row.agentId, false);
    };

    const saveEditForm = () => {
        if (!editTarget) return;
        void saveCatalogEntry(editTarget.agentId, true);
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

    const handleLisaCatalogAction = (detail: { id: string }) => {
        if (detail.id === 'edit' && selectedCatalog) {
            openEdit(selectedCatalog);
            return;
        }
        if (detail.id === 'remove' && selectedCatalog) {
            confirmRemove(selectedCatalog, () => catalogTableActions.setSelectedItems([]));
        }
    };

    const goToAddFormStep = () => {
        if (!selectedDiscovered) {
            notificationService.generateNotification('Select an agent from the list.', 'error');
            return;
        }
        if (!selectedDiscovered.invokeReady) {
            notificationService.generateNotification(
                'Choose an agent with a prepared alias (invocation ready).',
                'warning'
            );
            return;
        }
        populateFormFromDiscoveryRow(selectedDiscovered);
        setAddWizard({ step: 'form', row: selectedDiscovered });
    };

    const addFormRow = addWizard?.step === 'form' ? addWizard.row : null;
    const aliasSelectOptions =
        addFormRow
            ? addFormRow.aliases.map((a) => ({
                label: `${a.agentAliasName ?? a.agentAliasId} (${a.agentAliasId})`,
                value: a.agentAliasId,
            }))
            : [];

    return (
        <SpaceBetween size='l' direction='vertical'>
            <TextContent>
                <p>
                    Manage which Amazon Bedrock agents appear in the {getDisplayName()} catalog for your users.
                    Users only see entries that match their groups (or all users if you leave groups empty).
                </p>
            </TextContent>

            <Container
                header={(
                    <Header
                        variant='h2'
                        actions={(
                            <SpaceBetween direction='horizontal' size='xs' alignItems='center'>
                                <RefreshButton
                                    onClick={() => refetchApprovals()}
                                    isLoading={approvalsLoading}
                                    ariaLabel='Refresh catalog'
                                />
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
                                <Button variant='primary' onClick={openAddWizard}>
                                    Add to catalog
                                </Button>
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
                            <small>
                                No catalog entries yet. Choose <strong>Add to catalog</strong> to scan this Region and
                                add an agent.
                            </small>
                        </TextContent>
                    )}
                    variant='embedded'
                    selectionType='single'
                    selectedItems={catalogCollectionProps.selectedItems}
                    onSelectionChange={(e) => {
                        catalogCollectionProps.onSelectionChange?.(e);
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

            {addWizard && (
                <Modal
                    visible
                    onDismiss={closeAddWizard}
                    size='large'
                    header={
                        addWizard.step === 'select'
                            ? 'Add agent to catalog'
                            : 'Agent details'
                    }
                    footer={(
                        <Box float='right'>
                            <SpaceBetween direction='horizontal' size='xs'>
                                {addWizard.step === 'form' && (
                                    <Button
                                        variant='link'
                                        onClick={() => {
                                            discoveryTableActions.setSelectedItems([]);
                                            setAddWizard({ step: 'select' });
                                        }}
                                    >
                                        Back
                                    </Button>
                                )}
                                <Button variant='link' onClick={closeAddWizard}>
                                    Cancel
                                </Button>
                                {addWizard.step === 'select' ? (
                                    <Button variant='primary' onClick={goToAddFormStep}>
                                        Continue
                                    </Button>
                                ) : (
                                    <Button variant='primary' onClick={() => void saveAddForm()} loading={putLoading}>
                                        Save
                                    </Button>
                                )}
                            </SpaceBetween>
                        </Box>
                    )}
                >
                    {addWizard.step === 'select' ? (
                        <SpaceBetween size='m' direction='vertical'>
                            <TextContent>
                                <p>
                                    Scanning your AWS account in this Region for Bedrock agents. Select one that is not
                                    already in the catalog, then continue to set visibility and alias.
                                </p>
                            </TextContent>
                            <Table
                                {...discoveryCollectionProps}
                                ariaLabels={{ itemSelectionLabel: (_e, row) => row.agentName }}
                                header={null}
                                loading={discoveryLoading}
                                loadingText='Scanning account…'
                                empty={(
                                    <TextContent>
                                        <small>
                                            No agents to add—either none were found, or every discovered agent is already
                                            in the catalog.
                                        </small>
                                    </TextContent>
                                )}
                                variant='embedded'
                                selectionType='single'
                                selectedItems={discoveryCollectionProps.selectedItems}
                                onSelectionChange={(e) => {
                                    discoveryCollectionProps.onSelectionChange?.(e);
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
                        </SpaceBetween>
                    ) : (
                        <SpaceBetween size='m'>
                            <FormField label='Agent ID'>
                                <Input value={addWizard.row.agentId} readOnly />
                            </FormField>
                            <FormField label='Display name'>
                                <Input value={agentName} onChange={({ detail }) => setAgentName(detail.value)} />
                            </FormField>
                            {aliasSelectOptions.length > 0 ? (
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
                    )}
                </Modal>
            )}

            {editTarget && (
                <Modal
                    visible
                    onDismiss={closeEdit}
                    header='Edit catalog entry'
                    footer={(
                        <Box float='right'>
                            <SpaceBetween direction='horizontal' size='xs'>
                                <Button variant='link' onClick={closeEdit}>
                                    Cancel
                                </Button>
                                <Button variant='primary' onClick={() => void saveEditForm()} loading={putLoading}>
                                    Save
                                </Button>
                            </SpaceBetween>
                        </Box>
                    )}
                >
                    <SpaceBetween size='m'>
                        <FormField label='Agent ID'>
                            <Input value={editTarget.agentId} readOnly />
                        </FormField>
                        <FormField label='Display name'>
                            <Input value={agentName} onChange={({ detail }) => setAgentName(detail.value)} />
                        </FormField>
                        <FormField label='Alias ID' description='Must match a prepared alias in Bedrock.'>
                            <Input value={agentAliasId} onChange={({ detail }) => setAgentAliasId(detail.value)} />
                        </FormField>
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

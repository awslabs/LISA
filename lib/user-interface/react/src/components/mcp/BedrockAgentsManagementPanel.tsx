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
    ButtonDropdown,
    Header,
    Link,
    Pagination,
    SpaceBetween,
    Spinner,
    StatusIndicator,
    Table,
    TextContent,
    Toggle,
} from '@cloudscape-design/components';
import React, { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCollection } from '@cloudscape-design/collection-hooks';
import {
    DefaultUserPreferences,
    nextBedrockAgentsPrefs,
    useGetUserPreferencesQuery,
    useUpdateUserPreferencesMutation,
    UserPreferences,
} from '@/shared/reducers/user-preferences.reducer';
import { useListBedrockAgentsQuery } from '@/shared/reducers/mcp-server.reducer';
import type { BedrockAgentDiscoveryRow } from '@/types/bedrock-agent';
import { useAppDispatch, useAppSelector } from '@/config/store';
import { selectCurrentUsername } from '@/shared/reducers/user.reducer';
import { useNotificationService } from '@/shared/util/hooks';
import { getDisplayName } from '@/shared/util/branding';
import RefreshButton from '../common/RefreshButton';

export function BedrockAgentsManagementPanel (): React.ReactElement {
    const navigate = useNavigate();
    const dispatch = useAppDispatch();
    const notificationService = useNotificationService(dispatch);
    const userName = useAppSelector(selectCurrentUsername);
    const { data: userPreferences } = useGetUserPreferencesQuery();
    const { data, isFetching, refetch } = useListBedrockAgentsQuery();
    const [optimisticPreferences, setOptimisticPreferences] = useState<UserPreferences | null>(null);
    const [updatePreferences, { isLoading: isUpdating }] = useUpdateUserPreferencesMutation();

    const baselinePreferences = useMemo(
        () => (userPreferences ?? { ...DefaultUserPreferences, user: userName }) as UserPreferences,
        [userPreferences, userName]
    );

    const preferences = optimisticPreferences ?? baselinePreferences;

    const agents = data?.agents ?? [];

    const isAgentEnabled = (agentId: string) =>
        Boolean(preferences?.preferences?.bedrockAgents?.enabledAgents.some(
            (a) => a.agentId === agentId && a.enabled
        ));

    const isAgentAutoApprove = (agentId: string) =>
        Boolean(preferences?.preferences?.bedrockAgents?.enabledAgents.find((a) => a.agentId === agentId)?.autoApproveInvoke);

    const toggleAutoApproveForAgent = (agentId: string, autoApprove: boolean) => {
        if (!preferences) return;
        const cur = preferences.preferences.bedrockAgents?.enabledAgents ?? [];
        const nextAgents = cur.map((a) =>
            (a.agentId === agentId ? { ...a, autoApproveInvoke: autoApprove } : a));
        const updated: UserPreferences = {
            ...preferences,
            preferences: {
                ...preferences.preferences,
                bedrockAgents: nextBedrockAgentsPrefs(preferences.preferences.bedrockAgents, nextAgents),
            },
        };
        setOptimisticPreferences(updated);
        void updatePreferences(updated)
            .unwrap()
            .finally(() => {
                setOptimisticPreferences(null);
            });
    };

    const toggleBedrockAutopilotMode = () => {
        if (!preferences) return;
        const b = preferences.preferences.bedrockAgents ?? { enabledAgents: [] };
        const updated: UserPreferences = {
            ...preferences,
            preferences: {
                ...preferences.preferences,
                bedrockAgents: {
                    enabledAgents: b.enabledAgents,
                    overrideAllBedrockApprovals: !(b.overrideAllBedrockApprovals ?? false),
                },
            },
        };
        setOptimisticPreferences(updated);
        void updatePreferences(updated)
            .unwrap()
            .finally(() => {
                setOptimisticPreferences(null);
            });
    };

    const toggleAgent = (agent: BedrockAgentDiscoveryRow, enabled: boolean) => {
        if (!preferences || !agent.suggestedAliasId) {
            if (enabled) {
                notificationService.generateNotification(
                    'This agent has no alias prepared for invocation (prepare an alias in Bedrock).',
                    'warning'
                );
            }
            return;
        }
        const cur = preferences.preferences.bedrockAgents?.enabledAgents ?? [];
        let next;
        if (enabled) {
            const filtered = cur.filter((a) => a.agentId !== agent.agentId);
            const previous = cur.find((a) => a.agentId === agent.agentId);
            next = [
                ...filtered,
                {
                    agentId: agent.agentId,
                    agentAliasId: agent.suggestedAliasId,
                    name: agent.agentName,
                    enabled: true,
                    autoApproveInvoke: previous?.autoApproveInvoke ?? false,
                    ...(previous?.disabledActionTools?.length
                        ? { disabledActionTools: previous.disabledActionTools }
                        : {}),
                },
            ];
        } else {
            next = cur.filter((a) => a.agentId !== agent.agentId);
        }
        const updated: UserPreferences = {
            ...preferences,
            preferences: {
                ...preferences.preferences,
                bedrockAgents: nextBedrockAgentsPrefs(preferences.preferences.bedrockAgents, next),
            },
        };
        setOptimisticPreferences(updated);
        void updatePreferences(updated)
            .unwrap()
            .finally(() => {
                setOptimisticPreferences(null);
            });
    };

    const { paginationProps, items, collectionProps } = useCollection(agents, {
        trackBy: 'agentId',
        sorting: {
            defaultState: {
                sortingColumn: { sortingField: 'agentName' },
            },
        },
        pagination: { defaultPage: 1, pageSize: 10 },
    });

    return (
        <SpaceBetween size='l' direction='vertical'>
            <Table
                {...collectionProps}
                header={(
                    <Header
                        actions={(
                            <SpaceBetween direction='horizontal' size='xs' alignItems='center'>
                                <RefreshButton
                                    onClick={() => refetch()}
                                    isLoading={isFetching}
                                    ariaLabel='Refresh Bedrock agents'
                                />
                                <ButtonDropdown
                                    items={[
                                        {
                                            id: 'toggleBedrockAutopilot',
                                            text: preferences.preferences.bedrockAgents?.overrideAllBedrockApprovals
                                                ? 'Activate Safe Mode'
                                                : 'Activate Autopilot Mode',
                                        },
                                    ]}
                                    variant='primary'
                                    onItemClick={({ detail }) => {
                                        if (detail.id === 'toggleBedrockAutopilot') {
                                            toggleBedrockAutopilotMode();
                                        }
                                    }}
                                >
                                    Actions
                                </ButtonDropdown>
                            </SpaceBetween>
                        )}
                        description={`Opt in to use Bedrock agents from the ${getDisplayName()} catalog. Autopilot Mode auto-approves all Bedrock agent tools (like MCP). With Safe Mode, use per-agent auto-approve or confirm each invocation.`}
                    >
                        Amazon Bedrock agents
                    </Header>
                )}
                loading={isFetching}
                loadingText='Loading Bedrock agents'
                empty={(
                    <TextContent>
                        <small>
                            No agents are available yet.
                        </small>
                    </TextContent>
                )}
                variant='embedded'
                pagination={<Pagination {...paginationProps} />}
                items={items}
                columnDefinitions={[
                    {
                        id: 'use',
                        header: 'Use in chat',
                        cell: (item: BedrockAgentDiscoveryRow) => (
                            isUpdating ? <Spinner size='normal' /> : (
                                <Toggle
                                    checked={isAgentEnabled(item.agentId)}
                                    disabled={!item.invokeReady || isUpdating}
                                    onChange={({ detail }) => toggleAgent(item, detail.checked)}
                                />
                            )
                        ),
                    },
                    {
                        id: 'name',
                        header: 'Name',
                        cell: (item) => (
                            <Link onClick={() => navigate(`bedrock/${encodeURIComponent(item.agentId)}`)}>
                                {item.agentName}
                            </Link>
                        ),
                        sortingField: 'agentName',
                    },
                    { id: 'id', header: 'Agent ID', cell: (item) => item.agentId },
                    {
                        id: 'alias',
                        header: 'Suggested alias',
                        cell: (item) => item.suggestedAliasId ?? '—',
                    },
                    {
                        id: 'ready',
                        header: 'Invocation ready',
                        cell: (item) => (
                            item.invokeReady
                                ? <StatusIndicator type='success'>Yes</StatusIndicator>
                                : <StatusIndicator type='error'>No alias</StatusIndicator>
                        ),
                    },
                    {
                        id: 'autoApprove',
                        header: 'Auto-approve',
                        cell: (item: BedrockAgentDiscoveryRow) => (
                            isUpdating ? <Spinner size='normal' /> : (
                                <Toggle
                                    checked={isAgentAutoApprove(item.agentId)}
                                    disabled={!isAgentEnabled(item.agentId) || isUpdating}
                                    onChange={({ detail }) => toggleAutoApproveForAgent(item.agentId, detail.checked)}
                                />
                            )
                        ),
                    },
                    { id: 'status', header: 'Status', cell: (item) => item.agentStatus },
                ]}
            />
        </SpaceBetween>
    );
}

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
    ColumnLayout,
    Container,
    Grid,
    Header,
    Pagination,
    SpaceBetween,
    Spinner,
    StatusIndicator,
    Table,
    TextContent,
    Toggle,
} from '@cloudscape-design/components';
import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useCollection } from '@cloudscape-design/collection-hooks';
import { useListBedrockAgentsQuery } from '@/shared/reducers/mcp-server.reducer';
import {
    DefaultUserPreferences,
    nextBedrockAgentsPrefs,
    useGetUserPreferencesQuery,
    useUpdateUserPreferencesMutation,
    UserPreferences,
} from '@/shared/reducers/user-preferences.reducer';
import { setBreadcrumbs } from '@/shared/reducers/breadcrumbs.reducer';
import { useAppDispatch, useAppSelector } from '@/config/store';
import { selectCurrentUsername } from '@/shared/reducers/user.reducer';
import { useNotificationService } from '@/shared/util/hooks';

export function BedrockAgentDetails (): React.ReactElement {
    const { agentId: agentIdParam } = useParams();
    const agentId = agentIdParam ? decodeURIComponent(agentIdParam) : '';
    const navigate = useNavigate();
    const dispatch = useAppDispatch();
    const notificationService = useNotificationService(dispatch);
    const userName = useAppSelector(selectCurrentUsername);

    const { data: catalog, isFetching: catalogLoading } = useListBedrockAgentsQuery();
    const { data: userPreferences } = useGetUserPreferencesQuery();
    const [updatePreferences, { isLoading: isSavingPrefs }] = useUpdateUserPreferencesMutation();
    const [localPreferences, setLocalPreferences] = useState<UserPreferences | null>(null);
    const [updatingToolName, setUpdatingToolName] = useState<string | null>(null);

    useEffect(() => {
        if (userPreferences) {
            setLocalPreferences(userPreferences);
        }
    }, [userPreferences]);

    const preferences = localPreferences
        ?? (userPreferences ?? ({ ...DefaultUserPreferences, user: userName } as UserPreferences));

    const agent = useMemo(
        () => catalog?.agents?.find((a) => a.agentId === agentId),
        [catalog?.agents, agentId],
    );

    const prefEntry = preferences.preferences.bedrockAgents?.enabledAgents.find((a) => a.agentId === agentId);

    useEffect(() => {
        if (agent?.agentName) {
            dispatch(setBreadcrumbs([
                { text: 'Agentic connections', href: '/mcp-connections' },
                { text: agent.agentName, href: '' },
            ]));
        }
    }, [agent?.agentName, dispatch]);

    const toggleActionTool = (toolOpenAiName: string, useTool: boolean) => {
        if (!prefEntry?.enabled || !preferences || isSavingPrefs) {
            return;
        }
        setUpdatingToolName(toolOpenAiName);
        const cur = preferences.preferences.bedrockAgents?.enabledAgents ?? [];
        const disabled = new Set(prefEntry.disabledActionTools ?? []);
        if (useTool) {
            disabled.delete(toolOpenAiName);
        } else {
            disabled.add(toolOpenAiName);
        }
        const disabledArr = [...disabled].sort();
        const nextAgents = cur.map((a) =>
            (a.agentId === agentId
                ? {
                    ...a,
                    disabledActionTools: disabledArr.length > 0 ? disabledArr : undefined,
                }
                : a));
        const updated: UserPreferences = {
            ...preferences,
            preferences: {
                ...preferences.preferences,
                bedrockAgents: nextBedrockAgentsPrefs(preferences.preferences.bedrockAgents, nextAgents),
            },
        };
        setLocalPreferences(updated);
        void updatePreferences(updated)
            .unwrap()
            .then(() => {
                notificationService.generateNotification('Tool preference updated', 'success');
            })
            .catch((err: unknown) => {
                const msg = err instanceof Error ? err.message : String(err);
                notificationService.generateNotification(`Error updating tool preference: ${msg}`, 'error');
                setLocalPreferences(userPreferences ?? null);
            })
            .finally(() => {
                setUpdatingToolName(null);
            });
    };

    const toggleAutoApproveInvoke = (checked: boolean) => {
        if (!prefEntry?.enabled || !preferences || isSavingPrefs) {
            return;
        }
        const cur = preferences.preferences.bedrockAgents?.enabledAgents ?? [];
        const nextAgents = cur.map((a) =>
            (a.agentId === agentId ? { ...a, autoApproveInvoke: checked } : a));
        const updated: UserPreferences = {
            ...preferences,
            preferences: {
                ...preferences.preferences,
                bedrockAgents: nextBedrockAgentsPrefs(preferences.preferences.bedrockAgents, nextAgents),
            },
        };
        setLocalPreferences(updated);
        void updatePreferences(updated)
            .unwrap()
            .then(() => {
                notificationService.generateNotification('Preference updated', 'success');
            })
            .catch((err: unknown) => {
                const msg = err instanceof Error ? err.message : String(err);
                notificationService.generateNotification(`Error: ${msg}`, 'error');
                setLocalPreferences(userPreferences ?? null);
            });
    };

    const tools = agent?.actionTools ?? [];
    const { paginationProps, items, collectionProps } = useCollection(tools, {
        selection: {
            defaultSelectedItems: [],
            trackBy: 'openAiToolName',
            keepSelection: false,
        },
        pagination: {
            defaultPage: 1,
            pageSize: 20,
        },
    });

    const disabledToolSet = useMemo(
        () => new Set(prefEntry?.disabledActionTools ?? []),
        [prefEntry?.disabledActionTools],
    );

    if (!agentId) {
        return (
            <TextContent>
                <p>Missing agent ID.</p>
                <Button variant='link' onClick={() => navigate('/mcp-connections')}>Back to Agentic connections</Button>
            </TextContent>
        );
    }

    if (!catalogLoading && !agent) {
        return (
            <SpaceBetween size='l' direction='vertical'>
                <TextContent>
                    <p>This agent is not in your catalog. It may have been removed or you may not have access.</p>
                </TextContent>
                <Button variant='primary' onClick={() => navigate('/mcp-connections')}>Back to Agentic connections</Button>
            </SpaceBetween>
        );
    }

    return (
        <SpaceBetween size='l' direction='vertical'>
            <Grid gridDefinition={[{ colspan: 6 }, { colspan: 6 }]}>
                <Header variant='h1'>
                    {agent?.agentName ?? 'Bedrock agent'}
                </Header>
                <Box float='right' variant='div'>
                    <SpaceBetween direction='horizontal' size='s' alignItems='center'>
                        <Button variant='link' onClick={() => navigate('/mcp-connections')}>Back</Button>
                        <StatusIndicator type={agent?.invokeReady ? 'success' : 'error'}>
                            {agent?.invokeReady ? 'Invocation ready' : 'Not ready (alias)'}
                        </StatusIndicator>
                    </SpaceBetween>
                </Box>
            </Grid>

            <Container header={<Header variant='h2'>Agent details</Header>}>
                {catalogLoading && !agent ? (
                    <Spinner />
                ) : agent && (
                    <ColumnLayout columns={2} variant='text-grid'>
                        <SpaceBetween size='s'>
                            <div>
                                <Box variant='awsui-key-label'>Agent ID</Box>
                                <Box>{agent.agentId}</Box>
                            </div>
                            <div>
                                <Box variant='awsui-key-label'>Status</Box>
                                <Box>{agent.agentStatus}</Box>
                            </div>
                            {agent.description ? (
                                <div>
                                    <Box variant='awsui-key-label'>Description</Box>
                                    <Box>{agent.description}</Box>
                                </div>
                            ) : null}
                        </SpaceBetween>
                        <SpaceBetween size='s'>
                            <div>
                                <Box variant='awsui-key-label'>Suggested alias</Box>
                                <Box>{agent.suggestedAliasId ?? '—'}</Box>
                            </div>
                            {agent.inAccount !== undefined ? (
                                <div>
                                    <Box variant='awsui-key-label'>In account</Box>
                                    <Box>{agent.inAccount ? 'Yes' : 'No'}</Box>
                                </div>
                            ) : null}
                            {agent.catalogGroups && agent.catalogGroups.length > 0 ? (
                                <div>
                                    <Box variant='awsui-key-label'>Catalog groups</Box>
                                    <Box>{agent.catalogGroups.join(', ')}</Box>
                                </div>
                            ) : null}
                        </SpaceBetween>
                    </ColumnLayout>
                )}
            </Container>

            {prefEntry?.enabled && agent && (
                <Container header={<Header variant='h2'>Chat preferences</Header>}>
                    <SpaceBetween direction='horizontal' size='m' alignItems='center'>
                        {isSavingPrefs ? <Spinner size='normal' /> : (
                            <Toggle
                                checked={Boolean(prefEntry.autoApproveInvoke)}
                                onChange={({ detail }) => toggleAutoApproveInvoke(detail.checked)}
                            />
                        )}
                        <TextContent>
                            <small>Auto-approve invocations for this agent (skip the confirmation step in chat).</small>
                        </TextContent>
                    </SpaceBetween>
                </Container>
            )}

            {!prefEntry?.enabled && agent && (
                <TextContent>
                    <small>Turn on &quot;Use in chat&quot; for this agent on the Bedrock agents tab to enable per-tool toggles.</small>
                </TextContent>
            )}

            <Table
                {...collectionProps}
                header={
                    <Header counter={tools.length ? `(${tools.length})` : undefined}>
                        Agent tools
                    </Header>
                }
                sortingDisabled={false}
                selectedItems={collectionProps.selectedItems}
                loading={catalogLoading}
                loadingText='Loading agent tools'
                empty={(
                    <SpaceBetween direction='vertical' size='s' alignItems='center'>
                        <TextContent><small>No tools were discovered for this agent.</small></TextContent>
                    </SpaceBetween>
                )}
                variant='full-page'
                pagination={<Pagination {...paginationProps} />}
                items={items}
                columnDefinitions={[
                    {
                        id: 'use',
                        header: 'Use tool',
                        cell: (item) => (
                            updatingToolName === item.openAiToolName ? (
                                <Spinner size='normal' />
                            ) : (
                                <Toggle
                                    checked={!disabledToolSet.has(item.openAiToolName)}
                                    onChange={({ detail }) => toggleActionTool(item.openAiToolName, detail.checked)}
                                    disabled={!prefEntry?.enabled || isSavingPrefs}
                                />
                            )
                        ),
                    },
                    { id: 'toolName', header: 'Tool name', cell: (item) => item.openAiToolName },
                    { id: 'function', header: 'Function', cell: (item) => item.functionName },
                    { id: 'actionGroup', header: 'Action group', cell: (item) => item.actionGroupName || item.actionGroupId },
                    { id: 'desc', header: 'Description', cell: (item) => item.description },
                ]}
            />
        </SpaceBetween>
    );
}

export default BedrockAgentDetails;

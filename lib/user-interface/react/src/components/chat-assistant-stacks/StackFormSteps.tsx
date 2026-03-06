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

import { ReactElement, useMemo } from 'react';
import {
    Alert,
    Box,
    Checkbox,
    FormField,
    Input,
    Select,
    SpaceBetween,
    Spinner,
    StatusIndicator,
    Textarea,
} from '@cloudscape-design/components';
import { FormProps } from '@/shared/form/form-props';
import { UserGroupsInput } from '@/shared/form/UserGroupsInput';
import { ChatAssistantStackRequestForm } from '@/shared/model/chat-assistant-stack.model';
import { ModelType } from '@/shared/model/model-management.model';
import { useGetAllModelsQuery } from '@/shared/reducers/model-management.reducer';
import { useListRagRepositoriesQuery, useListAllCollectionsQuery } from '@/shared/reducers/rag.reducer';
import { useListMcpServersQuery, useListHostedMcpServersQuery } from '@/shared/reducers/mcp-server.reducer';
import { useListPromptTemplatesQuery } from '@/shared/reducers/prompt-templates.reducer';
import { PromptTemplateType } from '@/shared/reducers/prompt-templates.reducer';
import { VectorStoreStatus } from '#root/lib/schema';
import { STACK_NAME_MAX_LENGTH_EXPORT } from '@/shared/model/chat-assistant-stack.model';

type StackFormProps = FormProps<ChatAssistantStackRequestForm>;

export function StackBaseForm (props: StackFormProps): ReactElement {
    const { item, setFields, touchFields, formErrors } = props;
    return (
        <SpaceBetween size='m'>
            <FormField
                label='Stack Assistant Name'
                description={`Name shown to users. Max ${STACK_NAME_MAX_LENGTH_EXPORT} characters.`}
                errorText={formErrors?.name}
            >
                <Input
                    value={item.name}
                    onChange={({ detail }) => setFields({ name: detail.value })}
                    onBlur={() => touchFields(['name'])}
                    placeholder='e.g. Developer Assistant'
                />
            </FormField>
            <FormField label='Description' errorText={formErrors?.description}>
                <Textarea
                    value={item.description}
                    onChange={({ detail }) => setFields({ description: detail.value })}
                    onBlur={() => touchFields(['description'])}
                    placeholder='Describe what this assistant stack is for'
                    rows={3}
                />
            </FormField>
        </SpaceBetween>
    );
}

export function StackModelsStep (props: StackFormProps): ReactElement {
    const { item, setFields, formErrors } = props;
    const { data: models, isLoading, error } = useGetAllModelsQuery(undefined, { refetchOnMountOrArgChange: true });
    const selected = item.modelIds || [];
    const toggle = (modelId: string) => {
        if (selected.includes(modelId)) {
            setFields({ modelIds: selected.filter((id) => id !== modelId) });
        } else {
            setFields({ modelIds: [...selected, modelId] });
        }
    };
    if (isLoading) return <Spinner />;
    if (error) return <StatusIndicator type='error'>Failed to load models</StatusIndicator>;
    const list = (models || []).filter((m) => m.modelType !== ModelType.embedding);
    return (
        <SpaceBetween size='m'>
            <Alert type='info'>Select at least one model. Embedding models are excluded (used for RAG only).</Alert>
            <FormField label='Models' errorText={formErrors?.modelIds} description='Select one or more models.'>
                <SpaceBetween size='s'>
                    {list.map((m) => (
                        <Checkbox
                            key={m.modelId}
                            checked={selected.includes(m.modelId)}
                            onChange={() => toggle(m.modelId)}
                        >
                            {m.modelId} {m.modelName && `(${m.modelName})`} — {m.modelType}
                        </Checkbox>
                    ))}
                    {list.length === 0 && <Box color='text-body-secondary'>No models available.</Box>}
                </SpaceBetween>
            </FormField>
        </SpaceBetween>
    );
}

export function StackRagStep (props: StackFormProps): ReactElement {
    const { item, setFields } = props;
    const ragEnabled = typeof window !== 'undefined' && (window as any).env?.RAG_ENABLED;
    const { data: repositories, isLoading: loadingRepos } = useListRagRepositoriesQuery(undefined, { refetchOnMountOrArgChange: true, skip: !ragEnabled });
    const { data: allCollections, isLoading: loadingCollections } = useListAllCollectionsQuery(undefined, { refetchOnMountOrArgChange: true, skip: !ragEnabled });
    const repoIds = useMemo(() => item.repositoryIds || [], [item.repositoryIds]);
    const collIds = item.collectionIds || [];
    const toggleRepo = (id: string) => {
        if (repoIds.includes(id)) {
            const newRepoIds = repoIds.filter((x) => x !== id);
            const collectionsByRepo = (allCollections || []).filter((c) => c.repositoryId === id);
            const idsToRemove = new Set(collectionsByRepo.map((c) => c.collectionId));
            const newCollIds = collIds.filter((cid) => !idsToRemove.has(cid));
            setFields({ repositoryIds: newRepoIds, collectionIds: newCollIds });
        } else {
            setFields({ repositoryIds: [...repoIds, id] });
        }
    };
    const toggleColl = (id: string) => {
        if (collIds.includes(id)) setFields({ collectionIds: collIds.filter((x) => x !== id) });
        else setFields({ collectionIds: [...collIds, id] });
    };
    const repos = useMemo(() => {
        if (!repositories) return [];
        return repositories.filter(
            (r) => r.status === VectorStoreStatus.CREATE_COMPLETE || r.status === VectorStoreStatus.UPDATE_COMPLETE
        );
    }, [repositories]);
    const allCollectionsList = useMemo(() => allCollections || [], [allCollections]);
    const collectionsForSelectedRepos = useMemo(() => {
        if (repoIds.length === 0) return [];
        return allCollectionsList.filter((c) => c.repositoryId && repoIds.includes(c.repositoryId));
    }, [allCollectionsList, repoIds]);
    if (loadingRepos || loadingCollections) return <Spinner />;
    return (
        <SpaceBetween size='m'>
            <FormField
                label='RAG Repositories'
                description='Select one or more repositories first. Collections below are limited to the repositories you select here.'
            >
                <SpaceBetween size='s'>
                    {repos.map((r) => (
                        <Checkbox
                            key={r.repositoryId}
                            checked={repoIds.includes(r.repositoryId)}
                            onChange={() => toggleRepo(r.repositoryId)}
                        >
                            {r.repositoryName || r.repositoryId}
                        </Checkbox>
                    ))}
                    {repos.length === 0 && <Box color='text-body-secondary'>No repositories available.</Box>}
                </SpaceBetween>
            </FormField>
            <FormField
                label='RAG Collections'
                description={repoIds.length === 0
                    ? 'Select at least one repository above to see and choose collections.'
                    : 'Only collections from the selected repositories are shown.'}
            >
                <SpaceBetween size='s'>
                    {repoIds.length === 0 ? (
                        <></>
                    ) : (
                        collectionsForSelectedRepos.map((c) => (
                            <Checkbox
                                key={c.collectionId}
                                checked={collIds.includes(c.collectionId)}
                                onChange={() => toggleColl(c.collectionId)}
                            >
                                {c.name || c.collectionId} {c.repositoryId && `(${c.repositoryId})`}
                            </Checkbox>
                        ))
                    )}
                    {repoIds.length > 0 && collectionsForSelectedRepos.length === 0 && (
                        <Box color='text-body-secondary'>No collections in the selected repositories.</Box>
                    )}
                </SpaceBetween>
            </FormField>
        </SpaceBetween>
    );
}

export function StackAgentsStep (props: StackFormProps): ReactElement {
    const { item, setFields } = props;
    const { data: connectionServers } = useListMcpServersQuery(undefined, { refetchOnMountOrArgChange: true });
    const { data: hostedServers } = useListHostedMcpServersQuery(undefined, { refetchOnMountOrArgChange: true });
    const mcpServerIds = item.mcpServerIds || [];
    const servers = useMemo(() => {
        const byId = new Map<string, { id: string; name: string }>();
        (connectionServers?.Items || []).forEach((s) => byId.set(s.id, { id: s.id, name: s.name }));
        (hostedServers || []).forEach((s) => byId.set(s.id, { id: s.id, name: s.name }));
        return Array.from(byId.values());
    }, [connectionServers, hostedServers]);
    const toggleServer = (id: string) => {
        if (mcpServerIds.includes(id)) setFields({ mcpServerIds: mcpServerIds.filter((x) => x !== id) });
        else setFields({ mcpServerIds: [...mcpServerIds, id] });
    };
    return (
        <SpaceBetween size='m'>
            <Alert type='info'>If you select at least one MCP server, at least one selected model must support MCP tools (e.g. text generation models).</Alert>
            <FormField label='MCP Servers' description='From LISA MCP, Workbench, or Connections.'>
                <SpaceBetween size='s'>
                    {servers.map((s) => (
                        <Checkbox key={s.id} checked={mcpServerIds.includes(s.id)} onChange={() => toggleServer(s.id)}>
                            {s.name} ({s.id})
                        </Checkbox>
                    ))}
                    {servers.length === 0 && <Box color='text-body-secondary'>No MCP servers available.</Box>}
                </SpaceBetween>
            </FormField>
        </SpaceBetween>
    );
}

export function StackPromptsStep (props: StackFormProps): ReactElement {
    const { item, setFields } = props;
    const { data: listResponse, isLoading } = useListPromptTemplatesQuery({ showPublic: true }, { refetchOnMountOrArgChange: true });
    const templates = useMemo(() => listResponse?.Items || [], [listResponse]);
    const persona = templates.filter((t) => t.type === PromptTemplateType.Persona);
    const directive = templates.filter((t) => t.type === PromptTemplateType.Directive);
    const personaPromptId = item.personaPromptId ?? '';
    const directivePromptIds = item.directivePromptIds || [];
    const toggleDirective = (id: string) => {
        if (directivePromptIds.includes(id)) setFields({ directivePromptIds: directivePromptIds.filter((x) => x !== id) });
        else setFields({ directivePromptIds: [...directivePromptIds, id] });
    };
    if (isLoading) return <Spinner />;
    const personaOptions = [{ value: '', label: 'None' }, ...persona.map((t) => ({ value: t.id, label: t.title || t.id }))];
    return (
        <SpaceBetween size='m'>
            <FormField label='Persona Prompt' description='System promptapplied in the background (e.g. developer persona).'>
                <Select
                    selectedOption={personaOptions.find((o) => o.value === personaPromptId) || personaOptions[0]}
                    options={personaOptions}
                    onChange={({ detail }) => setFields({ personaPromptId: detail.selectedOption.value ? detail.selectedOption.value : null })}
                />
            </FormField>
            <FormField label='Directive Prompts' description='User can select from these.'>
                <SpaceBetween size='s'>
                    {directive.map((t) => (
                        <Checkbox
                            key={t.id}
                            checked={directivePromptIds.includes(t.id)}
                            onChange={() => toggleDirective(t.id)}
                        >
                            {t.title || t.id}
                        </Checkbox>
                    ))}
                    {directive.length === 0 && <Box color='text-body-secondary'>No directive prompts available.</Box>}
                </SpaceBetween>
            </FormField>
        </SpaceBetween>
    );
}

export function StackAccessStep (props: StackFormProps): ReactElement {
    const { item, setFields, formErrors } = props;
    return (
        <SpaceBetween size='m'>
            <UserGroupsInput
                label='Allowed Groups'
                description='Leave empty for global access. Users only see resources they have access to.'
                values={item.allowedGroups || []}
                onChange={(groups) => setFields({ allowedGroups: groups })}
                errorText={formErrors?.allowedGroups}
            />
        </SpaceBetween>
    );
}

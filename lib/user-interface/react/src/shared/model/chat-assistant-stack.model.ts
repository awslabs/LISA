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

import { z } from 'zod';

const STACK_NAME_MAX_LENGTH = 256;

export type IChatAssistantStack = {
    stackId: string;
    name: string;
    description: string;
    modelIds: string[];
    guardrailIds?: string[];
    repositoryIds: string[];
    collectionIds: string[];
    mcpServerIds: string[];
    mcpToolIds: string[];
    personaPromptId?: string | null;
    directivePromptIds: string[];
    allowedGroups: string[];
    isActive: boolean;
    created?: string;
    updated?: string;
};

export type IChatAssistantStackRequest = {
    name: string;
    description: string;
    modelIds: string[];
    guardrailIds?: string[];
    repositoryIds: string[];
    collectionIds: string[];
    mcpServerIds: string[];
    mcpToolIds: string[];
    personaPromptId?: string | null;
    directivePromptIds: string[];
    allowedGroups: string[];
};

export const ChatAssistantStackRequestSchema = z.object({
    name: z.string().min(1, 'Stack Assistant Name is required').max(STACK_NAME_MAX_LENGTH, `Name must be ${STACK_NAME_MAX_LENGTH} characters or less`),
    description: z.string().min(1, 'Description is required'),
    modelIds: z.array(z.string()).min(1, 'Select at least one model'),
    guardrailIds: z.array(z.string()).optional().default([]),
    repositoryIds: z.array(z.string()).default([]),
    collectionIds: z.array(z.string()).default([]),
    mcpServerIds: z.array(z.string()).default([]),
    mcpToolIds: z.array(z.string()).default([]),
    personaPromptId: z.string().nullable().optional(),
    directivePromptIds: z.array(z.string()).default([]),
    allowedGroups: z.array(z.string()).default([]),
}).superRefine((data) => {
    if (data.mcpServerIds.length > 0 && data.modelIds.length > 0) {
        // AS-9: When at least one MCP Server is selected, at least one model must support MCP tools.
        // We cannot validate "model supports MCP" here without model list; validation is done in UI.
    }
});

export type ChatAssistantStackRequestForm = z.infer<typeof ChatAssistantStackRequestSchema>;

export const STACK_NAME_MAX_LENGTH_EXPORT = STACK_NAME_MAX_LENGTH;

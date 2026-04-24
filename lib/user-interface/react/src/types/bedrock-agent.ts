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

export type BedrockAgentAlias = {
    agentAliasId: string;
    agentAliasName?: string;
    agentAliasStatus?: string;
    description?: string;
};

export type BedrockAgentActionToolRow = {
    openAiToolName: string;
    functionName: string;
    actionGroupId: string;
    actionGroupName: string;
    description: string;
    parameterSchema: {
        type?: string;
        properties?: Record<string, unknown>;
        required?: string[];
    };
};

export type BedrockAgentDiscoveryRow = {
    agentId: string;
    agentName: string;
    agentStatus: string;
    description?: string;
    updatedAt?: string;
    latestAgentVersion?: string;
    suggestedAliasId?: string | null;
    aliases: BedrockAgentAlias[];
    invokeReady: boolean;
    actionTools?: BedrockAgentActionToolRow[];
    /** Present when merged from admin catalog + discovery */
    inAccount?: boolean;
    catalogGroups?: string[];
};

export type BedrockAgentApprovalRow = {
    agentId: string;
    agentAliasId: string;
    agentName: string;
    groups?: string[];
    updatedAt?: string;
    updatedBy?: string;
};

export type ListBedrockAgentApprovalsResponse = {
    approvals: BedrockAgentApprovalRow[];
};

export type PutBedrockAgentApprovalRequest = {
    agentAliasId: string;
    agentName: string;
    /** Plain group names or group: tokens; empty = all users */
    groups?: string[];
};

export type ListBedrockAgentsResponse = {
    agents: BedrockAgentDiscoveryRow[];
    totalAgents: number;
};

export type InvokeBedrockAgentRequest = {
    agentId: string;
    agentAliasId: string;
    /** Natural-language turn; omit when using functionName */
    inputText?: string;
    sessionId?: string;
    /** When set, server builds inputText targeting this action-group function */
    functionName?: string;
    actionGroupId?: string;
    actionGroupName?: string;
    parameters?: Record<string, unknown>;
};

export type InvokeBedrockAgentResponse = {
    outputText: string;
    sessionId: string;
};

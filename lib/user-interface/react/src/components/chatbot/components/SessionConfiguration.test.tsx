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

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SessionConfiguration, SessionConfigurationProps } from './SessionConfiguration';
import { baseConfig } from '@/shared/model/chat.configurations.model';
import { ModelType } from '@/shared/model/model-management.model';
import { IConfiguration } from '@/shared/model/configuration.model';

function buildProps (overrides: Partial<SessionConfigurationProps> = {}): SessionConfigurationProps {
    const defaultSystemConfig: IConfiguration = {
        configScope: 'global',
        versionId: 0,
        changedBy: 'test',
        changeReason: 'test',
        configuration: {
            systemBanner: { isEnabled: false, text: '', textColor: '', backgroundColor: '' },
            enabledComponents: {
                deleteSessionHistory: true,
                viewMetaData: true,
                editKwargs: true,
                editPromptTemplate: true,
                editNumOfRagDocument: true,
                editChatHistoryBuffer: true,
                uploadRagDocs: true,
                ragSelectionAvailable: true,
                uploadContextDocs: true,
                documentSummarization: true,
                showRagLibrary: true,
                showPromptTemplateLibrary: true,
                enableModelComparisonUtility: false,
                mcpConnections: false,
                awsSessions: false,
                showMcpWorkbench: false,
                modelLibrary: true,
                encryptSession: false,
                enableUserApiTokens: false,
                chatAssistantStacks: false,
                projectOrganization: false,
                hybridSearch: false,
            },
            global: { defaultModel: '' },
            maxProjectsPerUser: 50,
            announcement: { isEnabled: false, message: '' },
        },
    };

    return {
        chatConfiguration: { ...baseConfig },
        setChatConfiguration: vi.fn(),
        setVisible: vi.fn(),
        visible: true,
        selectedModel: { modelId: 'test-model', modelType: ModelType.textgen } as any,
        isRunning: false,
        systemConfig: defaultSystemConfig,
        ...overrides,
    };
}

describe('SessionConfiguration — hybrid search', () => {
    it('shows RAG Search Mode selector when hybridSearch enabled and repo supports it', () => {
        const props = buildProps({
            ragConfig: { repositoryId: 'repo-1', repositoryType: 'bedrock_knowledge_base', supportsHybridSearch: true },
        });
        props.systemConfig.configuration.enabledComponents.hybridSearch = true;
        render(<SessionConfiguration {...props} />);
        expect(screen.getByText('RAG Search Mode')).toBeInTheDocument();
    });

    it('hides RAG Search Mode selector when hybridSearch admin flag is disabled', () => {
        const props = buildProps({
            ragConfig: { repositoryId: 'repo-1', repositoryType: 'bedrock_knowledge_base', supportsHybridSearch: true },
        });
        props.systemConfig.configuration.enabledComponents.hybridSearch = false;
        render(<SessionConfiguration {...props} />);
        expect(screen.queryByText('RAG Search Mode')).not.toBeInTheDocument();
    });

    it('hides RAG Search Mode selector when repo does not support hybrid', () => {
        const props = buildProps({
            ragConfig: { repositoryId: 'repo-1', repositoryType: 'opensearch', supportsHybridSearch: false },
        });
        props.systemConfig.configuration.enabledComponents.hybridSearch = true;
        render(<SessionConfiguration {...props} />);
        expect(screen.queryByText('RAG Search Mode')).not.toBeInTheDocument();
    });
});

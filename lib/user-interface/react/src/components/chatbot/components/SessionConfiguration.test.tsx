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

describe('SessionConfiguration — RAG Settings card', () => {
    it('renders RAG Settings container when editNumOfRagDocument is enabled', () => {
        const props = buildProps();
        props.systemConfig.configuration.enabledComponents.editNumOfRagDocument = true;
        render(<SessionConfiguration {...props} />);
        expect(screen.getByText('RAG Settings')).toBeInTheDocument();
    });

    it('does not render RAG Settings container when editNumOfRagDocument is disabled', () => {
        const props = buildProps();
        props.systemConfig.configuration.enabledComponents.editNumOfRagDocument = false;
        render(<SessionConfiguration {...props} />);
        expect(screen.queryByText('RAG Settings')).not.toBeInTheDocument();
    });

    it('does not render RAG Settings container for image models', () => {
        const props = buildProps({
            selectedModel: { modelId: 'img-model', modelType: ModelType.imagegen } as any,
        });
        render(<SessionConfiguration {...props} />);
        expect(screen.queryByText('RAG Settings')).not.toBeInTheDocument();
    });

    it('does not render RAG Settings container for video models', () => {
        const props = buildProps({
            selectedModel: { modelId: 'vid-model', modelType: ModelType.videogen } as any,
        });
        render(<SessionConfiguration {...props} />);
        expect(screen.queryByText('RAG Settings')).not.toBeInTheDocument();
    });

    it('does not render RAG Settings container when modelOnly is true', () => {
        const props = buildProps({ modelOnly: true });
        render(<SessionConfiguration {...props} />);
        expect(screen.queryByText('RAG Settings')).not.toBeInTheDocument();
    });

    it('renders Matching RAG Excerpts inside the RAG Settings card', () => {
        const props = buildProps();
        render(<SessionConfiguration {...props} />);
        expect(screen.getByText('RAG Settings')).toBeInTheDocument();
        expect(screen.getByText('Matching RAG Excerpts')).toBeInTheDocument();
    });

    it('renders HybridSearchControls when hybrid mode is active', () => {
        const props = buildProps({
            ragConfig: { repositoryId: 'repo-1', repositoryType: 'opensearch', supportsHybridSearch: true },
            chatConfiguration: {
                ...baseConfig,
                sessionConfiguration: { ...baseConfig.sessionConfiguration, ragSearchMode: 'hybrid' },
            },
        });
        props.systemConfig.configuration.enabledComponents.hybridSearch = true;
        render(<SessionConfiguration {...props} />);
        expect(screen.getByRole('slider', { name: /vector weight/i })).toBeInTheDocument();
    });

    it('does not render HybridSearchControls when search mode is vector', () => {
        const props = buildProps({
            ragConfig: { repositoryId: 'repo-1', repositoryType: 'opensearch', supportsHybridSearch: true },
            chatConfiguration: {
                ...baseConfig,
                sessionConfiguration: { ...baseConfig.sessionConfiguration, ragSearchMode: 'vector' },
            },
        });
        props.systemConfig.configuration.enabledComponents.hybridSearch = true;
        render(<SessionConfiguration {...props} />);
        expect(screen.queryByRole('slider', { name: /vector weight/i })).not.toBeInTheDocument();
    });

    it('does not render HybridSearchControls when repo does not support hybrid', () => {
        const props = buildProps({
            ragConfig: { repositoryId: 'repo-1', repositoryType: 'opensearch', supportsHybridSearch: false },
            chatConfiguration: {
                ...baseConfig,
                sessionConfiguration: { ...baseConfig.sessionConfiguration, ragSearchMode: 'hybrid' },
            },
        });
        props.systemConfig.configuration.enabledComponents.hybridSearch = true;
        render(<SessionConfiguration {...props} />);
        expect(screen.queryByRole('slider', { name: /vector weight/i })).not.toBeInTheDocument();
    });
});

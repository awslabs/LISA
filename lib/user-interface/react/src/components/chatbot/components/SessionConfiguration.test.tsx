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

describe('SessionConfiguration — RAG Settings card', () => {
    it('renders RAG Settings container when editNumOfRagDocument is enabled', () => {
        const props = buildProps();
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
});

describe('SessionConfiguration — RAG Search Mode (disable-not-hide)', () => {
    it('RAG Search Mode is always visible in RAG Settings card', () => {
        const props = buildProps();
        render(<SessionConfiguration {...props} />);
        expect(screen.getByText('RAG Search Mode')).toBeInTheDocument();
    });

    it('RAG Search Mode is enabled when hybridSearch admin flag on and repo supports it', () => {
        const props = buildProps({
            ragConfig: { repositoryId: 'repo-1', repositoryType: 'opensearch', supportsHybridSearch: true },
        });
        props.systemConfig.configuration.enabledComponents.hybridSearch = true;
        render(<SessionConfiguration {...props} />);
        expect(screen.queryByText('Hybrid search is disabled by your administrator')).not.toBeInTheDocument();
        expect(screen.queryByText('Selected repository does not support hybrid search')).not.toBeInTheDocument();
    });

    it('RAG Search Mode is disabled when hybridSearch admin flag is off', () => {
        const props = buildProps({
            ragConfig: { repositoryId: 'repo-1', repositoryType: 'opensearch', supportsHybridSearch: true },
        });
        props.systemConfig.configuration.enabledComponents.hybridSearch = false;
        render(<SessionConfiguration {...props} />);
        expect(screen.getByText('Hybrid search is disabled by your administrator')).toBeInTheDocument();
    });

    it('RAG Search Mode is disabled when repo does not support hybrid', () => {
        const props = buildProps({
            ragConfig: { repositoryId: 'repo-1', repositoryType: 'opensearch', supportsHybridSearch: false },
        });
        props.systemConfig.configuration.enabledComponents.hybridSearch = true;
        render(<SessionConfiguration {...props} />);
        expect(screen.getByText('Selected repository does not support hybrid search')).toBeInTheDocument();
    });
});

describe('SessionConfiguration — HybridSearchControls (disable-not-hide)', () => {
    it('weight sliders are always rendered in RAG Settings card', () => {
        const props = buildProps();
        render(<SessionConfiguration {...props} />);
        expect(screen.getByRole('slider', { name: /vector weight/i })).toBeInTheDocument();
    });

    it('weight sliders are enabled when hybrid mode active on OpenSearch repo', () => {
        const props = buildProps({
            ragConfig: { repositoryId: 'repo-1', repositoryType: 'opensearch', supportsHybridSearch: true },
            chatConfiguration: {
                ...baseConfig,
                sessionConfiguration: { ...baseConfig.sessionConfiguration, ragSearchMode: 'hybrid' },
            },
        });
        props.systemConfig.configuration.enabledComponents.hybridSearch = true;
        render(<SessionConfiguration {...props} />);
        const slider = screen.getByRole('slider', { name: /vector weight/i });
        expect(slider).not.toBeDisabled();
    });

    it('weight sliders are disabled when search mode is vector', () => {
        const props = buildProps({
            ragConfig: { repositoryId: 'repo-1', repositoryType: 'opensearch', supportsHybridSearch: true },
            chatConfiguration: {
                ...baseConfig,
                sessionConfiguration: { ...baseConfig.sessionConfiguration, ragSearchMode: 'vector' },
            },
        });
        props.systemConfig.configuration.enabledComponents.hybridSearch = true;
        render(<SessionConfiguration {...props} />);
        const slider = screen.getByRole('slider', { name: /vector weight/i });
        expect(slider).toBeDisabled();
    });

    it('weight sliders are disabled for Bedrock KB repos even in hybrid mode', () => {
        const props = buildProps({
            ragConfig: { repositoryId: 'repo-1', repositoryType: 'bedrock_knowledge_base', supportsHybridSearch: true },
            chatConfiguration: {
                ...baseConfig,
                sessionConfiguration: { ...baseConfig.sessionConfiguration, ragSearchMode: 'hybrid' },
            },
        });
        props.systemConfig.configuration.enabledComponents.hybridSearch = true;
        render(<SessionConfiguration {...props} />);
        const slider = screen.getByRole('slider', { name: /vector weight/i });
        expect(slider).toBeDisabled();
    });

    it('weight sliders are disabled when isRunning', () => {
        const props = buildProps({
            isRunning: true,
            ragConfig: { repositoryId: 'repo-1', repositoryType: 'opensearch', supportsHybridSearch: true },
            chatConfiguration: {
                ...baseConfig,
                sessionConfiguration: { ...baseConfig.sessionConfiguration, ragSearchMode: 'hybrid' },
            },
        });
        props.systemConfig.configuration.enabledComponents.hybridSearch = true;
        render(<SessionConfiguration {...props} />);
        const slider = screen.getByRole('slider', { name: /vector weight/i });
        expect(slider).toBeDisabled();
    });
});

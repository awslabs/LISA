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

import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { BedrockKnowledgeBaseConfigForm } from './BedrockKnowledgeBaseConfigForm';
import { BedrockKnowledgeBaseInstanceConfig } from '#root/lib/schema';

// Mock the RTK Query hooks
vi.mock('@/shared/reducers/rag.reducer', () => ({
    useListBedrockKnowledgeBasesQuery: vi.fn(),
    useListBedrockDataSourcesQuery: vi.fn(),
}));

import {
    useListBedrockKnowledgeBasesQuery,
    useListBedrockDataSourcesQuery,
} from '@/shared/reducers/rag.reducer';

describe('BedrockKnowledgeBaseConfigForm', () => {
    const mockSetFields = vi.fn();
    const mockTouchFields = vi.fn();

    const defaultProps = {
        item: BedrockKnowledgeBaseInstanceConfig.parse({}),
        setFields: mockSetFields,
        touchFields: mockTouchFields,
        formErrors: {},
        isEdit: false,
    };

    beforeEach(() => {
        vi.clearAllMocks();
        // Mock the hooks to return empty data
        (useListBedrockKnowledgeBasesQuery as any).mockReturnValue({
            data: { knowledgeBases: [] },
            isLoading: false,
        });
        (useListBedrockDataSourcesQuery as any).mockReturnValue({
            data: { dataSources: [] },
            isLoading: false,
        });
    });

    it('renders the informational alert about document management', () => {
        render(<BedrockKnowledgeBaseConfigForm {...defaultProps} />);

        expect(screen.getByText('How LISA manages your Knowledge Base documents')).toBeInTheDocument();
        expect(screen.getByText(/LISA tracks document ownership to preserve your existing data/)).toBeInTheDocument();
        expect(screen.getByText(/Documents already in your Knowledge Base are marked as user-managed/)).toBeInTheDocument();
        expect(screen.getByText(/Only documents uploaded through LISA/)).toBeInTheDocument();
    });

    it('renders Knowledge Base selector', () => {
        render(<BedrockKnowledgeBaseConfigForm {...defaultProps} />);

        expect(screen.getByLabelText('Knowledge Base')).toBeInTheDocument();
        expect(screen.getByText('Select a Bedrock Knowledge Base')).toBeInTheDocument();
    });

    it('shows Knowledge Base ID in edit mode', () => {
        const editProps = {
            ...defaultProps,
            isEdit: true,
            item: {
                bedrockKnowledgeBaseConfig: {
                    bedrockKnowledgeBaseId: 'KB123456',
                    bedrockKnowledgeBaseName: 'Test KB',
                    dataSources: [],
                },
            },
        };

        render(<BedrockKnowledgeBaseConfigForm {...editProps} />);

        expect(screen.getByText('Knowledge Base ID')).toBeInTheDocument();
        expect(screen.getByText('Knowledge Base cannot be changed after creation')).toBeInTheDocument();
    });

    it('renders without errors when no form errors provided', () => {
        render(<BedrockKnowledgeBaseConfigForm {...defaultProps} />);

        expect(screen.getByText('How LISA manages your Knowledge Base documents')).toBeInTheDocument();
    });
});

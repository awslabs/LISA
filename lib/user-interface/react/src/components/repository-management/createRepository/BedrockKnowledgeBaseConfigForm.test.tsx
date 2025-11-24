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
import { describe, it, expect, vi } from 'vitest';
import { BedrockKnowledgeBaseConfigForm } from './BedrockKnowledgeBaseConfigForm';
import { BedrockKnowledgeBaseInstanceConfig } from '#root/lib/schema';
import { getDefaults } from '#root/lib/schema/zodUtil';

describe('BedrockKnowledgeBaseConfigForm', () => {
    const mockSetFields = vi.fn();
    const mockTouchFields = vi.fn();

    const defaultProps = {
        item: getDefaults(BedrockKnowledgeBaseInstanceConfig),
        setFields: mockSetFields,
        touchFields: mockTouchFields,
        formErrors: {},
        isEdit: false,
    };

    it('renders the informational alert about document management', () => {
        render(<BedrockKnowledgeBaseConfigForm {...defaultProps} />);

        expect(screen.getByText('How LISA manages your Knowledge Base documents')).toBeInTheDocument();
        expect(screen.getByText(/LISA tracks document ownership to preserve your existing data/)).toBeInTheDocument();
        expect(screen.getByText(/Documents already in your Knowledge Base are marked as user-managed/)).toBeInTheDocument();
        expect(screen.getByText(/Only documents uploaded through LISA/)).toBeInTheDocument();
    });

    it('renders all required form fields', () => {
        render(<BedrockKnowledgeBaseConfigForm {...defaultProps} />);

        expect(screen.getByLabelText('Knowledge Base Name')).toBeInTheDocument();
        expect(screen.getByLabelText('Knowledge Base ID')).toBeInTheDocument();
        expect(screen.getByLabelText('Knowledge Base Datasource Name')).toBeInTheDocument();
        expect(screen.getByLabelText('Knowledge Base Datasource ID')).toBeInTheDocument();
        expect(screen.getByLabelText('Knowledge Base Datasource S3 Bucket')).toBeInTheDocument();
    });

    it('disables fields when in edit mode', () => {
        render(<BedrockKnowledgeBaseConfigForm {...defaultProps} isEdit={true} />);

        expect(screen.getByLabelText('Knowledge Base Name')).toBeDisabled();
        expect(screen.getByLabelText('Knowledge Base ID')).toBeDisabled();
        expect(screen.getByLabelText('Knowledge Base Datasource Name')).toBeDisabled();
        expect(screen.getByLabelText('Knowledge Base Datasource ID')).toBeDisabled();
        expect(screen.getByLabelText('Knowledge Base Datasource S3 Bucket')).toBeDisabled();
    });

    it('displays form errors when provided', () => {
        const formErrors = {
            bedrockKnowledgeBaseConfig: {
                bedrockKnowledgeBaseId: 'Knowledge Base ID is required',
            },
        };

        render(<BedrockKnowledgeBaseConfigForm {...defaultProps} formErrors={formErrors} />);

        expect(screen.getByText('Knowledge Base ID is required')).toBeInTheDocument();
    });
});

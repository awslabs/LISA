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
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { ChunkingStepForm } from './ChunkingStepForm';
import { ChunkingStrategyType } from '#root/lib/schema';

describe('ChunkingStepForm', () => {
    const defaultProps = {
        chunkingStrategy: {
            type: ChunkingStrategyType.FIXED,
            size: 512,
            overlap: 51,
        },
        metadata: { tags: ['test-tag'] },
        allowChunkingOverride: true,
        setFields: vi.fn(),
        touchFields: vi.fn(),
        formErrors: {},
        disabled: false,
    };

    it('renders all form sections', () => {
        render(<ChunkingStepForm {...defaultProps} />);

        // Check that chunking configuration is rendered
        expect(screen.getByText('Chunking Type')).toBeInTheDocument();

        // Check that metadata form (tags input) is rendered
        expect(screen.getByText('Tags (optional)')).toBeInTheDocument();

        // Check that allow chunking override checkbox is rendered
        expect(screen.getByText('Allow Chunking Override')).toBeInTheDocument();
        expect(screen.getByRole('checkbox')).toBeInTheDocument();
    });

    it('handles chunking override checkbox interaction', async () => {
        const user = userEvent.setup();
        const mockSetFields = vi.fn();

        render(<ChunkingStepForm {...defaultProps} setFields={mockSetFields} />);

        const checkbox = screen.getByRole('checkbox');
        await user.click(checkbox);

        expect(mockSetFields).toHaveBeenCalledWith({
            allowChunkingOverride: false
        });
    });

    it('respects disabled state', () => {
        render(<ChunkingStepForm {...defaultProps} disabled={true} />);

        const checkbox = screen.getByRole('checkbox');
        expect(checkbox).toBeDisabled();
    });

    it('displays form errors', () => {
        const formErrors = {
            allowChunkingOverride: 'Override setting is required'
        };

        render(<ChunkingStepForm {...defaultProps} formErrors={formErrors} />);

        expect(screen.getByText('Override setting is required')).toBeInTheDocument();
    });
});

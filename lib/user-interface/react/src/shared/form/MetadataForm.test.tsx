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
import { MetadataForm } from './MetadataForm';

describe('MetadataForm', () => {
    const defaultProps = {
        tags: ['tag1', 'tag2'],
        onTagsChange: vi.fn(),
    };

    it('renders tags input without header by default', () => {
        render(<MetadataForm {...defaultProps} />);

        expect(screen.getByText('Tags (optional)')).toBeInTheDocument();
        expect(screen.queryByText('Metadata')).not.toBeInTheDocument();
    });

    it('renders with header when showHeader is true', () => {
        render(<MetadataForm {...defaultProps} showHeader={true} />);

        expect(screen.getByText('Metadata')).toBeInTheDocument();
        expect(screen.getByText('Tags (optional)')).toBeInTheDocument();
    });

    it('uses custom header text and description', () => {
        render(
            <MetadataForm
                {...defaultProps}
                showHeader={true}
                headerText='Custom Metadata'
                headerDescription='Custom description'
            />
        );

        expect(screen.getByText('Custom Metadata')).toBeInTheDocument();
        expect(screen.getByText('Custom description')).toBeInTheDocument();
    });

    it('uses custom tags label and description', () => {
        render(
            <MetadataForm
                {...defaultProps}
                tagsLabel='Custom Tags'
                tagsDescription='Custom tags description'
            />
        );

        expect(screen.getByText('Custom Tags')).toBeInTheDocument();
        expect(screen.getByText('Custom tags description')).toBeInTheDocument();
    });

    it('handles tags change', async () => {
        const user = userEvent.setup();
        const mockOnTagsChange = vi.fn();

        render(<MetadataForm {...defaultProps} onTagsChange={mockOnTagsChange} />);

        const input = screen.getByRole('textbox');
        await user.type(input, 'new-tag{enter}');

        expect(mockOnTagsChange).toHaveBeenCalled();
    });

    it('respects disabled state', () => {
        render(<MetadataForm {...defaultProps} disabled={true} />);

        const input = screen.getByRole('textbox');
        expect(input).toBeDisabled();
    });

    it('displays error text', () => {
        render(<MetadataForm {...defaultProps} errorText='Tags are required' />);

        expect(screen.getByText('Tags are required')).toBeInTheDocument();
    });
});

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
import { RepositoryMetadataForm } from './RepositoryMetadataForm';

describe('RepositoryMetadataForm', () => {
    const defaultProps = {
        item: { tags: [] },
        setFields: vi.fn(),
        touchFields: vi.fn(),
        formErrors: {},
    };

    it('renders metadata form with tags input', () => {
        render(<RepositoryMetadataForm {...defaultProps} />);

        expect(screen.getByText('Repository Metadata')).toBeInTheDocument();
        expect(screen.getByText('Tags (optional)')).toBeInTheDocument();
        expect(screen.getByPlaceholderText('Add tag')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Add' })).toBeInTheDocument();
    });

    it('displays existing tags', () => {
        const propsWithTags = {
            ...defaultProps,
            item: { tags: ['production', 'ml-team'] },
        };

        render(<RepositoryMetadataForm {...propsWithTags} />);

        expect(screen.getByText('production')).toBeInTheDocument();
        expect(screen.getByText('ml-team')).toBeInTheDocument();
    });

    it('calls setFields when adding a new tag', async () => {
        const user = userEvent.setup();
        const mockSetFields = vi.fn();

        render(<RepositoryMetadataForm {...defaultProps} setFields={mockSetFields} />);

        const input = screen.getByPlaceholderText('Add tag');
        const addButton = screen.getByText('Add');

        await user.type(input, 'new-tag');
        await user.click(addButton);

        expect(mockSetFields).toHaveBeenCalledWith({ 'metadata.tags': ['new-tag'] });
    });

    it('handles empty metadata gracefully', () => {
        const propsWithoutMetadata = {
            ...defaultProps,
            item: undefined,
        };

        render(<RepositoryMetadataForm {...propsWithoutMetadata} />);

        expect(screen.getByText('Repository Metadata')).toBeInTheDocument();
        expect(screen.getByPlaceholderText('Add tag')).toBeInTheDocument();
    });

    it('disables input when disabled prop is true', () => {
        render(<RepositoryMetadataForm {...defaultProps} disabled={true} />);

        const input = screen.getByPlaceholderText('Add tag');
        expect(input).toBeDisabled();
    });

    it('displays error text when provided', () => {
        const propsWithError = {
            ...defaultProps,
            formErrors: { tags: 'Too many tags' },
        };

        render(<RepositoryMetadataForm {...propsWithError} />);

        expect(screen.getByText('Too many tags')).toBeInTheDocument();
    });
});

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
import { TagsInput } from './TagsInput';

describe('TagsInput', () => {
    it('renders with empty values', () => {
        const onChange = vi.fn();
        render(
            <TagsInput
                label='Tags'
                values={[]}
                onChange={onChange}
            />
        );

        expect(screen.getByPlaceholderText('Enter tag')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Add' })).toBeInTheDocument();
    });

    it('displays existing tag values as tokens', () => {
        const onChange = vi.fn();
        render(
            <TagsInput
                label='Tags'
                values={['production', 'important']}
                onChange={onChange}
            />
        );

        expect(screen.getByText('production')).toBeInTheDocument();
        expect(screen.getByText('important')).toBeInTheDocument();
    });

    it('adds a new tag when Add button is clicked', async () => {
        const user = userEvent.setup();
        const onChange = vi.fn();
        render(
            <TagsInput
                label='Tags'
                values={[]}
                onChange={onChange}
            />
        );

        const input = screen.getByPlaceholderText('Enter tag');
        await user.type(input, 'new-tag');
        await user.click(screen.getByRole('button', { name: 'Add' }));

        expect(onChange).toHaveBeenCalledWith(['new-tag']);
    });

    it('adds a new tag when Enter key is pressed', async () => {
        const user = userEvent.setup();
        const onChange = vi.fn();
        render(
            <TagsInput
                label='Tags'
                values={[]}
                onChange={onChange}
            />
        );

        const input = screen.getByPlaceholderText('Enter tag');
        await user.type(input, 'new-tag{Enter}');

        expect(onChange).toHaveBeenCalledWith(['new-tag']);
    });

    it('clears input after adding a tag', async () => {
        const user = userEvent.setup();
        const onChange = vi.fn();
        render(
            <TagsInput
                label='Tags'
                values={[]}
                onChange={onChange}
            />
        );

        const input = screen.getByPlaceholderText('Enter tag');
        await user.type(input, 'new-tag');
        await user.click(screen.getByRole('button', { name: 'Add' }));

        expect(input).toHaveValue('');
    });

    it('does not add duplicate tags', async () => {
        const user = userEvent.setup();
        const onChange = vi.fn();
        render(
            <TagsInput
                label='Tags'
                values={['production']}
                onChange={onChange}
            />
        );

        const input = screen.getByPlaceholderText('Enter tag');
        await user.type(input, 'production');
        await user.click(screen.getByRole('button', { name: 'Add' }));

        expect(onChange).not.toHaveBeenCalled();
    });

    it('does not add empty or whitespace-only tags', async () => {
        const user = userEvent.setup();
        const onChange = vi.fn();
        render(
            <TagsInput
                label='Tags'
                values={[]}
                onChange={onChange}
            />
        );

        const input = screen.getByPlaceholderText('Enter tag');
        await user.type(input, '   ');
        await user.click(screen.getByRole('button', { name: 'Add' }));

        expect(onChange).not.toHaveBeenCalled();
    });

    it('trims whitespace from tag names', async () => {
        const user = userEvent.setup();
        const onChange = vi.fn();
        render(
            <TagsInput
                label='Tags'
                values={[]}
                onChange={onChange}
            />
        );

        const input = screen.getByPlaceholderText('Enter tag');
        await user.type(input, '  new-tag  ');
        await user.click(screen.getByRole('button', { name: 'Add' }));

        expect(onChange).toHaveBeenCalledWith(['new-tag']);
    });

    it('removes a tag when dismiss button is clicked', async () => {
        const user = userEvent.setup();
        const onChange = vi.fn();
        render(
            <TagsInput
                label='Tags'
                values={['production', 'staging']}
                onChange={onChange}
            />
        );

        const removeButton = screen.getByLabelText('Remove production');
        await user.click(removeButton);

        expect(onChange).toHaveBeenCalledWith(['staging']);
    });

    it('uses custom placeholder when provided', () => {
        const onChange = vi.fn();
        render(
            <TagsInput
                label='Tags'
                values={[]}
                onChange={onChange}
                placeholder='Custom placeholder'
            />
        );

        expect(screen.getByPlaceholderText('Custom placeholder')).toBeInTheDocument();
    });

    it('displays error text when provided', () => {
        const onChange = vi.fn();
        render(
            <TagsInput
                label='Tags'
                values={[]}
                onChange={onChange}
                errorText='This field is required'
            />
        );

        expect(screen.getByText('This field is required')).toBeInTheDocument();
    });

    it('displays description when provided', () => {
        const onChange = vi.fn();
        render(
            <TagsInput
                label='Tags'
                values={[]}
                onChange={onChange}
                description='Add tags to organize content'
            />
        );

        expect(screen.getByText('Add tags to organize content')).toBeInTheDocument();
    });
});

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
import { UserGroupsInput } from './UserGroupsInput';

describe('UserGroupsInput', () => {
    it('renders with empty values', () => {
        const onChange = vi.fn();
        render(
            <UserGroupsInput
                label='Allowed Groups'
                values={[]}
                onChange={onChange}
            />
        );

        expect(screen.getByPlaceholderText('Enter group name')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Add' })).toBeInTheDocument();
    });

    it('displays existing group values as tokens', () => {
        const onChange = vi.fn();
        render(
            <UserGroupsInput
                label='Allowed Groups'
                values={['admin', 'developers']}
                onChange={onChange}
            />
        );

        expect(screen.getByText('admin')).toBeInTheDocument();
        expect(screen.getByText('developers')).toBeInTheDocument();
    });

    it('adds a new group when Add button is clicked', async () => {
        const user = userEvent.setup();
        const onChange = vi.fn();
        render(
            <UserGroupsInput
                label='Allowed Groups'
                values={[]}
                onChange={onChange}
            />
        );

        const input = screen.getByPlaceholderText('Enter group name');
        await user.type(input, 'new-group');
        await user.click(screen.getByRole('button', { name: 'Add' }));

        expect(onChange).toHaveBeenCalledWith(['new-group']);
    });

    it('adds a new group when Enter key is pressed', async () => {
        const user = userEvent.setup();
        const onChange = vi.fn();
        render(
            <UserGroupsInput
                label='Allowed Groups'
                values={[]}
                onChange={onChange}
            />
        );

        const input = screen.getByPlaceholderText('Enter group name');
        await user.type(input, 'new-group{Enter}');

        expect(onChange).toHaveBeenCalledWith(['new-group']);
    });

    it('clears input after adding a group', async () => {
        const user = userEvent.setup();
        const onChange = vi.fn();
        render(
            <UserGroupsInput
                label='Allowed Groups'
                values={[]}
                onChange={onChange}
            />
        );

        const input = screen.getByPlaceholderText('Enter group name');
        await user.type(input, 'new-group');
        await user.click(screen.getByRole('button', { name: 'Add' }));

        expect(input).toHaveValue('');
    });

    it('does not add duplicate groups', async () => {
        const user = userEvent.setup();
        const onChange = vi.fn();
        render(
            <UserGroupsInput
                label='Allowed Groups'
                values={['admin']}
                onChange={onChange}
            />
        );

        const input = screen.getByPlaceholderText('Enter group name');
        await user.type(input, 'admin');
        await user.click(screen.getByRole('button', { name: 'Add' }));

        expect(onChange).not.toHaveBeenCalled();
    });

    it('does not add empty or whitespace-only groups', async () => {
        const user = userEvent.setup();
        const onChange = vi.fn();
        render(
            <UserGroupsInput
                label='Allowed Groups'
                values={[]}
                onChange={onChange}
            />
        );

        const input = screen.getByPlaceholderText('Enter group name');
        await user.type(input, '   ');
        await user.click(screen.getByRole('button', { name: 'Add' }));

        expect(onChange).not.toHaveBeenCalled();
    });

    it('trims whitespace from group names', async () => {
        const user = userEvent.setup();
        const onChange = vi.fn();
        render(
            <UserGroupsInput
                label='Allowed Groups'
                values={[]}
                onChange={onChange}
            />
        );

        const input = screen.getByPlaceholderText('Enter group name');
        await user.type(input, '  new-group  ');
        await user.click(screen.getByRole('button', { name: 'Add' }));

        expect(onChange).toHaveBeenCalledWith(['new-group']);
    });

    it('removes a group when dismiss button is clicked', async () => {
        const user = userEvent.setup();
        const onChange = vi.fn();
        render(
            <UserGroupsInput
                label='Allowed Groups'
                values={['admin', 'developers']}
                onChange={onChange}
            />
        );

        const removeButton = screen.getByLabelText('Remove admin');
        await user.click(removeButton);

        expect(onChange).toHaveBeenCalledWith(['developers']);
    });

    it('uses custom placeholder when provided', () => {
        const onChange = vi.fn();
        render(
            <UserGroupsInput
                label='Allowed Groups'
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
            <UserGroupsInput
                label='Allowed Groups'
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
            <UserGroupsInput
                label='Allowed Groups'
                values={[]}
                onChange={onChange}
                description='Add groups to restrict access'
            />
        );

        expect(screen.getByText('Add groups to restrict access')).toBeInTheDocument();
    });
});

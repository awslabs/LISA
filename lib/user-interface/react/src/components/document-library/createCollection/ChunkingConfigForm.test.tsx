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
import { ChunkingConfigForm } from './ChunkingConfigForm';
import { ChunkingStrategyType } from '#root/lib/schema';

describe('ChunkingConfigForm', () => {
    const mockSetFields = vi.fn();
    const mockTouchFields = vi.fn();

    beforeEach(() => {
        mockSetFields.mockClear();
        mockTouchFields.mockClear();
    });

    describe('Dropdown Options', () => {
        it('displays FIXED and NONE options in dropdown', async () => {
            const user = userEvent.setup();

            render(
                <ChunkingConfigForm
                    item={undefined}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={{}}
                />
            );

            // Click the dropdown to open it (find by the combobox role)
            const dropdown = screen.getByRole('button', { name: /chunking type/i });
            await user.click(dropdown);

            // Verify both options are present using getAllByText since they appear multiple times
            const fixedOptions = screen.getAllByText('Fixed Size');
            const noneOptions = screen.getAllByText('None (No Chunking)');

            expect(fixedOptions.length).toBeGreaterThan(0);
            expect(noneOptions.length).toBeGreaterThan(0);
        });
    });

    describe('FIXED Strategy Selection', () => {
        it('shows size and overlap fields when FIXED is selected', () => {
            render(
                <ChunkingConfigForm
                    item={{ type: ChunkingStrategyType.FIXED, size: 512, overlap: 51 }}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={{}}
                />
            );

            // Verify size and overlap fields are visible
            expect(screen.getByLabelText(/chunk size/i)).toBeInTheDocument();
            expect(screen.getByLabelText(/chunk overlap/i)).toBeInTheDocument();
        });

        it('displays correct values for FIXED strategy', () => {
            render(
                <ChunkingConfigForm
                    item={{ type: ChunkingStrategyType.FIXED, size: 1024, overlap: 100 }}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={{}}
                />
            );

            const sizeInput = screen.getByLabelText(/chunk size/i) as HTMLInputElement;
            const overlapInput = screen.getByLabelText(/chunk overlap/i) as HTMLInputElement;

            expect(sizeInput.value).toBe('1024');
            expect(overlapInput.value).toBe('100');
        });

        it('calls setFields when size is changed', async () => {
            const user = userEvent.setup();

            render(
                <ChunkingConfigForm
                    item={{ type: ChunkingStrategyType.FIXED, size: 512, overlap: 51 }}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={{}}
                />
            );

            const sizeInput = screen.getByLabelText(/chunk size/i);

            // Type directly without clearing (which triggers onChange for each character)
            await user.click(sizeInput);
            await user.keyboard('{Control>}a{/Control}'); // Select all
            await user.keyboard('1024');

            // Verify setFields was called (it will be called multiple times during typing)
            expect(mockSetFields).toHaveBeenCalled();

            // Verify at least one call contains the size field
            const calls = mockSetFields.mock.calls;
            const hasSizeCall = calls.some((call) =>
                call[0] && typeof call[0]['chunkingStrategy.size'] === 'number'
            );
            expect(hasSizeCall).toBe(true);
        });

        it('calls setFields when overlap is changed', async () => {
            const user = userEvent.setup();

            render(
                <ChunkingConfigForm
                    item={{ type: ChunkingStrategyType.FIXED, size: 512, overlap: 51 }}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={{}}
                />
            );

            const overlapInput = screen.getByLabelText(/chunk overlap/i);

            // Type directly without clearing (which triggers onChange for each character)
            await user.click(overlapInput);
            await user.keyboard('{Control>}a{/Control}'); // Select all
            await user.keyboard('100');

            // Verify setFields was called (it will be called multiple times during typing)
            expect(mockSetFields).toHaveBeenCalled();

            // Verify at least one call contains the overlap field
            const calls = mockSetFields.mock.calls;
            const hasOverlapCall = calls.some((call) =>
                call[0] && typeof call[0]['chunkingStrategy.overlap'] === 'number'
            );
            expect(hasOverlapCall).toBe(true);
        });
    });

    describe('NONE Strategy Selection', () => {
        it('hides size and overlap fields when NONE is selected', () => {
            render(
                <ChunkingConfigForm
                    item={{ type: ChunkingStrategyType.NONE }}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={{}}
                />
            );

            // Verify size and overlap fields are NOT visible
            expect(screen.queryByLabelText(/chunk size/i)).not.toBeInTheDocument();
            expect(screen.queryByLabelText(/chunk overlap/i)).not.toBeInTheDocument();
        });

        it('displays NONE as selected option', () => {
            render(
                <ChunkingConfigForm
                    item={{ type: ChunkingStrategyType.NONE }}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={{}}
                />
            );

            // The selected option should show "None (No Chunking)"
            expect(screen.getByText('None (No Chunking)')).toBeInTheDocument();
        });

        it('calls setFields with NONE strategy when NONE is selected', async () => {
            const user = userEvent.setup();

            render(
                <ChunkingConfigForm
                    item={{ type: ChunkingStrategyType.FIXED, size: 512, overlap: 51 }}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={{}}
                />
            );

            // Click dropdown and select NONE
            const dropdown = screen.getByRole('button', { name: /chunking type/i });
            await user.click(dropdown);

            const noneOption = screen.getByText('None (No Chunking)');
            await user.click(noneOption);

            expect(mockSetFields).toHaveBeenCalledWith({
                chunkingStrategy: { type: ChunkingStrategyType.NONE }
            });
        });
    });

    describe('Strategy Switching', () => {
        it('switches from FIXED to NONE and hides fields', async () => {
            const { rerender } = render(
                <ChunkingConfigForm
                    item={{ type: ChunkingStrategyType.FIXED, size: 512, overlap: 51 }}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={{}}
                />
            );

            // Verify FIXED fields are visible
            expect(screen.getByLabelText(/chunk size/i)).toBeInTheDocument();

            // Switch to NONE
            rerender(
                <ChunkingConfigForm
                    item={{ type: ChunkingStrategyType.NONE }}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={{}}
                />
            );

            // Verify fields are hidden
            expect(screen.queryByLabelText(/chunk size/i)).not.toBeInTheDocument();
            expect(screen.queryByLabelText(/chunk overlap/i)).not.toBeInTheDocument();
        });

        it('switches from NONE to FIXED and shows fields', async () => {
            const { rerender } = render(
                <ChunkingConfigForm
                    item={{ type: ChunkingStrategyType.NONE }}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={{}}
                />
            );

            // Verify fields are hidden
            expect(screen.queryByLabelText(/chunk size/i)).not.toBeInTheDocument();

            // Switch to FIXED
            rerender(
                <ChunkingConfigForm
                    item={{ type: ChunkingStrategyType.FIXED, size: 512, overlap: 51 }}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={{}}
                />
            );

            // Verify fields are visible
            expect(screen.getByLabelText(/chunk size/i)).toBeInTheDocument();
            expect(screen.getByLabelText(/chunk overlap/i)).toBeInTheDocument();
        });

        it('calls setFields with default FIXED values when switching to FIXED', async () => {
            const user = userEvent.setup();

            render(
                <ChunkingConfigForm
                    item={{ type: ChunkingStrategyType.NONE }}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={{}}
                />
            );

            // Click dropdown and select FIXED
            const dropdown = screen.getByRole('button', { name: /chunking type/i });
            await user.click(dropdown);

            const fixedOption = screen.getByText('Fixed Size');
            await user.click(fixedOption);

            expect(mockSetFields).toHaveBeenCalledWith({
                chunkingStrategy: {
                    type: ChunkingStrategyType.FIXED,
                    size: 512,
                    overlap: 51
                }
            });
        });
    });

    describe('Form Validation', () => {
        it('displays error for size field', () => {
            render(
                <ChunkingConfigForm
                    item={{ type: ChunkingStrategyType.FIXED, size: 512, overlap: 51 }}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={{ 'chunkingStrategy.size': 'Size must be between 100 and 10000' }}
                />
            );

            expect(screen.getByText('Size must be between 100 and 10000')).toBeInTheDocument();
        });

        it('displays error for overlap field', () => {
            render(
                <ChunkingConfigForm
                    item={{ type: ChunkingStrategyType.FIXED, size: 512, overlap: 51 }}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={{ 'chunkingStrategy.overlap': 'Overlap must be less than size/2' }}
                />
            );

            expect(screen.getByText('Overlap must be less than size/2')).toBeInTheDocument();
        });

        it('calls touchFields when size input loses focus', async () => {
            const user = userEvent.setup();

            render(
                <ChunkingConfigForm
                    item={{ type: ChunkingStrategyType.FIXED, size: 512, overlap: 51 }}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={{}}
                />
            );

            const sizeInput = screen.getByLabelText(/chunk size/i);
            await user.click(sizeInput);
            await user.tab(); // Blur the input

            expect(mockTouchFields).toHaveBeenCalledWith(['chunkingStrategy.size']);
        });

        it('calls touchFields when overlap input loses focus', async () => {
            const user = userEvent.setup();

            render(
                <ChunkingConfigForm
                    item={{ type: ChunkingStrategyType.FIXED, size: 512, overlap: 51 }}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={{}}
                />
            );

            const overlapInput = screen.getByLabelText(/chunk overlap/i);
            await user.click(overlapInput);
            await user.tab(); // Blur the input

            expect(mockTouchFields).toHaveBeenCalledWith(['chunkingStrategy.overlap']);
        });
    });

    describe('Default Behavior', () => {
        it('defaults to FIXED strategy when item is undefined', () => {
            render(
                <ChunkingConfigForm
                    item={undefined}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={{}}
                />
            );

            // Should show "Fixed Size" as selected
            expect(screen.getByText('Fixed Size')).toBeInTheDocument();
        });
    });
});

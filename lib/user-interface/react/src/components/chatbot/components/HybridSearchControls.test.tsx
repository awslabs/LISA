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
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import HybridSearchControls, { HybridSearchControlsProps } from './HybridSearchControls';

function renderControls (overrides: Partial<HybridSearchControlsProps> = {}) {
    const defaultProps: HybridSearchControlsProps = {
        vectorWeight: 0.7,
        lexicalWeight: 0.3,
        onChange: vi.fn(),
        disabled: false,
        ...overrides,
    };
    const result = render(<HybridSearchControls {...defaultProps} />);
    return { ...result, props: defaultProps };
}

describe('HybridSearchControls', () => {
    describe('rendering', () => {
        it('renders vector slider and input with initial value', () => {
            const { container } = renderControls({ vectorWeight: 0.7, lexicalWeight: 0.3 });
            const vectorSlider = screen.getByRole('slider', { name: /vector weight/i });
            expect(vectorSlider).toBeInTheDocument();
            const numberInputs = container.querySelectorAll('input[type="number"]');
            expect(numberInputs[0]).toHaveValue(0.7);
        });

        it('renders lexical slider and input with complementary value', () => {
            const { container } = renderControls({ vectorWeight: 0.7, lexicalWeight: 0.3 });
            const lexicalSlider = screen.getByRole('slider', { name: /lexical weight/i });
            expect(lexicalSlider).toBeInTheDocument();
            const numberInputs = container.querySelectorAll('input[type="number"]');
            expect(numberInputs[1]).toHaveValue(0.3);
        });
    });

    describe('slider linkage (sum-to-1 invariant)', () => {
        it('calls onChange with complementary weights when vector slider changes', () => {
            const onChange = vi.fn();
            renderControls({ vectorWeight: 0.7, lexicalWeight: 0.3, onChange });
            const vectorSlider = screen.getByRole('slider', { name: /vector weight/i });
            fireEvent.change(vectorSlider, { target: { value: '0.6' } });
            expect(onChange).toHaveBeenCalledWith({ vectorWeight: 0.6, lexicalWeight: 0.4 });
        });

        it('calls onChange with complementary weights when lexical slider changes', () => {
            const onChange = vi.fn();
            renderControls({ vectorWeight: 0.7, lexicalWeight: 0.3, onChange });
            const lexicalSlider = screen.getByRole('slider', { name: /lexical weight/i });
            fireEvent.change(lexicalSlider, { target: { value: '0.5' } });
            expect(onChange).toHaveBeenCalledWith({ vectorWeight: 0.5, lexicalWeight: 0.5 });
        });

        it('clamps vector weight to 0-1 range', () => {
            const onChange = vi.fn();
            renderControls({ vectorWeight: 0.7, lexicalWeight: 0.3, onChange });
            const vectorSlider = screen.getByRole('slider', { name: /vector weight/i });
            fireEvent.change(vectorSlider, { target: { value: '1' } });
            expect(onChange).toHaveBeenCalledWith({ vectorWeight: 1.0, lexicalWeight: 0.0 });
        });
    });

    describe('input fields', () => {
        it('calls onChange when vector input value is changed', () => {
            const onChange = vi.fn();
            const { container } = renderControls({ vectorWeight: 0.7, lexicalWeight: 0.3, onChange });
            const vectorInput = container.querySelectorAll('input[type="number"]')[0];
            fireEvent.change(vectorInput, { target: { value: '0.6' } });
            expect(onChange).toHaveBeenCalledWith({ vectorWeight: 0.6, lexicalWeight: 0.4 });
        });

        it('rejects invalid input values outside 0-1 range', async () => {
            const user = userEvent.setup();
            const onChange = vi.fn();
            const { container } = renderControls({ vectorWeight: 0.7, lexicalWeight: 0.3, onChange });
            const vectorInput = container.querySelectorAll('input[type="number"]')[0];
            await user.clear(vectorInput);
            await user.type(vectorInput, '1.5');
            const outOfRangeCall = onChange.mock.calls.find(
                (call) => call[0].vectorWeight > 1 || call[0].vectorWeight < 0
            );
            expect(outOfRangeCall).toBeUndefined();
        });
    });

    describe('preset buttons', () => {
        it('clicking "Balanced" sets 0.5/0.5', async () => {
            const user = userEvent.setup();
            const onChange = vi.fn();
            renderControls({ vectorWeight: 0.7, lexicalWeight: 0.3, onChange });
            await user.click(screen.getByRole('button', { name: /balanced/i }));
            expect(onChange).toHaveBeenCalledWith({ vectorWeight: 0.5, lexicalWeight: 0.5 });
        });

        it('clicking "Semantic-heavy" sets 0.8/0.2', async () => {
            const user = userEvent.setup();
            const onChange = vi.fn();
            renderControls({ vectorWeight: 0.7, lexicalWeight: 0.3, onChange });
            await user.click(screen.getByRole('button', { name: /semantic/i }));
            expect(onChange).toHaveBeenCalledWith({ vectorWeight: 0.8, lexicalWeight: 0.2 });
        });

        it('clicking "Lexical-heavy" sets 0.3/0.7', async () => {
            const user = userEvent.setup();
            const onChange = vi.fn();
            renderControls({ vectorWeight: 0.7, lexicalWeight: 0.3, onChange });
            await user.click(screen.getByRole('button', { name: /lexical/i }));
            expect(onChange).toHaveBeenCalledWith({ vectorWeight: 0.3, lexicalWeight: 0.7 });
        });
    });

    describe('disabled state', () => {
        it('disables sliders, inputs, and preset buttons when disabled prop is true', () => {
            const { container } = renderControls({ disabled: true });
            const vectorSlider = screen.getByRole('slider', { name: /vector weight/i });
            const lexicalSlider = screen.getByRole('slider', { name: /lexical weight/i });
            expect(vectorSlider).toBeDisabled();
            expect(lexicalSlider).toBeDisabled();
            const numberInputs = container.querySelectorAll('input[type="number"]');
            numberInputs.forEach((input) => expect(input).toBeDisabled());
            screen.getAllByRole('button').forEach((button) => {
                expect(button).toBeDisabled();
            });
        });
    });
});

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
import { EmbeddingModelInput } from './EmbeddingModelInput';

// Mock the model management reducer
vi.mock('../reducers/model-management.reducer', () => ({
    useGetAllModelsQuery: vi.fn(() => ({
        data: [
            {
                modelId: 'embedding-model-1',
                modelName: 'Test Embedding Model 1',
                modelType: 'embedding',
                status: 'InService'
            },
            {
                modelId: 'embedding-model-2',
                modelName: 'Test Embedding Model 2',
                modelType: 'embedding',
                status: 'InService'
            }
        ],
        isFetching: false
    }))
}));

describe('EmbeddingModelInput', () => {
    const defaultProps = {
        value: '',
        onChange: vi.fn(),
    };

    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('renders with default label and description', () => {
        render(<EmbeddingModelInput {...defaultProps} />);

        expect(screen.getByText('Embedding model')).toBeInTheDocument();
        expect(screen.getByText('The model used to generate vector embeddings for documents')).toBeInTheDocument();
    });

    it('renders with custom label and description', () => {
        render(
            <EmbeddingModelInput
                {...defaultProps}
                label='Custom Model'
                description='Custom description'
            />
        );

        expect(screen.getByText('Custom Model')).toBeInTheDocument();
        expect(screen.getByText('Custom description')).toBeInTheDocument();
    });

    it('displays the current value', () => {
        render(<EmbeddingModelInput {...defaultProps} value='test-model-id' />);

        const input = screen.getByRole('combobox');
        expect(input).toHaveValue('test-model-id');
    });

    it('calls onChange when value changes', async () => {
        const user = userEvent.setup();
        const mockOnChange = vi.fn();

        render(<EmbeddingModelInput {...defaultProps} onChange={mockOnChange} />);

        const input = screen.getByRole('combobox');
        await user.type(input, 'new-model');

        expect(mockOnChange).toHaveBeenCalled();
    });

    it('calls onBlur when input loses focus', async () => {
        const user = userEvent.setup();
        const mockOnBlur = vi.fn();

        render(<EmbeddingModelInput {...defaultProps} onBlur={mockOnBlur} />);

        const input = screen.getByRole('combobox');
        await user.click(input);
        await user.tab();

        expect(mockOnBlur).toHaveBeenCalled();
    });

    it('displays error text', () => {
        render(<EmbeddingModelInput {...defaultProps} errorText='Model is required' />);

        expect(screen.getByText('Model is required')).toBeInTheDocument();
    });

    it('respects disabled state', () => {
        render(<EmbeddingModelInput {...defaultProps} disabled={true} />);

        const input = screen.getByRole('combobox');
        expect(input).toBeDisabled();
    });

    it('uses custom placeholder', () => {
        render(<EmbeddingModelInput {...defaultProps} placeholder='Choose a model' />);

        expect(screen.getByPlaceholderText('Choose a model')).toBeInTheDocument();
    });
});

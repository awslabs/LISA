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

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CommonFieldsForm } from './CommonFieldsForm';
import { renderWithProviders, createMockQueryHook } from '../../test/helpers/render';
import * as modelManagementReducer from '../reducers/model-management.reducer';
import { ModelStatus, ModelType } from '../model/model-management.model';

describe('CommonFieldsForm', () => {
    const mockSetFields = vi.fn();
    const mockTouchFields = vi.fn();
    const mockFormErrors = {};

    const mockEmbeddingModels = [
        {
            modelId: 'model-1',
            modelName: 'Embedding Model 1',
            modelType: ModelType.embedding,
            status: ModelStatus.InService,
        },
        {
            modelId: 'model-2',
            modelName: 'Embedding Model 2',
            modelType: ModelType.embedding,
            status: ModelStatus.InService,
        },
    ];

    const mockItem = {
        embeddingModel: '',
        allowedGroups: [],
    };

    beforeEach(() => {
        vi.clearAllMocks();

        vi.spyOn(modelManagementReducer, 'useGetAllModelsQuery').mockImplementation(
            createMockQueryHook(mockEmbeddingModels) as any
        );
    });

    describe('Rendering', () => {
        it('should render embedding model field when showEmbeddingModel is true', () => {
            renderWithProviders(
                <CommonFieldsForm
                    item={mockItem}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={mockFormErrors}
                    showEmbeddingModel={true}
                    showAllowedGroups={false}
                />
            );

            expect(screen.getByText('Embedding Model')).toBeInTheDocument();
            expect(screen.getByPlaceholderText('Select an embedding model')).toBeInTheDocument();
        });

        it('should not render embedding model field when showEmbeddingModel is false', () => {
            renderWithProviders(
                <CommonFieldsForm
                    item={mockItem}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={mockFormErrors}
                    showEmbeddingModel={false}
                    showAllowedGroups={false}
                />
            );

            expect(screen.queryByText('Embedding Model')).not.toBeInTheDocument();
        });

        it('should render allowed groups field when showAllowedGroups is true', () => {
            renderWithProviders(
                <CommonFieldsForm
                    item={mockItem}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={mockFormErrors}
                    showEmbeddingModel={false}
                    showAllowedGroups={true}
                />
            );

            expect(screen.getByText('Allowed Groups')).toBeInTheDocument();
        });

        it('should not render allowed groups field when showAllowedGroups is false', () => {
            renderWithProviders(
                <CommonFieldsForm
                    item={mockItem}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={mockFormErrors}
                    showEmbeddingModel={false}
                    showAllowedGroups={false}
                />
            );

            expect(screen.queryByText('Allowed Groups')).not.toBeInTheDocument();
        });
    });

    describe('Embedding Model Selection', () => {
        it('should call setFields when embedding model changes', async () => {
            const user = userEvent.setup();

            renderWithProviders(
                <CommonFieldsForm
                    item={mockItem}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={mockFormErrors}
                    showEmbeddingModel={true}
                    showAllowedGroups={false}
                />
            );

            const input = screen.getByPlaceholderText('Select an embedding model');
            await user.type(input, 'model-1');

            expect(mockSetFields).toHaveBeenCalled();
        });

        it('should call touchFields when embedding model loses focus', async () => {
            const user = userEvent.setup();

            renderWithProviders(
                <CommonFieldsForm
                    item={mockItem}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={mockFormErrors}
                    showEmbeddingModel={true}
                    showAllowedGroups={false}
                />
            );

            const input = screen.getByPlaceholderText('Select an embedding model');
            await user.click(input);
            await user.tab();

            expect(mockTouchFields).toHaveBeenCalledWith(['embeddingModel', 'embeddingModelId']);
        });

        it('should disable embedding model field when isEdit is true', () => {
            renderWithProviders(
                <CommonFieldsForm
                    item={{ ...mockItem, embeddingModel: 'model-1' }}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={mockFormErrors}
                    showEmbeddingModel={true}
                    showAllowedGroups={false}
                    isEdit={true}
                />
            );

            const input = screen.getByPlaceholderText('Select an embedding model');
            expect(input).toBeDisabled();
        });

        it('should enable embedding model field when isEdit is false', () => {
            renderWithProviders(
                <CommonFieldsForm
                    item={mockItem}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={mockFormErrors}
                    showEmbeddingModel={true}
                    showAllowedGroups={false}
                    isEdit={false}
                />
            );

            const input = screen.getByPlaceholderText('Select an embedding model');
            expect(input).not.toBeDisabled();
        });
    });

    describe('Error Handling', () => {
        it('should display error for embedding model', () => {
            const errorMessage = 'Embedding model is required';
            renderWithProviders(
                <CommonFieldsForm
                    item={mockItem}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={{ embeddingModel: errorMessage }}
                    showEmbeddingModel={true}
                    showAllowedGroups={false}
                />
            );

            expect(screen.getByText(errorMessage)).toBeInTheDocument();
        });

        it('should display error for embeddingModelId', () => {
            const errorMessage = 'Embedding model ID is required';
            renderWithProviders(
                <CommonFieldsForm
                    item={{ embeddingModelId: '' }}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={{ embeddingModelId: errorMessage }}
                    showEmbeddingModel={true}
                    showAllowedGroups={false}
                />
            );

            expect(screen.getByText(errorMessage)).toBeInTheDocument();
        });
    });

    describe('Loading States', () => {
        it('should show loading state for embedding models', () => {
            vi.spyOn(modelManagementReducer, 'useGetAllModelsQuery').mockImplementation(
                createMockQueryHook([]) as any
            );

            // Override to show loading state
            vi.spyOn(modelManagementReducer, 'useGetAllModelsQuery').mockReturnValue({
                data: [],
                isFetching: true,
                isLoading: true,
                isError: false,
                error: undefined,
                refetch: vi.fn(),
            } as any);

            renderWithProviders(
                <CommonFieldsForm
                    item={mockItem}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={mockFormErrors}
                    showEmbeddingModel={true}
                    showAllowedGroups={false}
                />
            );

            expect(screen.getByText('Embedding Model')).toBeInTheDocument();
        });
    });

    describe('Field Name Support', () => {
        it('should support embeddingModel field name', async () => {
            const user = userEvent.setup();

            renderWithProviders(
                <CommonFieldsForm
                    item={{ embeddingModel: '' }}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={mockFormErrors}
                    showEmbeddingModel={true}
                    showAllowedGroups={false}
                />
            );

            const input = screen.getByPlaceholderText('Select an embedding model');
            await user.type(input, 'test');

            expect(mockSetFields).toHaveBeenCalledWith({ embeddingModel: 't' });
        });

        it('should support embeddingModelId field name', async () => {
            const user = userEvent.setup();

            renderWithProviders(
                <CommonFieldsForm
                    item={{ embeddingModelId: '' }}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={mockFormErrors}
                    showEmbeddingModel={true}
                    showAllowedGroups={false}
                />
            );

            const input = screen.getByPlaceholderText('Select an embedding model');
            await user.type(input, 'test');

            expect(mockSetFields).toHaveBeenCalledWith({ embeddingModelId: 't' });
        });
    });
});

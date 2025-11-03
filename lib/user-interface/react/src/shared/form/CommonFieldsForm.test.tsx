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
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CommonFieldsForm } from './CommonFieldsForm';
import { renderWithProviders } from '../../test/helpers/render';
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

    beforeEach(() => {
        vi.clearAllMocks();

        // Mock the model query
        vi.spyOn(modelManagementReducer, 'useGetAllModelsQuery').mockReturnValue({
            data: mockEmbeddingModels,
            isFetching: false,
            isLoading: false,
            isError: false,
            error: undefined,
            refetch: vi.fn(),
        } as any);
    });

    describe('Embedding Model Selector', () => {
        it('should render embedding model field when showEmbeddingModel is true', () => {
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

            expect(screen.getByText('Embedding Model')).toBeInTheDocument();
            expect(
                screen.getByText('The model used to generate vector embeddings for documents')
            ).toBeInTheDocument();
        });

        it('should not render embedding model field when showEmbeddingModel is false', () => {
            renderWithProviders(
                <CommonFieldsForm
                    item={{ embeddingModel: '' }}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={mockFormErrors}
                    showEmbeddingModel={false}
                    showAllowedGroups={false}
                />
            );

            expect(screen.queryByText('Embedding Model')).not.toBeInTheDocument();
        });

        it('should filter and display only InService embedding models', async () => {
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
            await user.click(input);

            await waitFor(() => {
                expect(screen.getByText('Embedding Model 1')).toBeInTheDocument();
                expect(screen.getByText('Embedding Model 2')).toBeInTheDocument();
            });
        });

        it('should call setFields with embeddingModel when item has embeddingModel property', async () => {
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
            await user.click(input);
            
            // Click on the first option
            await waitFor(() => {
                expect(screen.getByText('Embedding Model 1')).toBeInTheDocument();
            });
            
            const option = screen.getByText('Embedding Model 1');
            await user.click(option);

            await waitFor(() => {
                expect(mockSetFields).toHaveBeenCalledWith({ embeddingModel: 'model-1' });
            });
        });

        it('should call setFields with embeddingModelId when item has embeddingModelId property', async () => {
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
            await user.click(input);
            
            // Click on the first option
            await waitFor(() => {
                expect(screen.getByText('Embedding Model 1')).toBeInTheDocument();
            });
            
            const option = screen.getByText('Embedding Model 1');
            await user.click(option);

            await waitFor(() => {
                expect(mockSetFields).toHaveBeenCalledWith({ embeddingModelId: 'model-1' });
            });
        });

        it('should call touchFields on blur', async () => {
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
            await user.click(input);
            await user.tab();

            expect(mockTouchFields).toHaveBeenCalledWith(['embeddingModel', 'embeddingModelId']);
        });

        it('should display loading state while fetching models', async () => {
            const user = userEvent.setup();
            vi.spyOn(modelManagementReducer, 'useGetAllModelsQuery').mockReturnValue({
                data: undefined,
                isFetching: true,
                isLoading: true,
            } as any);

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

            // Click to open dropdown to see loading state
            const input = screen.getByPlaceholderText('Select an embedding model');
            await user.click(input);

            await waitFor(() => {
                expect(screen.getByText('Loading embedding models...')).toBeInTheDocument();
            });
        });

        it('should display empty state when no models available', () => {
            vi.spyOn(modelManagementReducer, 'useGetAllModelsQuery').mockReturnValue({
                data: [],
                isFetching: false,
            } as any);

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
            expect(input).toBeInTheDocument();
        });

        it('should display error text when formErrors has embeddingModel error', () => {
            const errorMessage = 'Embedding model is required';
            renderWithProviders(
                <CommonFieldsForm
                    item={{ embeddingModel: '' }}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={{ embeddingModel: errorMessage }}
                    showEmbeddingModel={true}
                    showAllowedGroups={false}
                />
            );

            expect(screen.getByText(errorMessage)).toBeInTheDocument();
        });

        it('should disable embedding model field when isEdit is true', () => {
            renderWithProviders(
                <CommonFieldsForm
                    item={{ embeddingModel: 'model-1' }}
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
                    item={{ embeddingModel: '' }}
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

    describe('Allowed Groups Field', () => {
        it('should render allowed groups field when showAllowedGroups is true', () => {
            renderWithProviders(
                <CommonFieldsForm
                    item={{ allowedGroups: [] }}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={mockFormErrors}
                    showEmbeddingModel={false}
                    showAllowedGroups={true}
                />
            );

            expect(screen.getByText('Allowed Groups')).toBeInTheDocument();
            expect(
                screen.getByText(
                    'User groups that can access this resource. Leave empty for public access.'
                )
            ).toBeInTheDocument();
        });

        it('should not render allowed groups field when showAllowedGroups is false', () => {
            renderWithProviders(
                <CommonFieldsForm
                    item={{ allowedGroups: [] }}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={mockFormErrors}
                    showEmbeddingModel={false}
                    showAllowedGroups={false}
                />
            );

            expect(screen.queryByText('Allowed Groups')).not.toBeInTheDocument();
        });

        it('should call setFields when allowed groups are changed', async () => {
            const user = userEvent.setup();

            renderWithProviders(
                <CommonFieldsForm
                    item={{ allowedGroups: [] }}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={mockFormErrors}
                    showEmbeddingModel={false}
                    showAllowedGroups={true}
                />
            );

            const addButton = screen.getByText('Add new');
            await user.click(addButton);

            await waitFor(() => {
                expect(mockSetFields).toHaveBeenCalledWith({ allowedGroups: [''] });
            });
        });

        it('should display existing allowed groups', () => {
            renderWithProviders(
                <CommonFieldsForm
                    item={{ allowedGroups: ['admin', 'developers'] }}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={mockFormErrors}
                    showEmbeddingModel={false}
                    showAllowedGroups={true}
                />
            );

            expect(screen.getByDisplayValue('admin')).toBeInTheDocument();
            expect(screen.getByDisplayValue('developers')).toBeInTheDocument();
        });
    });

    describe('Conditional Rendering', () => {
        it('should render both fields when both flags are true', () => {
            renderWithProviders(
                <CommonFieldsForm
                    item={{ embeddingModel: '', allowedGroups: [] }}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={mockFormErrors}
                    showEmbeddingModel={true}
                    showAllowedGroups={true}
                />
            );

            expect(screen.getByText('Embedding Model')).toBeInTheDocument();
            expect(screen.getByText('Allowed Groups')).toBeInTheDocument();
        });

        it('should render neither field when both flags are false', () => {
            renderWithProviders(
                <CommonFieldsForm
                    item={{ embeddingModel: '', allowedGroups: [] }}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={mockFormErrors}
                    showEmbeddingModel={false}
                    showAllowedGroups={false}
                />
            );

            expect(screen.queryByText('Embedding Model')).not.toBeInTheDocument();
            expect(screen.queryByText('Allowed Groups')).not.toBeInTheDocument();
        });
    });
});

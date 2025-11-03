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
import { CollectionConfigForm } from './CollectionConfigForm';
import { renderWithProviders } from '../../../test/helpers/render';
import * as ragReducer from '../../../shared/reducers/rag.reducer';
import * as modelManagementReducer from '../../../shared/reducers/model-management.reducer';
import { ModelStatus, ModelType } from '../../../shared/model/model-management.model';

describe('CollectionConfigForm', () => {
    const mockSetFields = vi.fn();
    const mockTouchFields = vi.fn();
    const mockFormErrors = {};

    const mockRepositories = [
        {
            repositoryId: 'repo-1',
            repositoryName: 'Repository 1',
        },
        {
            repositoryId: 'repo-2',
            repositoryName: 'Repository 2',
        },
    ];

    const mockEmbeddingModels = [
        {
            modelId: 'model-1',
            modelName: 'Embedding Model 1',
            modelType: ModelType.embedding,
            status: ModelStatus.InService,
        },
    ];

    const mockItem = {
        repositoryId: '',
        name: '',
        description: '',
        embeddingModel: '',
        chunkingStrategy: undefined,
        allowedGroups: [],
        metadata: { tags: [], customFields: {} },
        private: false,
        allowChunkingOverride: true,
        pipelines: [],
    };

    beforeEach(() => {
        vi.clearAllMocks();

        vi.spyOn(ragReducer, 'useListRagRepositoriesQuery').mockReturnValue({
            data: mockRepositories,
            isLoading: false,
            isError: false,
            error: undefined,
            refetch: vi.fn(),
        } as any);

        vi.spyOn(modelManagementReducer, 'useGetAllModelsQuery').mockReturnValue({
            data: mockEmbeddingModels,
            isFetching: false,
            isLoading: false,
            isError: false,
            error: undefined,
            refetch: vi.fn(),
        } as any);
    });

    describe('Rendering', () => {
        it('should render all form fields', () => {
            renderWithProviders(
                <CollectionConfigForm
                    item={mockItem}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={mockFormErrors}
                    isEdit={false}
                />
            );

            expect(screen.getByText('Collection Name')).toBeInTheDocument();
            expect(screen.getByText('Description (optional)')).toBeInTheDocument();
            expect(screen.getByText('Repository')).toBeInTheDocument();
            expect(screen.getByText('Embedding Model')).toBeInTheDocument();
            expect(screen.getByText('Privacy')).toBeInTheDocument();
        });

        it('should render collection name input', () => {
            renderWithProviders(
                <CollectionConfigForm
                    item={mockItem}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={mockFormErrors}
                    isEdit={false}
                />
            );

            const input = screen.getByPlaceholderText('Engineering Documents');
            expect(input).toBeInTheDocument();
        });

        it('should render description textarea', () => {
            renderWithProviders(
                <CollectionConfigForm
                    item={mockItem}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={mockFormErrors}
                    isEdit={false}
                />
            );

            const textarea = screen.getByPlaceholderText(
                'Collection of engineering documentation and specifications'
            );
            expect(textarea).toBeInTheDocument();
        });

        it('should render private checkbox', () => {
            renderWithProviders(
                <CollectionConfigForm
                    item={mockItem}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={mockFormErrors}
                    isEdit={false}
                />
            );

            const checkbox = screen.getByRole('checkbox', {
                name: /Make this collection private/i,
            });
            expect(checkbox).toBeInTheDocument();
        });
    });

    describe('User Interactions', () => {
        it('should call setFields when collection name changes', async () => {
            const user = userEvent.setup();

            renderWithProviders(
                <CollectionConfigForm
                    item={mockItem}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={mockFormErrors}
                    isEdit={false}
                />
            );

            const input = screen.getByPlaceholderText('Engineering Documents');
            await user.type(input, 'Test Collection');

            expect(mockSetFields).toHaveBeenCalledWith({ name: 'T' });
        });

        it('should call touchFields when collection name loses focus', async () => {
            const user = userEvent.setup();

            renderWithProviders(
                <CollectionConfigForm
                    item={mockItem}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={mockFormErrors}
                    isEdit={false}
                />
            );

            const input = screen.getByPlaceholderText('Engineering Documents');
            await user.click(input);
            await user.tab();

            expect(mockTouchFields).toHaveBeenCalledWith(['name']);
        });

        it('should call setFields when description changes', async () => {
            const user = userEvent.setup();

            renderWithProviders(
                <CollectionConfigForm
                    item={mockItem}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={mockFormErrors}
                    isEdit={false}
                />
            );

            const textarea = screen.getByPlaceholderText(
                'Collection of engineering documentation and specifications'
            );
            await user.type(textarea, 'Test');

            expect(mockSetFields).toHaveBeenCalledWith({ description: 'T' });
        });

        it('should call setFields when private checkbox is toggled', async () => {
            const user = userEvent.setup();

            renderWithProviders(
                <CollectionConfigForm
                    item={mockItem}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={mockFormErrors}
                    isEdit={false}
                />
            );

            const checkbox = screen.getByRole('checkbox', {
                name: /Make this collection private/i,
            });
            await user.click(checkbox);

            expect(mockSetFields).toHaveBeenCalledWith({ private: true });
        });

        it('should call setFields when repository is selected', async () => {
            const user = userEvent.setup();

            renderWithProviders(
                <CollectionConfigForm
                    item={mockItem}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={mockFormErrors}
                    isEdit={false}
                />
            );

            const select = screen.getByRole('button', { name: /Repository/i });
            await user.click(select);

            await waitFor(() => {
                expect(screen.getAllByText('Repository 1')[0]).toBeInTheDocument();
            });

            const options = screen.getAllByText('Repository 1');
            await user.click(options[0]);

            expect(mockSetFields).toHaveBeenCalledWith({ repositoryId: 'repo-1' });
        });
    });

    describe('Edit Mode', () => {
        it('should disable repository field when isEdit is true', () => {
            renderWithProviders(
                <CollectionConfigForm
                    item={{ ...mockItem, repositoryId: 'repo-1' }}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={mockFormErrors}
                    isEdit={true}
                />
            );

            const select = screen.getByRole('button', { name: /Repository/i });
            expect(select).toBeDisabled();
        });

        it('should disable embedding model field when isEdit is true', () => {
            renderWithProviders(
                <CollectionConfigForm
                    item={{ ...mockItem, embeddingModel: 'model-1' }}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={mockFormErrors}
                    isEdit={true}
                />
            );

            const input = screen.getByPlaceholderText('Select an embedding model');
            expect(input).toBeDisabled();
        });

        it('should disable private checkbox when isEdit is true', () => {
            renderWithProviders(
                <CollectionConfigForm
                    item={{ ...mockItem, private: true }}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={mockFormErrors}
                    isEdit={true}
                />
            );

            const checkbox = screen.getByRole('checkbox', {
                name: /Make this collection private/i,
            });
            expect(checkbox).toBeDisabled();
        });

        it('should enable repository field when isEdit is false', () => {
            renderWithProviders(
                <CollectionConfigForm
                    item={mockItem}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={mockFormErrors}
                    isEdit={false}
                />
            );

            const select = screen.getByRole('button', { name: /Repository/i });
            expect(select).not.toBeDisabled();
        });

        it('should enable embedding model field when isEdit is false', () => {
            renderWithProviders(
                <CollectionConfigForm
                    item={mockItem}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={mockFormErrors}
                    isEdit={false}
                />
            );

            const input = screen.getByPlaceholderText('Select an embedding model');
            expect(input).not.toBeDisabled();
        });

        it('should enable private checkbox when isEdit is false', () => {
            renderWithProviders(
                <CollectionConfigForm
                    item={mockItem}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={mockFormErrors}
                    isEdit={false}
                />
            );

            const checkbox = screen.getByRole('checkbox', {
                name: /Make this collection private/i,
            });
            expect(checkbox).not.toBeDisabled();
        });
    });

    describe('Error Handling', () => {
        it('should display error for collection name', () => {
            const errorMessage = 'Collection name is required';
            renderWithProviders(
                <CollectionConfigForm
                    item={mockItem}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={{ name: errorMessage }}
                    isEdit={false}
                />
            );

            expect(screen.getByText(errorMessage)).toBeInTheDocument();
        });

        it('should display error for repository', () => {
            const errorMessage = 'Repository is required';
            renderWithProviders(
                <CollectionConfigForm
                    item={mockItem}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={{ repositoryId: errorMessage }}
                    isEdit={false}
                />
            );

            expect(screen.getByText(errorMessage)).toBeInTheDocument();
        });
    });

    describe('Loading States', () => {
        it('should show loading state for repositories', () => {
            vi.spyOn(ragReducer, 'useListRagRepositoriesQuery').mockReturnValue({
                data: undefined,
                isLoading: true,
                isError: false,
                error: undefined,
                refetch: vi.fn(),
            } as any);

            renderWithProviders(
                <CollectionConfigForm
                    item={mockItem}
                    setFields={mockSetFields}
                    touchFields={mockTouchFields}
                    formErrors={mockFormErrors}
                    isEdit={false}
                />
            );

            const select = screen.getByRole('button', { name: /Repository/i });
            expect(select).toBeInTheDocument();
        });
    });
});

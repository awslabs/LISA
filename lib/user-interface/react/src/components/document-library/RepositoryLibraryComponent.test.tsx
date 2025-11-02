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
import { RepositoryLibraryComponent } from './RepositoryLibraryComponent';
import { renderWithProviders } from '../../test/helpers/render';
import {
    createMockCollections,
    createMockCollection,
} from '../../test/factories/collection.factory';
import { MemoryRouter } from 'react-router-dom';
import * as ragReducer from '../../shared/reducers/rag.reducer';

const mockNavigate = vi.fn();

vi.mock('react-router-dom', async () => {
    const actual: any = await vi.importActual('react-router-dom');
    return {
        ...actual,
        useNavigate: () => mockNavigate,
    };
});

describe('RepositoryLibraryComponent', () => {
    beforeEach(() => {
        vi.clearAllMocks();

        // Default mocks
        vi.spyOn(ragReducer, 'useListAllCollectionsQuery').mockReturnValue({
            data: [],
            isLoading: false,
            isError: false,
            error: undefined,
            refetch: vi.fn(),
        } as any);

        vi.spyOn(ragReducer, 'useDeleteCollectionMutation').mockReturnValue([
            vi.fn(),
            { isLoading: false, isError: false, error: undefined },
        ] as any);
    });

    describe('Rendering', () => {
        it('should display collections in table format', async () => {
            const mockCollections = createMockCollections(3);
            vi.spyOn(ragReducer, 'useListAllCollectionsQuery').mockReturnValue({
                data: mockCollections,
                isLoading: false,
            } as any);

            renderWithProviders(
                <MemoryRouter>
                    <RepositoryLibraryComponent />
                </MemoryRouter>
            );

            await waitFor(() => {
                expect(screen.getByText('Collection Name')).toBeInTheDocument();
                expect(screen.getByText('Collection ID')).toBeInTheDocument();
                expect(screen.getByText('Repository')).toBeInTheDocument();
                expect(screen.getByText('Embedding Model')).toBeInTheDocument();
            });
        });

        it('should render collections header with count', async () => {
            const mockCollections = createMockCollections(5);
            vi.spyOn(ragReducer, 'useListAllCollectionsQuery').mockReturnValue({
                data: mockCollections,
                isLoading: false,
            } as any);

            renderWithProviders(
                <MemoryRouter>
                    <RepositoryLibraryComponent />
                </MemoryRouter>
            );

            await waitFor(() => {
                expect(screen.getByText('Collections')).toBeInTheDocument();
                expect(screen.getByText('5')).toBeInTheDocument();
            });
        });

        it('should display collection data in table rows', async () => {
            const mockCollection = createMockCollection({
                name: 'Engineering Docs',
                collectionId: 'eng-123',
                repositoryId: 'repo-456',
            });
            vi.spyOn(ragReducer, 'useListAllCollectionsQuery').mockReturnValue({
                data: [mockCollection],
                isLoading: false,
            } as any);

            renderWithProviders(
                <MemoryRouter>
                    <RepositoryLibraryComponent />
                </MemoryRouter>
            );

            await waitFor(() => {
                expect(screen.getByText('Engineering Docs')).toBeInTheDocument();
                expect(screen.getByText('eng-123')).toBeInTheDocument();
                expect(screen.getByText('repo-456')).toBeInTheDocument();
            });
        });

        it('should show loading state', async () => {
            vi.spyOn(ragReducer, 'useListAllCollectionsQuery').mockReturnValue({
                data: undefined,
                isLoading: true,
            } as any);

            renderWithProviders(
                <MemoryRouter>
                    <RepositoryLibraryComponent />
                </MemoryRouter>
            );

            expect(screen.getByText('Loading collections')).toBeInTheDocument();
        });

        it('should show empty state when no collections', async () => {
            vi.spyOn(ragReducer, 'useListAllCollectionsQuery').mockReturnValue({
                data: [],
                isLoading: false,
            } as any);

            renderWithProviders(
                <MemoryRouter>
                    <RepositoryLibraryComponent />
                </MemoryRouter>
            );

            await waitFor(() => {
                expect(screen.getByText('No collections')).toBeInTheDocument();
            });
        });
    });

    describe('Navigation', () => {
        it('should navigate to document library when row is clicked', async () => {
            const user = userEvent.setup();
            const mockCollection = createMockCollection({
                collectionId: 'col-123',
                repositoryId: 'repo-456',
            });
            vi.spyOn(ragReducer, 'useListAllCollectionsQuery').mockReturnValue({
                data: [mockCollection],
                isLoading: false,
            } as any);

            renderWithProviders(
                <MemoryRouter>
                    <RepositoryLibraryComponent />
                </MemoryRouter>
            );

            await waitFor(() => {
                expect(screen.getByText('Test Collection')).toBeInTheDocument();
            });

            const row = screen.getByText('Test Collection').closest('tr');
            await user.click(row!);

            expect(mockNavigate).toHaveBeenCalledWith('/document-library/repo-456/col-123');
        });
    });

    describe('Actions Button', () => {
        it('should render Actions button', async () => {
            vi.spyOn(ragReducer, 'useListAllCollectionsQuery').mockReturnValue({
                data: createMockCollections(1),
                isLoading: false,
            } as any);

            renderWithProviders(
                <MemoryRouter>
                    <RepositoryLibraryComponent />
                </MemoryRouter>
            );

            await waitFor(() => {
                expect(screen.getByText('Actions')).toBeInTheDocument();
            });
        });

        it('should disable Actions button when no collection is selected', async () => {
            vi.spyOn(ragReducer, 'useListAllCollectionsQuery').mockReturnValue({
                data: createMockCollections(1),
                isLoading: false,
            } as any);

            renderWithProviders(
                <MemoryRouter>
                    <RepositoryLibraryComponent />
                </MemoryRouter>
            );

            await waitFor(() => {
                const actionsButton = screen.getByText('Actions').closest('button');
                expect(actionsButton).toBeDisabled();
            });
        });
    });

    describe('Refresh Functionality', () => {
        it('should render refresh button', async () => {
            vi.spyOn(ragReducer, 'useListAllCollectionsQuery').mockReturnValue({
                data: createMockCollections(1),
                isLoading: false,
            } as any);

            renderWithProviders(
                <MemoryRouter>
                    <RepositoryLibraryComponent />
                </MemoryRouter>
            );

            await waitFor(() => {
                const refreshButton = screen.getByLabelText('Refresh collections');
                expect(refreshButton).toBeInTheDocument();
            });
        });
    });

    describe('Filter Functionality', () => {
        it('should render filter input', async () => {
            vi.spyOn(ragReducer, 'useListAllCollectionsQuery').mockReturnValue({
                data: createMockCollections(3),
                isLoading: false,
            } as any);

            renderWithProviders(
                <MemoryRouter>
                    <RepositoryLibraryComponent />
                </MemoryRouter>
            );

            await waitFor(() => {
                expect(screen.getByPlaceholderText('Find collections')).toBeInTheDocument();
            });
        });
    });

    describe('Pagination', () => {
        it('should handle large number of collections', async () => {
            // Create enough collections to test pagination behavior
            const mockCollections = createMockCollections(25);
            vi.spyOn(ragReducer, 'useListAllCollectionsQuery').mockReturnValue({
                data: mockCollections,
                isLoading: false,
            } as any);

            renderWithProviders(
                <MemoryRouter>
                    <RepositoryLibraryComponent />
                </MemoryRouter>
            );

            await waitFor(() => {
                // Verify the component renders successfully with many items
                expect(screen.getByText('Collections')).toBeInTheDocument();
                expect(screen.getByText('25')).toBeInTheDocument();
            });
        });
    });
});

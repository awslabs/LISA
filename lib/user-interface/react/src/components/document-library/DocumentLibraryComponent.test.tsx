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
import { DocumentLibraryComponent, getMatchesCountText } from './DocumentLibraryComponent';
import { renderWithProviders } from '../../test/helpers/render';
import { MemoryRouter } from 'react-router-dom';
import { createMockDocument } from '../../test/factories/document.factory';
import * as ragReducer from '../../shared/reducers/rag.reducer';
import * as store from '../../config/store';

vi.mock('../../shared/util/downloader', () => ({
    downloadFile: vi.fn(),
}));

describe('DocumentLibraryComponent', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        
        // Mock Redux selectors
        vi.spyOn(store, 'useAppSelector').mockImplementation((selector: any) => {
            if (selector.toString().includes('selectCurrentUsername')) return 'test-user';
            if (selector.toString().includes('selectCurrentUserIsAdmin')) return false;
            return null;
        });
        
        vi.spyOn(store, 'useAppDispatch').mockReturnValue(vi.fn() as any);
        
        // Default mocks for queries
        vi.spyOn(ragReducer, 'useListRagDocumentsQuery').mockReturnValue({
            data: {
                documents: [],
                totalDocuments: 0,
                hasNextPage: false,
            },
            isLoading: false,
        } as any);
        
        vi.spyOn(ragReducer, 'useGetCollectionQuery').mockReturnValue({
            data: null,
        } as any);
        
        vi.spyOn(ragReducer, 'useDeleteRagDocumentsMutation').mockReturnValue([
            vi.fn(),
            { isLoading: false },
        ] as any);
        
        vi.spyOn(ragReducer, 'useLazyDownloadRagDocumentQuery').mockReturnValue([
            vi.fn(),
            { isFetching: false },
        ] as any);
    });

    describe('Rendering', () => {
        it('should render document table with repository ID in header', async () => {
            renderWithProviders(
                <MemoryRouter>
                    <DocumentLibraryComponent repositoryId="repo-123" />
                </MemoryRouter>
            );

            await waitFor(() => {
                expect(screen.getByText('repo-123 Documents')).toBeInTheDocument();
            });
        });

        it('should render collection name in header when collectionId is provided', async () => {
            vi.spyOn(ragReducer, 'useGetCollectionQuery').mockReturnValue({
                data: {
                    collectionId: 'col-123',
                    name: 'Engineering Docs',
                },
            } as any);

            renderWithProviders(
                <MemoryRouter>
                    <DocumentLibraryComponent 
                        repositoryId="repo-123" 
                        collectionId="col-123" 
                    />
                </MemoryRouter>
            );

            await waitFor(() => {
                expect(screen.getByText('Engineering Docs Documents')).toBeInTheDocument();
            });
        });

        it('should display documents in table', async () => {
            const mockDocs = [
                createMockDocument({ document_name: 'doc1.pdf' }),
                createMockDocument({ document_name: 'doc2.pdf', document_id: 'doc-456' }),
            ];
            vi.spyOn(ragReducer, 'useListRagDocumentsQuery').mockReturnValue({
                data: {
                    documents: mockDocs,
                    totalDocuments: 2,
                    hasNextPage: false,
                },
                isLoading: false,
            } as any);

            renderWithProviders(
                <MemoryRouter>
                    <DocumentLibraryComponent repositoryId="repo-123" />
                </MemoryRouter>
            );

            await waitFor(() => {
                expect(screen.getByText('doc1.pdf')).toBeInTheDocument();
                expect(screen.getByText('doc2.pdf')).toBeInTheDocument();
            });
        });

        it('should show loading state', async () => {
            vi.spyOn(ragReducer, 'useListRagDocumentsQuery').mockReturnValue({
                data: undefined,
                isLoading: true,
            } as any);

            renderWithProviders(
                <MemoryRouter>
                    <DocumentLibraryComponent repositoryId="repo-123" />
                </MemoryRouter>
            );

            expect(screen.getByText('Loading documents')).toBeInTheDocument();
        });

        it('should show empty state when no documents', async () => {
            vi.spyOn(ragReducer, 'useListRagDocumentsQuery').mockReturnValue({
                data: {
                    documents: [],
                    totalDocuments: 0,
                    hasNextPage: false,
                },
                isLoading: false,
            } as any);

            renderWithProviders(
                <MemoryRouter>
                    <DocumentLibraryComponent repositoryId="repo-123" />
                </MemoryRouter>
            );

            await waitFor(() => {
                expect(screen.getByText('No documents')).toBeInTheDocument();
            });
        });

        it('should display document count in header', async () => {
            vi.spyOn(ragReducer, 'useListRagDocumentsQuery').mockReturnValue({
                data: {
                    documents: [createMockDocument()],
                    totalDocuments: 42,
                    hasNextPage: false,
                },
                isLoading: false,
            } as any);

            renderWithProviders(
                <MemoryRouter>
                    <DocumentLibraryComponent repositoryId="repo-123" />
                </MemoryRouter>
            );

            await waitFor(() => {
                expect(screen.getByText('(42)')).toBeInTheDocument();
            });
        });
    });

    describe('Actions Button', () => {
        it('should render Actions button', async () => {
            vi.spyOn(ragReducer, 'useListRagDocumentsQuery').mockReturnValue({
                data: {
                    documents: [createMockDocument()],
                    totalDocuments: 1,
                    hasNextPage: false,
                },
                isLoading: false,
            } as any);

            renderWithProviders(
                <MemoryRouter>
                    <DocumentLibraryComponent repositoryId="repo-123" />
                </MemoryRouter>
            );

            await waitFor(() => {
                expect(screen.getByText('Actions')).toBeInTheDocument();
            });
        });

        it('should disable Actions button when no documents selected', async () => {
            vi.spyOn(ragReducer, 'useListRagDocumentsQuery').mockReturnValue({
                data: {
                    documents: [createMockDocument()],
                    totalDocuments: 1,
                    hasNextPage: false,
                },
                isLoading: false,
            } as any);

            renderWithProviders(
                <MemoryRouter>
                    <DocumentLibraryComponent repositoryId="repo-123" />
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
            vi.spyOn(ragReducer, 'useListRagDocumentsQuery').mockReturnValue({
                data: {
                    documents: [createMockDocument()],
                    totalDocuments: 1,
                    hasNextPage: false,
                },
                isLoading: false,
            } as any);

            renderWithProviders(
                <MemoryRouter>
                    <DocumentLibraryComponent repositoryId="repo-123" />
                </MemoryRouter>
            );

            await waitFor(() => {
                const refreshButton = screen.getByLabelText('Refresh documents');
                expect(refreshButton).toBeInTheDocument();
            });
        });
    });

    describe('Filter Functionality', () => {
        it('should render filter input', async () => {
            vi.spyOn(ragReducer, 'useListRagDocumentsQuery').mockReturnValue({
                data: {
                    documents: [createMockDocument()],
                    totalDocuments: 1,
                    hasNextPage: false,
                },
                isLoading: false,
            } as any);

            renderWithProviders(
                <MemoryRouter>
                    <DocumentLibraryComponent repositoryId="repo-123" />
                </MemoryRouter>
            );

            await waitFor(() => {
                const filterInput = screen.getByRole('searchbox');
                expect(filterInput).toBeInTheDocument();
            });
        });
    });

    describe('Pagination', () => {
        it('should render pagination controls', async () => {
            vi.spyOn(ragReducer, 'useListRagDocumentsQuery').mockReturnValue({
                data: {
                    documents: [createMockDocument()],
                    totalDocuments: 50,
                    hasNextPage: true,
                },
                isLoading: false,
            } as any);

            renderWithProviders(
                <MemoryRouter>
                    <DocumentLibraryComponent repositoryId="repo-123" />
                </MemoryRouter>
            );

            await waitFor(() => {
                expect(screen.getByLabelText('Next page')).toBeInTheDocument();
                expect(screen.getByLabelText('Previous page')).toBeInTheDocument();
            });
        });
    });

    describe('Collection Filtering', () => {
        it('should fetch collection data when collectionId is provided', async () => {
            const mockGetCollection = vi.fn();
            vi.spyOn(ragReducer, 'useGetCollectionQuery').mockReturnValue({
                data: { collectionId: 'col-123', name: 'Test Collection' },
            } as any);

            renderWithProviders(
                <MemoryRouter>
                    <DocumentLibraryComponent 
                        repositoryId="repo-123" 
                        collectionId="col-456" 
                    />
                </MemoryRouter>
            );

            await waitFor(() => {
                expect(ragReducer.useGetCollectionQuery).toHaveBeenCalled();
            });
        });
    });

    describe('Utility Functions', () => {
        it('should return correct matches count text for single match', () => {
            expect(getMatchesCountText(1)).toBe('1 match');
        });

        it('should return correct matches count text for multiple matches', () => {
            expect(getMatchesCountText(5)).toBe('5 matches');
        });

        it('should return correct matches count text for zero matches', () => {
            expect(getMatchesCountText(0)).toBe('0 matches');
        });
    });
});

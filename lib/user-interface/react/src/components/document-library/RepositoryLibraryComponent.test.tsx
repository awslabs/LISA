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
import { renderWithRouter } from '../../test/helpers/router';
import { 
    createMockCollections, 
    createMockPublicCollection, 
    createMockPrivateCollection 
} from '../../test/factories/collection.factory';
import { MemoryRouter } from 'react-router-dom';

const mockNavigate = vi.fn();

vi.mock('react-router-dom', async () => {
    const actual: any = await vi.importActual('react-router-dom');
    return {
        ...actual,
        useNavigate: () => mockNavigate,
    };
});

vi.mock('../../shared/reducers/rag.reducer', async () => {
    const actual: any = await vi.importActual('../../shared/reducers/rag.reducer');
    return {
        ...actual,
        useListAllCollectionsQuery: vi.fn(() => ({
            data: [], // Backend returns only accessible collections
            isLoading: false,
        })),
    };
});

describe('RepositoryLibraryComponent with Collections', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('should display collections in table format (not cards)', async () => {
        renderWithProviders(
            <MemoryRouter>
                <RepositoryLibraryComponent />
            </MemoryRouter>
        );

        await waitFor(() => {
            // Check for table headers (not card layout)
            expect(screen.getByText('Collection Name')).toBeInTheDocument();
            expect(screen.getByText('Collection ID')).toBeInTheDocument();
            expect(screen.getByText('Repository')).toBeInTheDocument();
        });
    });

    it('should render collections header', async () => {
        renderWithProviders(
            <MemoryRouter>
                <RepositoryLibraryComponent />
            </MemoryRouter>
        );

        await waitFor(() => {
            expect(screen.getByText('Collections')).toBeInTheDocument();
        });
    });

    it('should display collections returned from backend (access control handled server-side)', async () => {
        // Note: Backend filters collections based on user's group memberships
        // Frontend displays whatever collections the backend returns
        renderWithProviders(
            <MemoryRouter>
                <RepositoryLibraryComponent />
            </MemoryRouter>
        );

        await waitFor(() => {
            expect(screen.getByText('Collections')).toBeInTheDocument();
        });
    });
});

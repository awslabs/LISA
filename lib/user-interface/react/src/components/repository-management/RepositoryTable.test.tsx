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
import { RepositoryTable } from './RepositoryTable';
import { renderWithProviders } from '../../test/helpers/render';
import { createMockRepositories } from '../../test/factories/repository.factory';

// Mock the API hooks
const mockRepositories = createMockRepositories(3);
const mockRagStatus = {
    'test-repo-1': 'CREATE_COMPLETE',
    'test-repo-2': 'CREATE_IN_PROGRESS',
    'test-repo-3': 'CREATE_FAILED',
};

vi.mock('../../shared/reducers/rag.reducer', async () => {
    const actual: any = await vi.importActual('../../shared/reducers/rag.reducer');
    return {
        ...actual,
        useListRagRepositoriesQuery: vi.fn(() => ({
            data: mockRepositories,
            isLoading: false,
        })),
        useGetRagStatusQuery: vi.fn(() => ({
            data: mockRagStatus,
            isFetching: false,
        })),
        ragApi: {
            ...actual.ragApi,
            util: {
                invalidateTags: vi.fn(),
            },
        },
    };
});

vi.mock('./createRepository/CreateRepositoryModal', () => ({
    default: () => <div data-testid="create-repository-modal">Create Repository Modal</div>,
}));

describe('RepositoryTable', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('should display all repository columns correctly', async () => {
        renderWithProviders(<RepositoryTable />);

        await waitFor(() => {
            expect(screen.getByText('Name')).toBeInTheDocument();
            expect(screen.getByText('Repository ID')).toBeInTheDocument();
            expect(screen.getByText('Type')).toBeInTheDocument();
            expect(screen.getByText('Default Embedding Model')).toBeInTheDocument();
            expect(screen.getByText('Allowed Groups')).toBeInTheDocument();
            expect(screen.getByText('Status')).toBeInTheDocument();
        });
    });

    it('should display repository data in table', async () => {
        renderWithProviders(<RepositoryTable />);

        await waitFor(() => {
            expect(screen.getByText('Test Repository 1')).toBeInTheDocument();
            expect(screen.getByText('test-repo-1')).toBeInTheDocument();
        });
    });

    it('should display public label for repositories with empty allowedGroups', async () => {
        renderWithProviders(<RepositoryTable />);

        await waitFor(() => {
            const publicLabels = screen.getAllByText('(public)');
            expect(publicLabels.length).toBeGreaterThan(0);
        });
    });

    it('should have Create Repository button', async () => {
        renderWithProviders(<RepositoryTable />);

        await waitFor(() => {
            expect(screen.getByText('Create Repository')).toBeInTheDocument();
        });
    });

    it('should have Actions dropdown', async () => {
        renderWithProviders(<RepositoryTable />);

        await waitFor(() => {
            expect(screen.getByText('Actions')).toBeInTheDocument();
        });
    });

    it('should have refresh button', async () => {
        renderWithProviders(<RepositoryTable />);

        await waitFor(() => {
            const refreshButtons = screen.getAllByLabelText('Refresh repository table');
            expect(refreshButtons.length).toBeGreaterThan(0);
        });
    });

    it('should display status indicators for repositories', async () => {
        renderWithProviders(<RepositoryTable />);

        await waitFor(() => {
            expect(screen.getByText('CREATE_COMPLETE')).toBeInTheDocument();
            expect(screen.getByText('CREATE_IN_PROGRESS')).toBeInTheDocument();
            expect(screen.getByText('CREATE_FAILED')).toBeInTheDocument();
        });
    });
});

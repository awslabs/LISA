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
import { RepositoryActions } from './RepositoryActions';
import { renderWithProviders } from '../../test/helpers/render';
import { createMockRepositories } from '../../test/factories/repository.factory';

const mockRepositories = createMockRepositories(3);

vi.mock('../../shared/reducers/rag.reducer', async () => {
    const actual: any = await vi.importActual('../../shared/reducers/rag.reducer');
    return {
        ...actual,
        useListRagRepositoriesQuery: vi.fn(() => ({
            data: mockRepositories,
            isFetching: false,
            isLoading: false,
        })),
        useUpdateRagRepositoryMutation: vi.fn(() => [vi.fn(), { isSuccess: false, isError: false, error: null, isLoading: false }]),
        useDeleteRagRepositoryMutation: vi.fn(() => [vi.fn(), { isSuccess: false, isError: false, error: null, isLoading: false }]),
        ragApi: {
            ...actual.ragApi,
            util: {
                invalidateTags: vi.fn(),
            },
        },
    };
});

const defaultProps = {
    selectedItems: [] as any[],
    setSelectedItems: vi.fn(),
    setNewRepositoryModalVisible: vi.fn(),
    setEdit: vi.fn(),
};

const adminState = {
    user: { info: { isAdmin: true, isRagAdmin: false, isUser: true, isApiUser: false } },
};

const ragAdminState = {
    user: { info: { isAdmin: false, isRagAdmin: true, isUser: false, isApiUser: false } },
};

describe('RepositoryActions', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    describe('admin user', () => {
        it('shows Create Repository button', async () => {
            renderWithProviders(<RepositoryActions {...defaultProps} />, { preloadedState: adminState });

            await waitFor(() => {
                expect(screen.getByText('Create Repository')).toBeInTheDocument();
            });
        });

        it('shows Delete in actions dropdown', async () => {
            const user = userEvent.setup();
            const propsWithSelection = {
                ...defaultProps,
                selectedItems: [mockRepositories[0]],
            };
            renderWithProviders(<RepositoryActions {...propsWithSelection} />, { preloadedState: adminState });

            const actionsButton = screen.getByText('Actions');
            await user.click(actionsButton);

            await waitFor(() => {
                expect(screen.getByText('Delete')).toBeInTheDocument();
            });
        });
    });

    describe('RAG admin user', () => {
        it('does not show Create Repository button', async () => {
            renderWithProviders(<RepositoryActions {...defaultProps} />, { preloadedState: ragAdminState });

            await waitFor(() => {
                expect(screen.queryByText('Create Repository')).not.toBeInTheDocument();
            });
        });

        it('does not show Delete in actions dropdown', async () => {
            const user = userEvent.setup();
            const propsWithSelection = {
                ...defaultProps,
                selectedItems: [mockRepositories[0]],
            };
            renderWithProviders(<RepositoryActions {...propsWithSelection} />, { preloadedState: ragAdminState });

            const actionsButton = screen.getByText('Actions');
            await user.click(actionsButton);

            await waitFor(() => {
                expect(screen.queryByText('Delete')).not.toBeInTheDocument();
            });
        });

        it('shows Edit in actions dropdown', async () => {
            const user = userEvent.setup();
            const propsWithSelection = {
                ...defaultProps,
                selectedItems: [mockRepositories[0]],
            };
            renderWithProviders(<RepositoryActions {...propsWithSelection} />, { preloadedState: ragAdminState });

            const actionsButton = screen.getByText('Actions');
            await user.click(actionsButton);

            await waitFor(() => {
                expect(screen.getByText('Edit')).toBeInTheDocument();
            });
        });
    });
});

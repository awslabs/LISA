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

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import { MemoryRouter } from 'react-router-dom';
import { AuthProvider } from 'react-oidc-context';
import Sessions from './Sessions';
import modalReducer from '@/shared/reducers/modal.reducer';

// Mock the reducers
vi.mock('@/shared/reducers/configuration.reducer', () => ({
    useLazyGetConfigurationQuery: vi.fn(() => [
        vi.fn(() => Promise.resolve({ data: [{ configuration: { enabledComponents: { deleteSessionHistory: true } } }] })),
    ]),
}));

vi.mock('@/shared/reducers/session.reducer', () => ({
    sessionApi: {
        util: {
            invalidateTags: vi.fn(),
        },
    },
    useDeleteAllSessionsForUserMutation: vi.fn(() => [
        vi.fn(),
        { isSuccess: false, isError: false, error: null, isLoading: false },
    ]),
    useDeleteSessionByIdMutation: vi.fn(() => [
        vi.fn(),
        { isSuccess: false, isError: false, error: null, isLoading: false },
    ]),
    useLazyGetSessionByIdQuery: vi.fn(() => [vi.fn()]),
    useListSessionsQuery: vi.fn(),
    useUpdateSessionNameMutation: vi.fn(() => [
        vi.fn(),
        { isSuccess: false, isError: false, error: null, isLoading: false },
    ]),
}));

vi.mock('@/config/store', () => ({
    useAppDispatch: vi.fn(() => vi.fn()),
}));

vi.mock('@/shared/util/hooks', () => ({
    useNotificationService: vi.fn(() => ({
        generateNotification: vi.fn(),
    })),
}));

const createMockStore = () => {
    return configureStore({
        reducer: {
            modal: modalReducer,
        },
    });
};

const renderWithProviders = (component: React.ReactElement) => {
    const mockStore = createMockStore();
    return render(
        <Provider store={mockStore}>
            <AuthProvider>
                <MemoryRouter>
                    {component}
                </MemoryRouter>
            </AuthProvider>
        </Provider>
    );
};

describe('Sessions', () => {
    const mockNewSession = vi.fn();

    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('displays "No sessions" message when there are no sessions', async () => {
        const { useListSessionsQuery } = await import('@/shared/reducers/session.reducer');
        vi.mocked(useListSessionsQuery).mockReturnValue({
            data: [],
            isLoading: false,
        } as any);

        renderWithProviders(<Sessions newSession={mockNewSession} />);

        await waitFor(() => {
            expect(screen.getByText('No sessions')).toBeInTheDocument();
            expect(screen.getByText('Start a new conversation to create your first session')).toBeInTheDocument();
        });
    });

    it('displays sessions when data is available', async () => {
        const mockSessions = [
            {
                sessionId: 'session-1',
                name: 'Test Session 1',
                startTime: new Date().toISOString(),
                lastUpdated: new Date().toISOString(),
            },
            {
                sessionId: 'session-2',
                name: 'Test Session 2',
                startTime: new Date(Date.now() - 86400000).toISOString(), // 1 day ago
                lastUpdated: new Date(Date.now() - 86400000).toISOString(),
            },
        ];

        const { useListSessionsQuery } = await import('@/shared/reducers/session.reducer');
        vi.mocked(useListSessionsQuery).mockReturnValue({
            data: mockSessions,
            isLoading: false,
        } as any);

        renderWithProviders(<Sessions newSession={mockNewSession} />);

        await waitFor(() => {
            expect(screen.getByText('Test Session 1')).toBeInTheDocument();
            expect(screen.getByText('Test Session 2')).toBeInTheDocument();
        });

        expect(screen.queryByText('No sessions')).not.toBeInTheDocument();
    });

    it('displays loading state while fetching sessions', async () => {
        const { useListSessionsQuery } = await import('@/shared/reducers/session.reducer');
        vi.mocked(useListSessionsQuery).mockReturnValue({
            data: undefined,
            isLoading: true,
        } as any);

        renderWithProviders(<Sessions newSession={mockNewSession} />);

        await waitFor(() => {
            expect(screen.getByText('Loading sessions...')).toBeInTheDocument();
        });
    });

    it('displays "No sessions" with search hint when search returns no results', async () => {
        const user = userEvent.setup();
        const mockSessions = [
            {
                sessionId: 'session-1',
                name: 'Test Session',
                startTime: new Date().toISOString(),
                lastUpdated: new Date().toISOString(),
            },
        ];

        const { useListSessionsQuery } = await import('@/shared/reducers/session.reducer');
        vi.mocked(useListSessionsQuery).mockReturnValue({
            data: mockSessions,
            isLoading: false,
        } as any);

        renderWithProviders(<Sessions newSession={mockNewSession} />);

        // Open search popover
        const searchButton = screen.getByLabelText('Search sessions');
        await user.click(searchButton);

        // Type search query that won't match
        const searchInput = screen.getByPlaceholderText('Search sessions by name...');
        await user.type(searchInput, 'NonExistentSession');

        await waitFor(() => {
            expect(screen.getByText('No sessions')).toBeInTheDocument();
            expect(screen.getByText('Try adjusting your search query')).toBeInTheDocument();
        });
    });

    it('filters sessions based on search query', async () => {
        const user = userEvent.setup();
        const mockSessions = [
            {
                sessionId: 'session-1',
                name: 'Python Tutorial',
                startTime: new Date().toISOString(),
                lastUpdated: new Date().toISOString(),
            },
            {
                sessionId: 'session-2',
                name: 'JavaScript Guide',
                startTime: new Date().toISOString(),
                lastUpdated: new Date().toISOString(),
            },
        ];

        const { useListSessionsQuery } = await import('@/shared/reducers/session.reducer');
        vi.mocked(useListSessionsQuery).mockReturnValue({
            data: mockSessions,
            isLoading: false,
        } as any);

        renderWithProviders(<Sessions newSession={mockNewSession} />);

        // Open search popover
        const searchButton = screen.getByLabelText('Search sessions');
        await user.click(searchButton);

        // Type search query
        const searchInput = screen.getByPlaceholderText('Search sessions by name...');
        await user.type(searchInput, 'Python');

        await waitFor(() => {
            expect(screen.getByText('Python Tutorial')).toBeInTheDocument();
            expect(screen.queryByText('JavaScript Guide')).not.toBeInTheDocument();
        });
    });

    it('calls newSession when new session button is clicked', async () => {
        const user = userEvent.setup();
        const { useListSessionsQuery } = await import('@/shared/reducers/session.reducer');
        vi.mocked(useListSessionsQuery).mockReturnValue({
            data: [],
            isLoading: false,
        } as any);

        renderWithProviders(<Sessions newSession={mockNewSession} />);

        const newSessionButton = screen.getByLabelText('New Session');
        await user.click(newSessionButton);

        expect(mockNewSession).toHaveBeenCalledOnce();
    });
});

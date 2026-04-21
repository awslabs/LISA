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
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';

import App from './App';
import {
    selectCurrentUserIsAdmin,
    selectCurrentUserIsUser,
    selectCurrentUserIsRagAdmin,
    selectCurrentUserIsApiUser,
    selectCurrentUsername,
} from './shared/reducers/user.reducer';

// Mock auth
vi.mock('./auth/useAuth');

// Mock store - useAppSelector matches by selector function reference
vi.mock('./config/store', async (importOriginal) => {
    const actual = await importOriginal<any>();
    return {
        ...actual,
        useAppDispatch: vi.fn(() => vi.fn()),
        useAppSelector: vi.fn(),
    };
});

// Mock lazy-loaded pages to avoid Suspense complexity
vi.mock('./pages/Home', () => ({ default: () => <div data-testid='home-page'>Home</div> }));
vi.mock('./pages/Chatbot', () => ({ default: () => <div data-testid='chatbot-page'>Chatbot</div> }));
vi.mock('./pages/RepositoryManagement', () => ({ default: () => <div data-testid='repo-management-page'>Repository Management</div> }));
vi.mock('./pages/ModelManagement', () => ({ default: () => <div data-testid='model-management-page'>Model Management</div> }));
vi.mock('./pages/Configuration', () => ({ default: () => <div data-testid='configuration-page'>Configuration</div> }));
vi.mock('./pages/ApiTokenManagement', () => ({ default: () => <div data-testid='api-token-page'>API Token Management</div> }));

// Mock configuration query
vi.mock('./shared/reducers/configuration.reducer', async (importOriginal) => {
    const actual = await importOriginal<any>();
    return {
        ...actual,
        useGetConfigurationQuery: vi.fn(() => ({ data: undefined, isLoading: false })),
    };
});

// Mock notification hook
vi.mock('./shared/hooks/useAnnouncementNotifier', () => ({
    useAnnouncementNotifier: vi.fn(),
}));

// Mock Topbar to simplify rendering
vi.mock('./components/Topbar', () => ({ default: () => <div data-testid='topbar'>Topbar</div> }));

// Mock system banner
vi.mock('./components/system-banner/system-banner', () => ({ default: () => null }));

// Mock notification banner
vi.mock('./shared/notification/notification', () => ({ default: () => null }));

// Mock confirmation modal
vi.mock('./shared/modal/confirmation-modal', () => ({ default: () => null }));

// Mock breadcrumbs
vi.mock('./shared/breadcrumb/breadcrumbs', () => ({ Breadcrumbs: () => null }));
vi.mock('./shared/breadcrumb/breadcrumbs-change-listener', () => ({ default: () => null }));

// Helper to create selector mock for different role combinations
type RoleMockConfig = {
    isAdmin?: boolean;
    isUser?: boolean;
    isRagAdmin?: boolean;
    isApiUser?: boolean;
};

const createSelectorMock = (roles: RoleMockConfig) => {
    return (selector: any) => {
        if (selector === selectCurrentUserIsAdmin) return roles.isAdmin ?? false;
        if (selector === selectCurrentUserIsRagAdmin) return roles.isRagAdmin ?? false;
        if (selector === selectCurrentUserIsUser) return roles.isUser ?? false;
        if (selector === selectCurrentUserIsApiUser) return roles.isApiUser ?? false;
        if (selector === selectCurrentUsername) return 'Test User';
        // Inline selectors (e.g., confirmationModal) — return safe defaults
        return null;
    };
};

const mockStore = configureStore({
    reducer: {
        user: () => ({ info: undefined }),
        modal: () => ({ confirmationModal: null }),
    },
});

const renderApp = (route: string) => {
    return render(
        <Provider store={mockStore}>
            <MemoryRouter initialEntries={[route]}>
                <App />
            </MemoryRouter>
        </Provider>
    );
};

describe('Route Guards', () => {
    beforeEach(async () => {
        vi.clearAllMocks();
        (window as any).env = {
            ...window.env,
            RAG_ENABLED: true,
            HOSTED_MCP_ENABLED: false,
        };
    });

    describe('RagAdminRoute (/repository-management)', () => {
        it('renders children when user isRagAdmin', async () => {
            const { useAuth } = await import('./auth/useAuth');
            (useAuth as any).mockReturnValue({ isAuthenticated: true, isLoading: false });

            const { useAppSelector } = await import('./config/store');
            (useAppSelector as any).mockImplementation(createSelectorMock({ isRagAdmin: true }));

            renderApp('/repository-management');
            expect(await screen.findByTestId('repo-management-page')).toBeInTheDocument();
        });

        it('renders children when user isAdmin', async () => {
            const { useAuth } = await import('./auth/useAuth');
            (useAuth as any).mockReturnValue({ isAuthenticated: true, isLoading: false });

            const { useAppSelector } = await import('./config/store');
            (useAppSelector as any).mockImplementation(createSelectorMock({ isAdmin: true }));

            renderApp('/repository-management');
            expect(await screen.findByTestId('repo-management-page')).toBeInTheDocument();
        });

        it('redirects when user is regular user', async () => {
            const { useAuth } = await import('./auth/useAuth');
            (useAuth as any).mockReturnValue({ isAuthenticated: true, isLoading: false });

            const { useAppSelector } = await import('./config/store');
            (useAppSelector as any).mockImplementation(createSelectorMock({ isUser: true }));

            renderApp('/repository-management');
            expect(screen.queryByTestId('repo-management-page')).not.toBeInTheDocument();
        });
    });

    describe('PrivateRoute (/ai-assistant)', () => {
        it('renders children when user isRagAdmin', async () => {
            const { useAuth } = await import('./auth/useAuth');
            (useAuth as any).mockReturnValue({ isAuthenticated: true, isLoading: false });

            const { useAppSelector } = await import('./config/store');
            (useAppSelector as any).mockImplementation(createSelectorMock({ isRagAdmin: true }));

            renderApp('/ai-assistant');
            expect(await screen.findByTestId('chatbot-page')).toBeInTheDocument();
        });
    });

    describe('AdminRoute (/model-management)', () => {
        it('blocks rag-admin from admin-only routes', async () => {
            const { useAuth } = await import('./auth/useAuth');
            (useAuth as any).mockReturnValue({ isAuthenticated: true, isLoading: false });

            const { useAppSelector } = await import('./config/store');
            (useAppSelector as any).mockImplementation(createSelectorMock({ isRagAdmin: true }));

            renderApp('/model-management');
            expect(screen.queryByTestId('model-management-page')).not.toBeInTheDocument();
        });
    });
});

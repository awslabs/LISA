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
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useAuth } from '../auth/useAuth';
import { MemoryRouter } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';

import Topbar from './Topbar';
import ColorSchemeContext from '@/shared/color-scheme.provider';
import { Mode } from '@cloudscape-design/global-styles';
import {
    selectCurrentUserIsAdmin,
    selectCurrentUserIsRagAdmin,
    selectCurrentUserIsApiUser,
    selectCurrentUsername,
} from '@/shared/reducers/user.reducer';

// Mock the auth abstraction
vi.mock('../auth/useAuth');

// Mock store functions - use selector reference matching
vi.mock('@/config/store', () => ({
    useAppDispatch: vi.fn(() => vi.fn()),
    useAppSelector: vi.fn(),
}));

const mockAuth = {
    isAuthenticated: true,
    signoutRedirect: vi.fn(),
    signinRedirect: vi.fn(),
    removeUser: vi.fn(),
    signoutSilent: vi.fn(),
};

const mockStore = configureStore({
    reducer: {
        user: () => ({
            currentUser: {
                isAdmin: false,
                isApiUser: false,
                name: 'Test User',
            },
        }),
    },
});

const mockColorSchemeContext = {
    colorScheme: Mode.Light,
    setColorScheme: vi.fn(),
};

const renderTopbar = (props = {}) => {
    return render(
        <Provider store={mockStore}>
            <MemoryRouter>
                <ColorSchemeContext.Provider value={mockColorSchemeContext}>
                    <Topbar {...props} />
                </ColorSchemeContext.Provider>
            </MemoryRouter>
        </Provider>
    );
};

describe('Topbar', () => {
    beforeEach(async () => {
        vi.clearAllMocks();
        (useAuth as any).mockReturnValue(mockAuth);

        // Set default selector mock (regular user, no admin roles)
        const storeModule = await import('@/config/store');
        (storeModule.useAppSelector as any).mockImplementation((selector: any) => {
            if (selector === selectCurrentUserIsAdmin) return false;
            if (selector === selectCurrentUserIsRagAdmin) return false;
            if (selector === selectCurrentUserIsApiUser) return false;
            if (selector === selectCurrentUsername) return 'Test User';
            return null;
        });

        // Mock window.env
        (window as any).env = {
            CLIENT_ID: 'test-client-id',
            AUTHORITY: 'https://test-authority.com',
        };
    });

    it('calls signoutRedirect when sign out is clicked', async () => {
        const user = userEvent.setup();

        renderTopbar();

        const userButton = screen.getByRole('button', { expanded: false });
        await user.click(userButton);
        await user.click(screen.getByText('Sign out'));

        expect(mockAuth.signoutRedirect).toHaveBeenCalledOnce();
    });

    it('shows Administration with only RAG Management for rag-admin user', async () => {
        const storeModule = await import('@/config/store');
        (storeModule.useAppSelector as any).mockImplementation((selector: any) => {
            if (selector === selectCurrentUserIsAdmin) return false;
            if (selector === selectCurrentUserIsRagAdmin) return true;
            if (selector === selectCurrentUserIsApiUser) return false;
            if (selector === selectCurrentUsername) return 'RAG Admin User';
            return null;
        });
        (window as any).env = {
            ...window.env,
            RAG_ENABLED: true,
        };

        const user = userEvent.setup();
        renderTopbar();

        // Should see Administration dropdown (Cloudscape renders duplicate text in collapsed/expanded views)
        const adminDropdowns = screen.getAllByText('Administration');
        expect(adminDropdowns.length).toBeGreaterThan(0);

        // Click to open dropdown
        await user.click(adminDropdowns[0]);

        // Should see RAG Management
        expect(screen.getByText('RAG Management')).toBeInTheDocument();

        // Should NOT see admin-only items
        expect(screen.queryByText('Configuration')).not.toBeInTheDocument();
        expect(screen.queryByText('Model Management')).not.toBeInTheDocument();
        expect(screen.queryByText('API Token Management')).not.toBeInTheDocument();
    });

    it('shows all admin items for admin user', async () => {
        const storeModule = await import('@/config/store');
        (storeModule.useAppSelector as any).mockImplementation((selector: any) => {
            if (selector === selectCurrentUserIsAdmin) return true;
            if (selector === selectCurrentUserIsRagAdmin) return false;
            if (selector === selectCurrentUserIsApiUser) return false;
            if (selector === selectCurrentUsername) return 'Admin User';
            return null;
        });
        (window as any).env = {
            ...window.env,
            RAG_ENABLED: true,
        };

        const user = userEvent.setup();
        renderTopbar();

        // Cloudscape TopNavigation renders duplicate text in collapsed/expanded views
        const adminDropdowns = screen.getAllByText('Administration');
        expect(adminDropdowns.length).toBeGreaterThan(0);
        await user.click(adminDropdowns[0]);

        expect(screen.getByText('Configuration')).toBeInTheDocument();
        expect(screen.getByText('Model Management')).toBeInTheDocument();
        expect(screen.getByText('RAG Management')).toBeInTheDocument();
        expect(screen.getByText('API Token Management')).toBeInTheDocument();
    });

    it('hides Administration for rag-admin when RAG_ENABLED is false', async () => {
        const storeModule = await import('@/config/store');
        (storeModule.useAppSelector as any).mockImplementation((selector: any) => {
            if (selector === selectCurrentUserIsAdmin) return false;
            if (selector === selectCurrentUserIsRagAdmin) return true;
            if (selector === selectCurrentUserIsApiUser) return false;
            if (selector === selectCurrentUsername) return 'RAG Admin User';
            return null;
        });
        (window as any).env = {
            ...window.env,
            RAG_ENABLED: false,
        };

        renderTopbar();
        expect(screen.queryByText('Administration')).not.toBeInTheDocument();
    });

    it('hides Administration for regular user', () => {
        // Default mock already returns isAdmin=false, isRagAdmin=false
        renderTopbar();
        expect(screen.queryByText('Administration')).not.toBeInTheDocument();
    });

    it('calls signinRedirect when sign in is clicked for unauthenticated user', async () => {
        const user = userEvent.setup();

        // Mock unauthenticated state
        (useAuth as any).mockReturnValue({
            ...mockAuth,
            isAuthenticated: false,
        });

        renderTopbar();

        // Click the user profile dropdown button
        const userButton = screen.getByRole('button', { expanded: false });
        await user.click(userButton);

        // Click the sign in option
        await user.click(screen.getByText('Sign in'));

        // Verify that signinRedirect was called with correct redirect_uri (no hash, per OAuth spec)
        const { getRedirectUri } = await import('@/config/oidc.config');
        expect(mockAuth.signinRedirect).toHaveBeenCalledWith({
            redirect_uri: getRedirectUri(),
        });
    });

});

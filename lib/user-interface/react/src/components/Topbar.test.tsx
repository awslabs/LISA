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

// Mock the auth abstraction
vi.mock('../auth/useAuth');

// Mock store functions
vi.mock('@/config/store', () => ({
    useAppDispatch: vi.fn(() => vi.fn()),
    useAppSelector: vi.fn((selector) => {
        const selectorStr = selector.toString();
        if (selectorStr.includes('selectCurrentUserIsAdmin')) return false;
        if (selectorStr.includes('selectCurrentUserIsApiUser')) return false;
        if (selectorStr.includes('selectCurrentUsername')) return 'Test User';
        return null;
    }),
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
    beforeEach(() => {
        vi.clearAllMocks();
        (useAuth as any).mockReturnValue(mockAuth);

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

        // Verify that signinRedirect was called with correct redirect_uri
        expect(mockAuth.signinRedirect).toHaveBeenCalledWith({
            redirect_uri: window.location.toString(),
        });
    });

});

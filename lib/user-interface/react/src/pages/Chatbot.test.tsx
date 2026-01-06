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
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useAuth } from 'react-oidc-context';

import { Chatbot } from './Chatbot';

// Mock all the dependencies
vi.mock('react-oidc-context');
vi.mock('@/config/store', () => ({
    useAppDispatch: () => vi.fn(),
}));
vi.mock('@/shared/reducers/session.reducer', () => ({
    sessionApi: {
        util: {
            invalidateTags: vi.fn(),
        },
    },
}));
vi.mock('@/components/chatbot/Chat', () => ({
    default: ({ sessionId }: { sessionId?: string }) => (
        <div data-testid='chat-component' data-session-id={sessionId || ''}>
            Chat Component
        </div>
    )
}));

vi.mock('@/components/chatbot/components/Sessions', () => ({
    default: ({ newSession }: { newSession: () => void }) => (
        <div data-testid='sessions-component'>
            <button onClick={newSession} data-testid='new-session-button'>
                New Session
            </button>
        </div>
    )
}));

const mockAuth = {
    user: {
        profile: {
            sub: 'test-user-id'
        }
    }
};

const createMockStore = () => configureStore({
    reducer: {
        // Minimal store for testing
        test: (state = {}) => state,
    },
});

describe('Chatbot', () => {
    const mockSetNav = vi.fn();

    const renderWithRouter = (initialEntry: string) => {
        return render(
            <Provider store={createMockStore()}>
                <MemoryRouter initialEntries={[initialEntry]}>
                    <Routes>
                        <Route path="/ai-assistant" element={<Chatbot setNav={mockSetNav} />} />
                        <Route path="/ai-assistant/:sessionId" element={<Chatbot setNav={mockSetNav} />} />
                    </Routes>
                </MemoryRouter>
            </Provider>
        );
    };

    beforeEach(() => {
        vi.clearAllMocks();
        (useAuth as any).mockReturnValue(mockAuth);
    });

    it('renders Chat component with correct sessionId from URL', () => {
        renderWithRouter('/ai-assistant/test-session-123');

        const chatComponent = screen.getByTestId('chat-component');
        expect(chatComponent).toHaveAttribute('data-session-id', 'test-session-123');
    });

    it('renders Chat component without sessionId for new session', () => {
        renderWithRouter('/ai-assistant');

        const chatComponent = screen.getByTestId('chat-component');
        expect(chatComponent).toHaveAttribute('data-session-id', '');
    });

    it('re-renders Chat component when navigating between sessions', () => {
        // Test with sessionId first
        const { unmount } = renderWithRouter('/ai-assistant/existing-session');

        let chatComponent = screen.getByTestId('chat-component');
        expect(chatComponent).toHaveAttribute('data-session-id', 'existing-session');

        // Unmount and render with different route
        unmount();
        renderWithRouter('/ai-assistant');

        // Component should render with empty sessionId
        chatComponent = screen.getByTestId('chat-component');
        expect(chatComponent).toHaveAttribute('data-session-id', '');
    });

    it('calls setNav with Sessions component', () => {
        renderWithRouter('/ai-assistant');

        expect(mockSetNav).toHaveBeenCalledTimes(1);

        // Verify that setNav was called with a React element
        const setNavCall = mockSetNav.mock.calls[0][0];
        expect(setNavCall).toBeDefined();
        expect(setNavCall.type).toBeDefined(); // Should be a React component
    });
});

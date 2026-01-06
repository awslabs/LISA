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
import { MemoryRouter } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useAuth } from 'react-oidc-context';

import { Chatbot } from './Chatbot';

// Mock all the dependencies
vi.mock('react-oidc-context');
vi.mock('@/components/chatbot/Chat', () => ({
    default: ({ sessionId, key }: { sessionId?: string; key: string }) => (
        <div data-testid='chat-component' data-session-id={sessionId} data-key={key}>
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

    beforeEach(() => {
        vi.clearAllMocks();
        (useAuth as any).mockReturnValue(mockAuth);
    });

    it('renders Chat component with correct sessionId from URL', () => {
        render(
            <Provider store={createMockStore()}>
                <MemoryRouter initialEntries={['/ai-assistant/test-session-123']}>
                    <Chatbot setNav={mockSetNav} />
                </MemoryRouter>
            </Provider>
        );

        const chatComponent = screen.getByTestId('chat-component');
        expect(chatComponent).toHaveAttribute('data-session-id', 'test-session-123');
    });

    it('renders Chat component without sessionId for new session', () => {
        render(
            <Provider store={createMockStore()}>
                <MemoryRouter initialEntries={['/ai-assistant']}>
                    <Chatbot setNav={mockSetNav} />
                </MemoryRouter>
            </Provider>
        );

        const chatComponent = screen.getByTestId('chat-component');
        expect(chatComponent).toHaveAttribute('data-session-id', '');
    });

    it('updates Chat component key when navigating to new session', () => {
        const { rerender } = render(
            <Provider store={createMockStore()}>
                <MemoryRouter initialEntries={['/ai-assistant/existing-session']}>
                    <Chatbot setNav={mockSetNav} />
                </MemoryRouter>
            </Provider>
        );

        const chatComponent = screen.getByTestId('chat-component');
        const initialKey = chatComponent.getAttribute('data-key');

        // Simulate navigation to new session (no sessionId)
        rerender(
            <Provider store={createMockStore()}>
                <MemoryRouter initialEntries={['/ai-assistant']}>
                    <Chatbot setNav={mockSetNav} />
                </MemoryRouter>
            </Provider>
        );

        // Key should have changed (forcing remount) when sessionId becomes undefined
        const updatedChatComponent = screen.getByTestId('chat-component');
        const newKey = updatedChatComponent.getAttribute('data-key');

        expect(newKey).not.toBe(initialKey);
        expect(updatedChatComponent).toHaveAttribute('data-session-id', '');
    });

    it('calls setNav with Sessions component', () => {
        render(
            <Provider store={createMockStore()}>
                <MemoryRouter initialEntries={['/ai-assistant']}>
                    <Chatbot setNav={mockSetNav} />
                </MemoryRouter>
            </Provider>
        );

        expect(mockSetNav).toHaveBeenCalledTimes(1);
        // Verify that Sessions component was passed to setNav
        expect(screen.getByTestId('sessions-component')).toBeInTheDocument();
    });
});

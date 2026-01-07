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

import { renderHook, act } from '@testing-library/react';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useAuth } from 'react-oidc-context';

import { useSession } from './useSession.hooks';
import breadcrumbsReducer from '@/shared/reducers/breadcrumbs.reducer';

// Mock react-oidc-context
vi.mock('react-oidc-context');

// Mock uuid
vi.mock('uuid', () => ({
    v4: () => 'test-session-id-123'
}));

const mockAuth = {
    user: {
        profile: {
            sub: 'test-user-id'
        }
    }
};

const mockGetSessionById = vi.fn();

const createMockStore = () => configureStore({
    reducer: {
        breadcrumbs: breadcrumbsReducer,
    },
});

const wrapper = ({ children }: { children: React.ReactNode }) => (
    <Provider store={createMockStore()}>
        {children}
    </Provider>
);

describe('useSession', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        (useAuth as any).mockReturnValue(mockAuth);
    });

    it('creates new session when sessionId is undefined', async () => {
        const { result } = renderHook(
            () => useSession(undefined, mockGetSessionById),
            { wrapper }
        );

        await act(async () => {
            // Wait for useEffect to complete
            await new Promise((resolve) => setTimeout(resolve, 0));
        });

        expect(result.current.session.sessionId).toBe('test-session-id-123');
        expect(result.current.session.history).toEqual([]);
        expect(result.current.session.userId).toBe('test-user-id');
        expect(result.current.loadingSession).toBe(false);
    });

    it('loads existing session when sessionId is provided', async () => {
        const mockSession = {
            sessionId: 'existing-session-id',
            history: [{ type: 'human', content: 'test message' }],
            userId: 'test-user-id',
            startTime: '2024-01-01T00:00:00.000Z',
            configuration: {
                selectedModel: { modelId: 'test-model' },
                ragConfig: { repositoryId: 'test-repo' }
            }
        };

        mockGetSessionById.mockResolvedValue({ data: mockSession });

        const { result } = renderHook(
            () => useSession('existing-session-id', mockGetSessionById),
            { wrapper }
        );

        // Initially loading
        expect(result.current.loadingSession).toBe(true);

        // Wait for session to load
        await act(async () => {
            await new Promise((resolve) => setTimeout(resolve, 0));
        });

        expect(mockGetSessionById).toHaveBeenCalledWith('existing-session-id');
        expect(result.current.session.sessionId).toBe('existing-session-id');
        expect(result.current.session.history).toEqual(mockSession.history);
        expect(result.current.loadingSession).toBe(false);
    });

    it('creates new session when transitioning from existing session to undefined', async () => {
        const { result, rerender } = renderHook(
            ({ sessionId }) => useSession(sessionId, mockGetSessionById),
            {
                wrapper,
                initialProps: { sessionId: 'existing-session-id' }
            }
        );

        await act(async () => {
            // Wait for initial useEffect
            await new Promise((resolve) => setTimeout(resolve, 0));
        });

        // Initially has existing session ID
        expect(result.current.internalSessionId).toBe('existing-session-id');

        // Transition to new session (sessionId becomes undefined)
        await act(async () => {
            rerender({ sessionId: undefined });
            // Wait for useEffect to complete
            await new Promise((resolve) => setTimeout(resolve, 0));
        });

        // Should create new session immediately (no cache interference)
        expect(result.current.session.sessionId).toBe('test-session-id-123');
        expect(result.current.session.history).toEqual([]);
        expect(result.current.internalSessionId).toBe('test-session-id-123');
    });

    it('does not reload session if sessionId has not changed', async () => {
        const { rerender } = renderHook(
            ({ sessionId }) => useSession(sessionId, mockGetSessionById),
            {
                wrapper,
                initialProps: { sessionId: 'same-session-id' }
            }
        );

        await act(async () => {
            // Wait for initial useEffect
            await new Promise((resolve) => setTimeout(resolve, 0));
        });

        // Clear the mock call count
        mockGetSessionById.mockClear();

        // Re-render with same sessionId
        await act(async () => {
            rerender({ sessionId: 'same-session-id' });
            await new Promise((resolve) => setTimeout(resolve, 0));
        });

        // Should not call getSessionById again
        expect(mockGetSessionById).not.toHaveBeenCalled();
    });

    it('always creates fresh session when sessionId is undefined (no cache persistence)', () => {
        // First render with undefined sessionId
        const { result: result1, unmount } = renderHook(
            () => useSession(undefined, mockGetSessionById),
            { wrapper }
        );

        const firstSessionId = result1.current.session.sessionId;
        expect(firstSessionId).toBe('test-session-id-123');

        // Unmount and remount (simulating new session button click)
        unmount();

        const { result: result2 } = renderHook(
            () => useSession(undefined, mockGetSessionById),
            { wrapper }
        );

        // Should create a new session (not restore from cache)
        expect(result2.current.session.sessionId).toBe('test-session-id-123');
        expect(result2.current.session.history).toEqual([]);
    });
});

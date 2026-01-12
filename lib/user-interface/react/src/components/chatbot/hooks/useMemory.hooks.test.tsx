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

import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useAuth } from 'react-oidc-context';

import { useMemory } from './useMemory.hooks';
import { LisaChatSession } from '@/components/types';
import { IChatConfiguration } from '@/shared/model/chat.configurations.model';
import { IModel } from '@/shared/model/model-management.model';
import { ChatMemory } from '@/shared/util/chat-memory';

vi.mock('react-oidc-context');

const createMockSession = (overrides?: Partial<LisaChatSession>): LisaChatSession => ({
    sessionId: 'test-session-id',
    history: [],
    userId: 'test-user',
    startTime: '2024-01-01T00:00:00.000Z',
    ...overrides,
});

const createMockChatConfiguration = (overrides?: Partial<IChatConfiguration['sessionConfiguration']>): IChatConfiguration => ({
    sessionConfiguration: {
        chatHistoryBufferSize: 10,
        max_tokens: 1024,
        modelArgs: {},
        ...overrides,
    },
} as IChatConfiguration);

const createMockModel = (overrides?: Partial<IModel>): IModel => ({
    modelId: 'test-model',
    modelName: 'Test Model',
    features: [],
    ...overrides,
} as IModel);

const mockNotificationService = {
    generateNotification: vi.fn(),
};

describe('useMemory', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        (useAuth as ReturnType<typeof vi.fn>).mockReturnValue({
            isAuthenticated: true,
            user: { profile: { sub: 'test-user' } },
        });
    });

    it('creates memory with correct configuration from session and chat config', () => {
        const session = createMockSession();
        const chatConfig = createMockChatConfiguration({ chatHistoryBufferSize: 15 });

        const { result } = renderHook(() =>
            useMemory(session, chatConfig, undefined, '', '', mockNotificationService)
        );

        expect(result.current.memory).toBeInstanceOf(ChatMemory);
        expect(result.current.memory.k).toBe(15);
        expect(result.current.memory.memoryKey).toBe('history');
        expect(result.current.memory.returnMessages).toBe(false);
    });

    it('updates memory when session changes', () => {
        const session1 = createMockSession({ sessionId: 'session-1' });
        const session2 = createMockSession({ sessionId: 'session-2' });
        const chatConfig = createMockChatConfiguration();

        const { result, rerender } = renderHook(
            ({ session }) => useMemory(session, chatConfig, undefined, '', '', mockNotificationService),
            { initialProps: { session: session1 } }
        );

        const firstMemory = result.current.memory;

        rerender({ session: session2 });

        expect(result.current.memory).not.toBe(firstMemory);
    });

    it('updates memory when buffer size changes', () => {
        const session = createMockSession();
        const chatConfig1 = createMockChatConfiguration({ chatHistoryBufferSize: 10 });
        const chatConfig2 = createMockChatConfiguration({ chatHistoryBufferSize: 20 });

        const { result, rerender } = renderHook(
            ({ chatConfig }) => useMemory(session, chatConfig, undefined, '', '', mockNotificationService),
            { initialProps: { chatConfig: chatConfig1 } }
        );

        expect(result.current.memory.k).toBe(10);

        rerender({ chatConfig: chatConfig2 });

        expect(result.current.memory.k).toBe(20);
    });

    it('does not recreate memory when unrelated props change', async () => {
        const session = createMockSession();
        const chatConfig = createMockChatConfiguration();
        const model = createMockModel();

        const { result, rerender } = renderHook(
            ({ userPrompt }) => useMemory(session, chatConfig, model, userPrompt, '', mockNotificationService),
            { initialProps: { userPrompt: 'initial prompt' } }
        );

        await act(async () => {
            await new Promise((resolve) => setTimeout(resolve, 0));
        });

        const firstMemory = result.current.memory;

        await act(async () => {
            rerender({ userPrompt: 'updated prompt' });
        });

        expect(result.current.memory).toBe(firstMemory);
    });

    it('updates metadata when model and auth are available', async () => {
        const session = createMockSession();
        const chatConfig = createMockChatConfiguration({ max_tokens: 2048, modelArgs: { temperature: 0.7 } });
        const model = createMockModel({ modelId: 'claude-v2' });

        const { result } = renderHook(() =>
            useMemory(session, chatConfig, model, '', '', mockNotificationService)
        );

        await waitFor(() => {
            expect(result.current.metadata.modelName).toBe('claude-v2');
        });

        expect(result.current.metadata.modelKwargs).toEqual({
            max_tokens: 2048,
            modelKwargs: { temperature: 0.7 },
        });
    });

    it('does not update metadata when not authenticated', async () => {
        (useAuth as ReturnType<typeof vi.fn>).mockReturnValue({
            isAuthenticated: false,
            user: null,
        });

        const session = createMockSession();
        const chatConfig = createMockChatConfiguration();
        const model = createMockModel();

        const { result } = renderHook(() =>
            useMemory(session, chatConfig, model, '', '', mockNotificationService)
        );

        await act(async () => {
            await new Promise((resolve) => setTimeout(resolve, 50));
        });

        expect(result.current.metadata).toEqual({});
    });

    it('shows notification when model without image support receives image context', async () => {
        const session = createMockSession();
        const chatConfig = createMockChatConfiguration();
        const modelWithoutImageSupport = createMockModel({ features: [] });

        await act(async () => {
            renderHook(() =>
                useMemory(
                    session,
                    chatConfig,
                    modelWithoutImageSupport,
                    '',
                    'File context: data:image/png;base64,abc123',
                    mockNotificationService
                )
            );
        });

        expect(mockNotificationService.generateNotification).toHaveBeenCalledWith(
            'Removed file from context as new model doesn\'t support image input',
            'info'
        );
    });

    it('does not show notification when model supports image input', async () => {
        const session = createMockSession();
        const chatConfig = createMockChatConfiguration();
        const modelWithImageSupport = createMockModel({
            features: [{ name: 'imageInput' }],
        });

        await act(async () => {
            renderHook(() =>
                useMemory(
                    session,
                    chatConfig,
                    modelWithImageSupport,
                    '',
                    'File context: data:image/png;base64,abc123',
                    mockNotificationService
                )
            );
        });

        expect(mockNotificationService.generateNotification).not.toHaveBeenCalled();
    });

    it('does not show notification when file context is not an image', async () => {
        const session = createMockSession();
        const chatConfig = createMockChatConfiguration();
        const modelWithoutImageSupport = createMockModel({ features: [] });

        await act(async () => {
            renderHook(() =>
                useMemory(
                    session,
                    chatConfig,
                    modelWithoutImageSupport,
                    '',
                    'File context: some text content',
                    mockNotificationService
                )
            );
        });

        expect(mockNotificationService.generateNotification).not.toHaveBeenCalled();
    });
});

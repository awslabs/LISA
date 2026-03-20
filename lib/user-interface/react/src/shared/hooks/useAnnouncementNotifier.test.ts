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

import { renderHook } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { configureStore } from '@reduxjs/toolkit';
import { Provider } from 'react-redux';
import React from 'react';

import { useAnnouncementNotifier } from '@/shared/hooks/useAnnouncementNotifier';
import notificationReducer from '@/shared/reducers/notification.reducer';
import { selectNotifications } from '@/shared/reducers/notification.reducer';
import { IConfiguration } from '@/shared/model/configuration.model';
import * as announcementDismissal from '@/shared/util/announcementDismissal';

vi.mock('@/shared/util/announcementDismissal', () => ({
    shouldShowAnnouncement: vi.fn(),
    setDismissedTimestamp: vi.fn(),
    getDismissedTimestamp: vi.fn(),
    clearDismissedTimestamp: vi.fn(),
    DISMISSAL_KEY: 'lisa-announcement-dismissed-at',
}));

function createTestStore () {
    return configureStore({
        reducer: { notification: notificationReducer },
        middleware: (getDefaultMiddleware) =>
            getDefaultMiddleware({ serializableCheck: false }),
    });
}

function createWrapper (store: ReturnType<typeof createTestStore>) {
    return function Wrapper ({ children }: { children: React.ReactNode }) {
        return React.createElement(Provider, { store }, children);
    };
}

function buildConfig (overrides: {
    isEnabled?: boolean;
    message?: string;
    createdAt?: string;
} = {}): IConfiguration {
    return {
        configScope: 'system',
        versionId: 1,
        createdAt: overrides.createdAt ?? '2025-01-01T00:00:00Z',
        changedBy: 'test-user',
        changeReason: 'test',
        configuration: {
            systemBanner: { isEnabled: false, text: '', textColor: '#000', backgroundColor: '#fff' },
            enabledComponents: {
                deleteSessionHistory: true,
                viewMetaData: true,
                editKwargs: true,
                editPromptTemplate: true,
                editNumOfRagDocument: true,
                editChatHistoryBuffer: true,
                uploadRagDocs: true,
                ragSelectionAvailable: true,
                uploadContextDocs: true,
                documentSummarization: true,
                showRagLibrary: true,
                showPromptTemplateLibrary: true,
                enableModelComparisonUtility: false,
                mcpConnections: true,
                awsSessions: true,
                showMcpWorkbench: false,
                modelLibrary: true,
                encryptSession: false,
                enableUserApiTokens: false,
                chatAssistantStacks: false,
            },
            global: { defaultModel: '' },
            announcement: {
                isEnabled: overrides.isEnabled ?? true,
                message: overrides.message ?? 'System maintenance tonight',
            },
        },
    };
}

describe('useAnnouncementNotifier', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('generates a notification when announcement is enabled and should be shown', () => {
        vi.mocked(announcementDismissal.shouldShowAnnouncement).mockReturnValue(true);
        const store = createTestStore();

        renderHook(() => useAnnouncementNotifier(buildConfig()), {
            wrapper: createWrapper(store),
        });

        const notifications = selectNotifications(store.getState());
        expect(notifications).toHaveLength(1);
        expect(notifications[0]).toMatchObject({
            id: 'announcement-notification',
            header: '📢 Announcement: System maintenance tonight',
            type: 'info',
            dismissible: true,
        });
    });

    it('does not generate a notification when config is undefined', () => {
        const store = createTestStore();

        renderHook(() => useAnnouncementNotifier(undefined), {
            wrapper: createWrapper(store),
        });

        expect(selectNotifications(store.getState())).toHaveLength(0);
    });

    it('does not generate a notification when isEnabled is false', () => {
        vi.mocked(announcementDismissal.shouldShowAnnouncement).mockReturnValue(true);
        const store = createTestStore();

        renderHook(() => useAnnouncementNotifier(buildConfig({ isEnabled: false })), {
            wrapper: createWrapper(store),
        });

        expect(selectNotifications(store.getState())).toHaveLength(0);
    });

    it('does not generate a notification when message is empty', () => {
        vi.mocked(announcementDismissal.shouldShowAnnouncement).mockReturnValue(true);
        const store = createTestStore();

        renderHook(() => useAnnouncementNotifier(buildConfig({ message: '' })), {
            wrapper: createWrapper(store),
        });

        expect(selectNotifications(store.getState())).toHaveLength(0);
    });

    it('does not generate a notification when announcement was already dismissed', () => {
        vi.mocked(announcementDismissal.shouldShowAnnouncement).mockReturnValue(false);
        const store = createTestStore();

        renderHook(() => useAnnouncementNotifier(buildConfig()), {
            wrapper: createWrapper(store),
        });

        expect(selectNotifications(store.getState())).toHaveLength(0);
    });

    it('clears existing notification when announcement becomes disabled', () => {
        vi.mocked(announcementDismissal.shouldShowAnnouncement).mockReturnValue(true);
        const store = createTestStore();
        const wrapper = createWrapper(store);

        const { rerender } = renderHook(
            ({ config }) => useAnnouncementNotifier(config),
            {
                wrapper,
                initialProps: { config: buildConfig() as IConfiguration | undefined },
            },
        );

        expect(selectNotifications(store.getState())).toHaveLength(1);

        rerender({ config: buildConfig({ isEnabled: false }) });

        expect(selectNotifications(store.getState())).toHaveLength(0);
    });

    it('passes createdAt to shouldShowAnnouncement', () => {
        vi.mocked(announcementDismissal.shouldShowAnnouncement).mockReturnValue(true);
        const store = createTestStore();
        const config = buildConfig({ createdAt: '2025-06-15T12:00:00Z' });

        renderHook(() => useAnnouncementNotifier(config), {
            wrapper: createWrapper(store),
        });

        expect(announcementDismissal.shouldShowAnnouncement).toHaveBeenCalledWith('2025-06-15T12:00:00Z');
    });
});

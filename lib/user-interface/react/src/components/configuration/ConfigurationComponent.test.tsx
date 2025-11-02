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
import { ConfigurationComponent } from './ConfigurationComponent';
import { renderWithProviders } from '../../test/helpers/render';
import { configurationApi } from '../../shared/reducers/configuration.reducer';
import { mcpServerApi } from '../../shared/reducers/mcp-server.reducer';

// Mock axios to prevent actual API calls
vi.mock('axios', () => {
    return {
        default: {
            create: vi.fn(() => ({
                interceptors: {
                    request: { use: vi.fn(), eject: vi.fn() },
                    response: { use: vi.fn(), eject: vi.fn() },
                },
            })),
            isAxiosError: vi.fn(() => false),
        },
    };
});

// Mock the notification service
vi.mock('../../shared/util/hooks', () => ({
    useNotificationService: vi.fn(() => ({
        generateNotification: vi.fn(),
    })),
}));

// Mock the modal reducer
vi.mock('../../shared/reducers/modal.reducer', () => ({
    default: vi.fn(() => ({})),
    setConfirmationModal: vi.fn(),
    dismissModal: vi.fn(),
}));

// Mock the validation hook
vi.mock('../../shared/validation', () => ({
    scrollToInvalid: vi.fn(),
    useValidationReducer: vi.fn(() => ({
        state: {
            validateAll: false,
            touched: {},
            formSubmitting: false,
            form: {
                enabledComponents: {},
                systemBanner: {
                    isEnabled: false,
                    text: '',
                    textColor: '',
                    backgroundColor: '',
                },
            },
        },
        setState: vi.fn(),
        setFields: vi.fn(),
        touchFields: vi.fn(),
        errors: {},
        isValid: true,
    })),
}));

describe('ConfigurationComponent without RepositoryTable', () => {
    const mockConfigData = [{
        configuration: {
            enabledComponents: {},
            systemBanner: {
                isEnabled: false,
                text: '',
                textColor: '',
                backgroundColor: '',
            },
        },
        versionId: 1,
    }];

    const getPreloadedState = () => ({
        [configurationApi.reducerPath]: {
            queries: {
                'getConfiguration("global")': {
                    status: 'fulfilled',
                    endpointName: 'getConfiguration',
                    requestId: 'test-request-id',
                    data: mockConfigData,
                    startedTimeStamp: Date.now(),
                    fulfilledTimeStamp: Date.now(),
                },
            },
            mutations: {},
            provided: {},
            subscriptions: {},
            config: {
                online: true,
                focused: true,
                middlewareRegistered: true,
                refetchOnFocus: false,
                refetchOnReconnect: false,
                refetchOnMountOrArgChange: false,
                keepUnusedDataFor: 60,
                reducerPath: 'configuration',
            },
        },
        user: {
            currentUser: {
                username: 'testuser',
            },
        },
    });

    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('should render without RepositoryTable', async () => {
        renderWithProviders(<ConfigurationComponent />, {
            apis: [configurationApi, mcpServerApi],
            preloadedState: getPreloadedState(),
        });

        await waitFor(() => {
            expect(screen.getByText('LISA App Configuration')).toBeInTheDocument();
        });

        // Should NOT have repository-related headers
        expect(screen.queryByText('RAG Repository Configuration')).not.toBeInTheDocument();
        expect(screen.queryByText('Repositories')).not.toBeInTheDocument();
    });

    it('should display system configuration settings', async () => {
        renderWithProviders(<ConfigurationComponent />, {
            apis: [configurationApi, mcpServerApi],
            preloadedState: getPreloadedState(),
        });

        await waitFor(() => {
            expect(screen.getByText('LISA App Configuration')).toBeInTheDocument();
            expect(screen.getByText('The current configuration of LISA')).toBeInTheDocument();
        });
    });

    it('should have Save Changes button', async () => {
        renderWithProviders(<ConfigurationComponent />, {
            apis: [configurationApi, mcpServerApi],
            preloadedState: getPreloadedState(),
        });

        await waitFor(() => {
            expect(screen.getByText('Save Changes')).toBeInTheDocument();
        });
    });

    it('should display ActivatedUserComponents section', async () => {
        renderWithProviders(<ConfigurationComponent />, {
            apis: [configurationApi, mcpServerApi],
            preloadedState: getPreloadedState(),
        });

        await waitFor(() => {
            // ActivatedUserComponents should be rendered
            expect(screen.getByText('LISA App Configuration')).toBeInTheDocument();
        });
    });

    it('should display SystemBannerConfiguration section', async () => {
        renderWithProviders(<ConfigurationComponent />, {
            apis: [configurationApi, mcpServerApi],
            preloadedState: getPreloadedState(),
        });

        await waitFor(() => {
            // SystemBannerConfiguration should be rendered
            expect(screen.getByText('LISA App Configuration')).toBeInTheDocument();
        });
    });
});

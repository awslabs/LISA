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

import '@testing-library/jest-dom';
import { cleanup } from '@testing-library/react';
import { afterEach, vi } from 'vitest';

// Mock Axios to prevent real HTTP requests during tests
vi.mock('axios', async (importOriginal) => {
    const actual = await importOriginal<typeof import('axios')>();
    return {
        ...actual,
        default: {
            ...actual.default,
            create: vi.fn(() => ({
                interceptors: {
                    request: { use: vi.fn() },
                    response: { use: vi.fn() },
                },
                get: vi.fn().mockResolvedValue({ data: {} }),
                post: vi.fn().mockResolvedValue({ data: {} }),
                put: vi.fn().mockResolvedValue({ data: {} }),
                delete: vi.fn().mockResolvedValue({ data: {} }),
                request: vi.fn().mockResolvedValue({ data: {} }),
            })),
        },
    };
});

// Cleanup after each test
afterEach(() => {
    cleanup();
});

// Mock window.env for API configuration
Object.defineProperty(window, 'env', {
    writable: true,
    value: {
        RESTAPI_URI: 'http://localhost:8080',
        RESTAPI_VERSION: 'v2',
        API_BASE_URL: 'http://localhost:8080/v2',
        AUTHORITY: 'http://localhost:8080',
        CLIENT_ID: 'test-client-id',
    },
});

// Mock window.matchMedia
Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
    })),
});

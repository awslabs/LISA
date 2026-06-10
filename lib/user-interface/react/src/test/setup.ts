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

// Node 25 ships an experimental built-in `localStorage` global that is just
// an empty object (it expects `--localstorage-file=<path>`). jsdom can't
// install its own Storage on the opaque-origin window we get under vitest,
// so Node's stub wins and `localStorage.getItem` ends up undefined. Install
// a real in-memory Storage shim on both `window` and `globalThis` so code
// under test sees a working API.
const createStorageShim = (): Storage => {
    const store = new Map<string, string>();
    return {
        get length () {
            return store.size;
        },
        clear: () => store.clear(),
        getItem: (key) => (store.has(key) ? store.get(key)! : null),
        setItem: (key, value) => {
            store.set(String(key), String(value));
        },
        removeItem: (key) => {
            store.delete(key);
        },
        key: (index) => Array.from(store.keys())[index] ?? null,
    };
};

for (const target of [globalThis, globalThis.window]) {
    Object.defineProperty(target, 'localStorage', {
        configurable: true,
        writable: true,
        value: createStorageShim(),
    });
    Object.defineProperty(target, 'sessionStorage', {
        configurable: true,
        writable: true,
        value: createStorageShim(),
    });
}

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
        MCP_WORKBENCH_URI: 'http://localhost:8080',
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

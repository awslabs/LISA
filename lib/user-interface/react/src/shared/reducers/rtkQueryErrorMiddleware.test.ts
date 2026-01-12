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
import { configureStore } from '@reduxjs/toolkit';
import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';
import { rtkQueryErrorMiddleware } from './rtkQueryErrorMiddleware';

describe('rtkQueryErrorMiddleware', () => {
    let store: ReturnType<typeof configureStore>;
    let testApi: ReturnType<typeof createApi>;
    let consoleDebugSpy: ReturnType<typeof vi.spyOn>;

    beforeEach(() => {
        // Clear all mocks before each test
        vi.clearAllMocks();

        // Spy on console.debug to verify logging
        consoleDebugSpy = vi.spyOn(console, 'debug').mockImplementation(() => {});

        // Create a test API
        testApi = createApi({
            reducerPath: 'testApi',
            baseQuery: fetchBaseQuery({ baseUrl: 'http://test.com' }),
            endpoints: (builder) => ({
                getTest: builder.query<{ data: string }, void>({
                    query: () => '/test',
                }),
            }),
        });

        // Create store with our middleware
        store = configureStore({
            reducer: {
                [testApi.reducerPath]: testApi.reducer,
            },
            middleware: (getDefaultMiddleware) =>
                getDefaultMiddleware()
                    .concat(rtkQueryErrorMiddleware)
                    .concat(testApi.middleware),
        });
    });

    it('should pass through non-error actions', () => {
        const action = { type: 'SOME_ACTION', payload: 'test' };
        const next = vi.fn();
        const middleware = rtkQueryErrorMiddleware(store)(next);

        middleware(action);

        expect(next).toHaveBeenCalledWith(action);
        expect(consoleDebugSpy).not.toHaveBeenCalled();
    });

    it('should detect and log AbortError from string error', () => {
        const action = {
            type: 'testApi/executeQuery/rejected',
            error: {
                name: 'AbortError',
                message: 'The user aborted a request',
            },
            meta: {
                arg: {
                    endpointName: 'getTest',
                },
            },
        };

        const next = vi.fn();
        const middleware = rtkQueryErrorMiddleware(store)(next);

        middleware(action);

        expect(next).toHaveBeenCalledWith(action);
        expect(consoleDebugSpy).toHaveBeenCalledWith(
            '[RTK Query] Detected cancelled request:',
            'getTest'
        );
    });

    it('should detect AbortError from Error object', () => {
        const abortError = new Error('Request aborted');
        abortError.name = 'AbortError';

        const action = {
            type: 'testApi/executeQuery/rejected',
            error: abortError,
            meta: {
                arg: {
                    endpointName: 'getTest',
                },
            },
        };

        const next = vi.fn();
        const middleware = rtkQueryErrorMiddleware(store)(next);

        middleware(action);

        expect(next).toHaveBeenCalledWith(action);
        expect(consoleDebugSpy).toHaveBeenCalledWith(
            '[RTK Query] Detected cancelled request:',
            'getTest'
        );
    });

    it('should detect abort from error message containing "abort"', () => {
        const action = {
            type: 'testApi/executeQuery/rejected',
            error: new Error('The operation was aborted'),
            meta: {
                arg: {
                    endpointName: 'getTest',
                },
            },
        };

        const next = vi.fn();
        const middleware = rtkQueryErrorMiddleware(store)(next);

        middleware(action);

        expect(next).toHaveBeenCalledWith(action);
        expect(consoleDebugSpy).toHaveBeenCalledWith(
            '[RTK Query] Detected cancelled request:',
            'getTest'
        );
    });

    it('should not log for non-abort errors', () => {
        const action = {
            type: 'testApi/executeQuery/rejected',
            error: {
                name: 'NetworkError',
                message: 'Network error',
            },
            meta: {
                arg: {
                    endpointName: 'getTest',
                },
            },
        };

        const next = vi.fn();
        const middleware = rtkQueryErrorMiddleware(store)(next);

        middleware(action);

        expect(next).toHaveBeenCalledWith(action);
        expect(consoleDebugSpy).not.toHaveBeenCalled();
    });

    it('should handle actions without error payload', () => {
        const action = {
            type: 'testApi/executeQuery/rejected',
            payload: {},
            meta: {
                arg: {
                    endpointName: 'getTest',
                },
            },
            error: { message: 'Rejected' },
        };

        const next = vi.fn();
        const middleware = rtkQueryErrorMiddleware(store)(next);

        middleware(action);

        expect(next).toHaveBeenCalledWith(action);
        expect(consoleDebugSpy).not.toHaveBeenCalled();
    });

    it('should handle actions without meta', () => {
        const action = {
            type: 'testApi/executeQuery/rejected',
            error: {
                name: 'AbortError',
                message: 'Aborted',
            },
        };

        const next = vi.fn();
        const middleware = rtkQueryErrorMiddleware(store)(next);

        middleware(action);

        expect(next).toHaveBeenCalledWith(action);
        // Should still log but with undefined endpoint name
        expect(consoleDebugSpy).toHaveBeenCalledWith(
            '[RTK Query] Detected cancelled request:',
            undefined
        );
    });
});

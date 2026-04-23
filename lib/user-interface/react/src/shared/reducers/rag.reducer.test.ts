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
import { ragApi } from './rag.reducer';

// Capture the URL that lisaAxios is called with
const mockAxios = vi.fn().mockResolvedValue({ data: [] });
vi.mock('./reducer.utils', () => ({
    lisaBaseQuery: () => async (config: any) => {
        mockAxios(config);
        return { data: [] };
    },
}));

function createTestStore () {
    return configureStore({
        reducer: {
            [ragApi.reducerPath]: ragApi.reducer,
        },
        middleware: (getDefaultMiddleware) =>
            getDefaultMiddleware().concat(ragApi.middleware),
    });
}

describe('getRelevantDocuments query builder', () => {
    beforeEach(() => {
        mockAxios.mockClear();
    });

    it('includes searchMode=hybrid in the request URL when searchMode is hybrid', async () => {
        const store = createTestStore();
        store.dispatch(
            ragApi.endpoints.getRelevantDocuments.initiate({
                repositoryId: 'repo-1',
                query: 'test query',
                topK: 3,
                searchMode: 'hybrid',
            })
        );

        await vi.waitFor(() => {
            expect(mockAxios).toHaveBeenCalled();
        });

        const config = mockAxios.mock.calls[0][0];
        expect(config.url).toContain('searchMode=hybrid');
    });

    it('does not include searchMode in the request URL when searchMode is absent', async () => {
        const store = createTestStore();
        store.dispatch(
            ragApi.endpoints.getRelevantDocuments.initiate({
                repositoryId: 'repo-1',
                query: 'test query',
                topK: 3,
            })
        );

        await vi.waitFor(() => {
            expect(mockAxios).toHaveBeenCalled();
        });

        const config = mockAxios.mock.calls[0][0];
        expect(config.url).not.toContain('searchMode');
    });
});

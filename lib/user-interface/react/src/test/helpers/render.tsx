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

import { ReactElement } from 'react';
import { render, RenderOptions } from '@testing-library/react';
import { Provider } from 'react-redux';
import { configureStore, PreloadedState } from '@reduxjs/toolkit';
import User from '../../shared/reducers/user.reducer';
import { ragApi } from '../../shared/reducers/rag.reducer';

interface ExtendedRenderOptions extends Omit<RenderOptions, 'queries'> {
    preloadedState?: PreloadedState<any>;
    store?: any;
    apis?: any[];
}

export function renderWithProviders(
    ui: ReactElement,
    {
        preloadedState = {},
        apis = [],
        store = configureStore({
            reducer: {
                user: User,
                [ragApi.reducerPath]: ragApi.reducer,
                ...apis.reduce((acc, api) => {
                    acc[api.reducerPath] = api.reducer;
                    return acc;
                }, {}),
            },
            middleware: (getDefaultMiddleware) =>
                apis.reduce(
                    (middleware, api) => middleware.concat(api.middleware),
                    getDefaultMiddleware().concat(ragApi.middleware)
                ),
            preloadedState,
        }),
        ...renderOptions
    }: ExtendedRenderOptions = {}
) {
    function Wrapper({ children }: { children: React.ReactNode }) {
        return <Provider store={store}>{children}</Provider>;
    }

    return { store, ...render(ui, { wrapper: Wrapper, ...renderOptions }) };
}

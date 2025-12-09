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

import { createApi } from '@reduxjs/toolkit/query/react';
import { lisaBaseQuery } from './reducer.utils';
import { normalizeError } from '../util/validationUtils';

export type McpServerPreferences = {
    id: string;
    name: string;
    enabled: boolean;
    disabledTools: string[];
    autoApprovedTools: string[];
};

export type McpPreferences = {
    overrideAllApprovals: boolean;
    enabledServers: McpServerPreferences[];
};

export type Preferences = {
    mcp?: McpPreferences;
};

export type UserPreferences = {
    user: string;
    preferences: Preferences;
};

export const DefaultUserPreferences: UserPreferences = {
    user: '',
    preferences: {},
};

export const userPreferencesApi = createApi({
    reducerPath: 'userPreferences',
    baseQuery: lisaBaseQuery(),
    tagTypes: ['user-preferences'],
    refetchOnFocus: true,
    refetchOnMountOrArgChange: true,
    endpoints: (builder) => ({
        updateUserPreferences: builder.mutation<UserPreferences, UserPreferences>({
            query: (userPreferences) => ({
                url: '/user-preferences',
                method: 'PUT',
                data: userPreferences
            }),
            transformErrorResponse: (baseQueryReturnValue) => normalizeError('Update User Preferences', baseQueryReturnValue),
            invalidatesTags: ['user-preferences'],
        }),
        getUserPreferences: builder.query<UserPreferences, void>({
            query () {
                return {
                    url: '/user-preferences',
                    method: 'GET'
                };
            },
            providesTags: ['user-preferences']
        }),
    })

});

export const {
    useUpdateUserPreferencesMutation,
    useGetUserPreferencesQuery,
} = userPreferencesApi;

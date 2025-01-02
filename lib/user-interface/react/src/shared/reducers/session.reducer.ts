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
import { LisaChatMessageFields, LisaChatSession } from '../../components/types';

export const sessionApi = createApi({
    reducerPath: 'sessions',
    baseQuery: lisaBaseQuery(),
    tagTypes: ['sessions'],
    refetchOnFocus: true,
    refetchOnReconnect: true,
    endpoints: (builder) => ({
        getSessionById: builder.query<LisaChatSession, String>({
            query: (sessionId: String) => ({
                url: `/session/${sessionId}`
            }),
        }),
        getSessionHealth: builder.query<any, void>({
            query: () => ({
                url: `${window.env.RESTAPI_URI}health`
            }),
        }),
        listSessions: builder.query<LisaChatSession[], void>({
            query: () => ({
                url: '/session'
            }),
            providesTags:['sessions'],
        }),
        updateSession: builder.mutation<LisaChatSession, LisaChatSession>({
            query: (session) => ({
                url: `/session/${session.sessionId}`,
                method: 'PUT',
                data: {
                    messages: session.history.map((elem) => {
                        const message: LisaChatMessageFields = {
                            content: elem.content,
                            type: elem.type,
                            metadata: elem.metadata,
                        };
                        return message;
                    }),
                }
            }),
            transformErrorResponse: (baseQueryReturnValue) => {
                // transform into SerializedError
                return {
                    name: 'Update Session Error',
                    message: baseQueryReturnValue.data?.type === 'RequestValidationError' ? baseQueryReturnValue.data.detail.map((error) => error.msg).join(', ') : baseQueryReturnValue.data.message
                };
            },
            invalidatesTags: ['sessions'],
        }),
        deleteSessionById: builder.mutation<LisaChatSession, String>({
            query: (sessionId: String) => ({
                url: `/session/${sessionId}`,
                method: 'DELETE',
            }),
            transformErrorResponse: (baseQueryReturnValue) => {
                // transform into SerializedError
                return {
                    name: 'Delete Session Error',
                    message: baseQueryReturnValue.data?.type === 'RequestValidationError' ? baseQueryReturnValue.data.detail.map((error) => error.msg).join(', ') : baseQueryReturnValue.data.message
                };
            },
            invalidatesTags: ['sessions'],
        }),
        deleteAllSessionsForUser: builder.mutation<LisaChatSession, void>({
            query: () => ({
                url: '/session',
                method: 'DELETE',
            }),
            transformErrorResponse: (baseQueryReturnValue) => {
                // transform into SerializedError
                return {
                    name: 'Delete Session Error',
                    message: baseQueryReturnValue.data?.type === 'RequestValidationError' ? baseQueryReturnValue.data.detail.map((error) => error.msg).join(', ') : baseQueryReturnValue.data.message
                };
            },
            invalidatesTags: ['sessions'],
        }),
    }),
});

export const {
    useListSessionsQuery,
    useDeleteSessionByIdMutation,
    useDeleteAllSessionsForUserMutation,
    useUpdateSessionMutation,
    useLazyGetSessionByIdQuery,
    useGetSessionHealthQuery
} = sessionApi;

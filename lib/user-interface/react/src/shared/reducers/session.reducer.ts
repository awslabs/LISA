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
import {
    LisaAttachImageRequest,
    LisaAttachImageResponse,
    LisaChatMessageFields,
    LisaChatSession
} from '../../components/types';
import { RESTAPI_URI } from '../../components/utils';

/**
 * Extract error message from API response
 */
const extractErrorMessage = (baseQueryReturnValue: any): string => {
    let message = 'Unknown error';
    if (baseQueryReturnValue.data) {
        if (baseQueryReturnValue.data.type === 'RequestValidationError') {
            message = baseQueryReturnValue.data.detail.map((error: any) => error.msg).join(', ');
        } else if (typeof baseQueryReturnValue.data === 'string') {
            message = baseQueryReturnValue.data;
        } else if (baseQueryReturnValue.data.message) {
            message = baseQueryReturnValue.data.message;
        }
    }
    return message;
};

export const sessionApi = createApi({
    reducerPath: 'sessions',
    baseQuery: lisaBaseQuery(),
    tagTypes: ['sessions', 'session'],
    refetchOnFocus: true,
    refetchOnMountOrArgChange: true,
    endpoints: (builder) => ({
        getSessionById: builder.query<LisaChatSession, string>({
            query: (sessionId: string) => ({
                url: `/session/${sessionId}`
            }),
            // Provide specific tags for individual sessions
            providesTags: (result, error, sessionId) => [
                { type: 'session', id: sessionId }
            ],
        }),
        getSessionHealth: builder.query<any, void>({
            query: () => ({
                url: `${RESTAPI_URI}/health`
            }),
        }),
        listSessions: builder.query<LisaChatSession[], void>({
            query: () => ({
                url: '/session'
            }),
            // Simple tag for session list
            providesTags: ['sessions'],
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
                            toolCalls: elem.toolCalls,
                            usage: elem.usage,
                            guardrailTriggered: elem.guardrailTriggered,
                        };
                        return message;
                    }),
                    configuration: session.configuration,
                    name: session.name
                }
            }),
            transformErrorResponse: (baseQueryReturnValue) => ({
                name: 'Update Session Error',
                message: extractErrorMessage(baseQueryReturnValue)
            }),
            // Invalidate session list (for updated metadata) and specific session details
            invalidatesTags: (result, error, session) => [
                'sessions',
                { type: 'session', id: session.sessionId }
            ],
        }),
        updateSessionName: builder.mutation<LisaChatSession, { sessionId: string, name: string }>({
            query: (session) => ({
                url: `/session/${session.sessionId}/name`,
                method: 'PUT',
                data: {
                    name: session.name
                }
            }),
            // Only invalidate the specific session and session list
            invalidatesTags: (result, error, { sessionId }) => [
                'sessions',
                { type: 'session', id: sessionId }
            ],
            transformErrorResponse: (baseQueryReturnValue) => ({
                name: 'Rename Session Error',
                message: extractErrorMessage(baseQueryReturnValue)
            }),
        }),
        attachImageToSession: builder.mutation<LisaAttachImageResponse, LisaAttachImageRequest>({
            query: (attachImageRequest) => ({
                url: `/session/${attachImageRequest.sessionId}/attachImage`,
                method: 'PUT',
                data: {
                    message: attachImageRequest.message
                }
            }),
            transformErrorResponse: (baseQueryReturnValue) => ({
                name: 'Attach Image to Session Error',
                message: extractErrorMessage(baseQueryReturnValue)
            }),
            // Only invalidate the specific session
            invalidatesTags: (result, error, { sessionId }) => [
                { type: 'session', id: sessionId }
            ],
        }),
        deleteSessionById: builder.mutation<LisaChatSession, string>({
            query: (sessionId: string) => ({
                url: `/session/${sessionId}`,
                method: 'DELETE',
            }),
            transformErrorResponse: (baseQueryReturnValue) => ({
                name: 'Delete Session Error',
                message: extractErrorMessage(baseQueryReturnValue)
            }),
            // Invalidate session list and the specific session
            invalidatesTags: (result, error, sessionId) => [
                'sessions',
                { type: 'session', id: sessionId }
            ],
        }),
        deleteAllSessionsForUser: builder.mutation<LisaChatSession, void>({
            query: () => ({
                url: '/session',
                method: 'DELETE',
            }),
            transformErrorResponse: (baseQueryReturnValue) => ({
                name: 'Delete All Sessions Error',
                message: extractErrorMessage(baseQueryReturnValue)
            }),
            // Invalidate everything when deleting all sessions
            invalidatesTags: ['sessions', 'session'],
        }),
    }),
});

export const {
    useListSessionsQuery,
    useDeleteSessionByIdMutation,
    useDeleteAllSessionsForUserMutation,
    useUpdateSessionMutation,
    useUpdateSessionNameMutation,
    useLazyGetSessionByIdQuery,
    useGetSessionHealthQuery,
    useAttachImageToSessionMutation
} = sessionApi;

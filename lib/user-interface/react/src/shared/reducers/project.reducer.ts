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
import { LisaProject } from '../model/project.model';

export const projectApi = createApi({
    reducerPath: 'projects',
    baseQuery: lisaBaseQuery(),
    tagTypes: ['projects'],
    endpoints: (builder) => ({
        listProjects: builder.query<LisaProject[], void>({
            query: () => ({ url: '/project' }),
            providesTags: ['projects'],
        }),
        createProject: builder.mutation<LisaProject, { name: string }>({
            query: (body) => ({ url: '/project', method: 'POST', data: body }),
            invalidatesTags: ['projects'],
        }),
        renameProject: builder.mutation<void, { projectId: string; name: string }>({
            query: ({ projectId, name }) => ({
                url: `/project/${projectId}`,
                method: 'PUT',
                data: { name },
            }),
            invalidatesTags: ['projects'],
        }),
        deleteProject: builder.mutation<void, { projectId: string; deleteSessions: boolean }>({
            query: ({ projectId, deleteSessions }) => ({
                url: `/project/${projectId}`,
                method: 'DELETE',
                data: { deleteSessions },
            }),
            invalidatesTags: ['projects'],
        }),
    }),
});

export const {
    useListProjectsQuery,
    useCreateProjectMutation,
    useRenameProjectMutation,
    useDeleteProjectMutation,
} = projectApi;

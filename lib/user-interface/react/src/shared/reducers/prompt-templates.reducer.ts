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

export enum PromptTemplateType {
    Persona = 'persona',
    Directive = 'directive'
}

export type PromptTemplate = {
    id: string;
    created: string;
    owner: string;
    groups: string[];
    title: string;
    revision: number;
    latest?: boolean;
    body: string;
    type: PromptTemplateType;
    isOwner?: true;
};

export type NewPromptTemplate = Partial<PromptTemplate> & Pick<PromptTemplate, | 'groups' | 'title' | 'body' | 'type'>;

export const DefaultPromptTemplate: NewPromptTemplate = {
    groups: [],
    title: '',
    body: '',
    type: PromptTemplateType.Persona
};

export type PromptTemplateListResponse = {
    Items: PromptTemplate[],
};

export const promptTemplateApi = createApi({
    reducerPath: 'promptTemplates',
    baseQuery: lisaBaseQuery(),
    tagTypes: ['promptTemplates'],
    refetchOnFocus: true,
    refetchOnReconnect: true,
    endpoints: (builder) => ({
        createPromptTemplate: builder.mutation<PromptTemplate, NewPromptTemplate>({
            query: (promptTemplate) => ({
                url: '/prompt-templates',
                method: 'POST',
                data: promptTemplate
            }),
            transformErrorResponse: (baseQueryReturnValue) => normalizeError('Create Prompt Template', baseQueryReturnValue),
            invalidatesTags: ['promptTemplates'],
        }),
        getPromptTemplate: builder.query<PromptTemplate, string>({
            query (promptTemplateId) {
                return {
                    url: `/prompt-templates/${promptTemplateId}`,
                    method: 'GET'
                };
            },
            providesTags: ['promptTemplates']
        }),
        listPromptTemplates: builder.query<PromptTemplateListResponse, {showPublic: boolean}>({
            query ({showPublic}) {
                const queryStringParameters = new URLSearchParams();
                queryStringParameters.append('public', String(showPublic));

                return {
                    url: `/prompt-templates?${queryStringParameters.toString()}`,
                    method: 'GET'
                };
            },
            providesTags: ['promptTemplates']
        }),
        updatePromptTemplate: builder.mutation<PromptTemplate, PromptTemplate>({
            query: (promptTemplate) => ({
                url: `/prompt-templates/${promptTemplate.id}`,
                method: 'PUT',
                data: promptTemplate
            }),
            transformErrorResponse: (baseQueryReturnValue) => normalizeError('Update Prompt Template', baseQueryReturnValue),
            invalidatesTags: ['promptTemplates'],
        }),
        deletePromptTemplate: builder.mutation<any, string>({
            query: (promptTemplateId) => ({
                url: `/prompt-templates/${promptTemplateId}`,
                method: 'DELETE',
            }),
            invalidatesTags: ['promptTemplates']
        })
    })

});

export const {
    useCreatePromptTemplateMutation,
    useLazyGetPromptTemplateQuery,
    useListPromptTemplatesQuery,
    useUpdatePromptTemplateMutation,
    useDeletePromptTemplateMutation,
} = promptTemplateApi;

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

import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import { DEFAULT_WORKFLOW_TEMPLATES, Workflow, WorkflowTemplate } from '@/shared/model/workflow.model';

type WorkflowState = {
    templates: WorkflowTemplate[];
    workflows: Workflow[];
};

const initialState: WorkflowState = {
    templates: DEFAULT_WORKFLOW_TEMPLATES,
    workflows: []
};

type CreateWorkflowPayload = {
    id: string;
    name: string;
    templateId: string;
    createdAt?: string;
};

export const Workflow = createSlice({
    name: 'workflow',
    initialState,
    reducers: {
        createWorkflowFromResponse: (state, action: PayloadAction<CreateWorkflowPayload>) => {
            const template = state.templates.find((item) => item.id === action.payload.templateId);
            if (!template) {
                return;
            }

            state.workflows.unshift({
                id: action.payload.id,
                name: action.payload.name.trim(),
                templateId: template.id,
                templateName: template.name,
                createdAt: action.payload.createdAt ?? new Date().toISOString()
            });
        }
    }
});

export const selectWorkflowTemplates = (state: any) => state.workflow.templates;
export const selectWorkflows = (state: any) => state.workflow.workflows;

export const { createWorkflowFromResponse } = Workflow.actions;

export default Workflow.reducer;

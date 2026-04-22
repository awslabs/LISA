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

import { Alert, Box, Container, Header, SpaceBetween, Table } from '@cloudscape-design/components';
import { useState } from 'react';
import { useAppDispatch, useAppSelector } from '@/config/store';
import {
    createWorkflowFromResponse,
    selectWorkflows,
    selectWorkflowTemplates
} from '@/shared/reducers/workflow.reducer';
import WorkflowForm from '@/components/workflows/WorkflowForm';
import { formatDate } from '@/shared/util/formats';
import { lisaAxios } from '@/shared/reducers/reducer.utils';

type CreateWorkflowResponse = {
    workflowId?: string;
    id?: string;
    name?: string;
    templateId?: string;
    template?: string;
    createdAt?: string;
    created?: string;
};

export function WorkflowManagementComponent () {
    const dispatch = useAppDispatch();
    const templates = useAppSelector(selectWorkflowTemplates);
    const workflows = useAppSelector(selectWorkflows);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [createError, setCreateError] = useState<string | null>(null);

    return (
        <SpaceBetween size='l'>
            <Container
                header={<Header variant='h2'>Template Catalog</Header>}
                data-testid='workflow-template-catalog'
            >
                <WorkflowForm
                    templates={templates}
                    isSubmitting={isSubmitting}
                    onSubmit={async ({ name, templateId }) => {
                        setIsSubmitting(true);
                        setCreateError(null);
                        try {
                            const submittedName = name.trim();
                            const { data } = await lisaAxios.post<CreateWorkflowResponse>('/workflows', {
                                name: submittedName,
                                templateId
                            });

                            const id = data.workflowId ?? data.id;
                            const responseTemplateId = data.templateId ?? data.template ?? templateId;
                            if (!id) {
                                setCreateError('Failed to create workflow. Please try again.');
                                return;
                            }
                            dispatch(createWorkflowFromResponse({
                                id,
                                name: data.name?.trim() || submittedName,
                                templateId: responseTemplateId,
                                createdAt: data.createdAt ?? data.created
                            }));
                        } catch {
                            setCreateError('Failed to create workflow. Please try again.');
                        } finally {
                            setIsSubmitting(false);
                        }
                    }}
                />
                {createError ? (
                    <Alert type='error' data-testid='workflow-create-error'>
                        {createError}
                    </Alert>
                ) : null}
            </Container>
            <Table
                variant='full-page'
                items={workflows}
                trackBy='id'
                header={<Header counter={`(${workflows.length})`}>Workflows</Header>}
                empty={
                    <Box textAlign='center' color='inherit'>
                        No workflows created yet.
                    </Box>
                }
                columnDefinitions={[
                    { id: 'name', header: 'Name', cell: (item) => item.name },
                    { id: 'templateName', header: 'Template', cell: (item) => item.templateName },
                    { id: 'createdAt', header: 'Created', cell: (item) => formatDate(item.createdAt) }
                ]}
            />
        </SpaceBetween>
    );
}

export default WorkflowManagementComponent;

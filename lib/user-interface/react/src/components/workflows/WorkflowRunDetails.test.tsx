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

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { WorkflowRunDetails } from './WorkflowRunDetails';

describe('WorkflowRunDetails', () => {
    it('renders run id, state, and workflow name/id fields', () => {
        render(
            <WorkflowRunDetails
                run={{
                    runId: 'run-123',
                    workflowId: 'order-approval-workflow',
                    state: 'RUNNING',
                    currentStep: 'validate-request',
                    approvalToken: 'token-123',
                }}
            />
        );

        expect(screen.getByTestId('workflow-run-id')).toHaveTextContent('run-123');
        expect(screen.getByText('RUNNING')).toBeInTheDocument();
        expect(screen.getByText('Workflow ID')).toBeInTheDocument();
        expect(screen.getByText('order-approval-workflow')).toBeInTheDocument();
    });
});

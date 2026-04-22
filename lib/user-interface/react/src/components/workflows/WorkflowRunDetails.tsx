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

import { Box, ColumnLayout, Container, Header, SpaceBetween, StatusIndicator } from '@cloudscape-design/components';
import React from 'react';

export type WorkflowRunDetailsData = {
    runId: string;
    workflowId?: string;
    state: 'WAITING_APPROVAL' | 'RUNNING' | 'SUCCEEDED' | 'FAILED';
    currentStep?: string;
    approvalToken?: string;
};

type WorkflowRunDetailsProps = {
    run: WorkflowRunDetailsData;
};

export function WorkflowRunDetails ({ run }: WorkflowRunDetailsProps): React.ReactElement {
    const statusType = run.state === 'FAILED' ? 'error' : run.state === 'SUCCEEDED' ? 'success' : 'in-progress';

    return (
        <Container header={<Header variant='h2'>Workflow run details</Header>}>
            <SpaceBetween size='m' direction='vertical'>
                <StatusIndicator type={statusType}>{run.state}</StatusIndicator>
                <ColumnLayout columns={2} variant='text-grid'>
                    <div>
                        <Box variant='awsui-key-label'>Run ID</Box>
                        <Box data-testid='workflow-run-id'>{run.runId}</Box>
                    </div>
                    <div>
                        <Box variant='awsui-key-label'>Workflow ID</Box>
                        <Box>{run.workflowId ?? 'Unknown'}</Box>
                    </div>
                    <div>
                        <Box variant='awsui-key-label'>Current step</Box>
                        <Box>{run.currentStep ?? 'N/A'}</Box>
                    </div>
                    <div>
                        <Box variant='awsui-key-label'>Approval token</Box>
                        <Box>{run.approvalToken ?? 'N/A'}</Box>
                    </div>
                </ColumnLayout>
            </SpaceBetween>
        </Container>
    );
}

export default WorkflowRunDetails;

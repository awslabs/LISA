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

import { Button, Header, SpaceBetween, Table, TextContent } from '@cloudscape-design/components';
import React from 'react';

export type ApprovalQueueItem = {
    runId: string;
    approvalToken: string;
    stepName?: string;
    requestedBy?: string;
};

type ApprovalQueueProps = {
    items: ApprovalQueueItem[];
    isLoading?: boolean;
    onApprove: (item: ApprovalQueueItem) => void;
};

export function ApprovalQueue ({ items, isLoading = false, onApprove }: ApprovalQueueProps): React.ReactElement {
    return (
        <Table
            items={items}
            loading={isLoading}
            loadingText='Loading approvals'
            header={<Header counter={items.length ? `(${items.length})` : undefined}>Approval queue</Header>}
            empty={<TextContent><small>No approvals pending.</small></TextContent>}
            columnDefinitions={[
                { id: 'runId', header: 'Run ID', cell: (item) => item.runId },
                { id: 'stepName', header: 'Step', cell: (item) => item.stepName ?? 'Approval step' },
                { id: 'requestedBy', header: 'Requested by', cell: (item) => item.requestedBy ?? 'System' },
                {
                    id: 'actions',
                    header: 'Actions',
                    cell: (item) => (
                        <SpaceBetween direction='horizontal' size='xs'>
                            <Button
                                variant='primary'
                                data-testid={`approval-approve-${item.runId}`}
                                onClick={() => onApprove(item)}
                            >
                                Approve
                            </Button>
                        </SpaceBetween>
                    ),
                },
            ]}
        />
    );
}

export default ApprovalQueue;

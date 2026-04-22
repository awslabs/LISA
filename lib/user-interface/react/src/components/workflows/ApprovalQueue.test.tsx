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
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ApprovalQueue, type ApprovalQueueItem } from './ApprovalQueue';

describe('ApprovalQueue', () => {
    it('renders queue items and calls onApprove with selected item', async () => {
        const user = userEvent.setup();
        const onApprove = vi.fn();
        const items: ApprovalQueueItem[] = [
            {
                runId: 'run-1',
                approvalToken: 'token-1',
                stepName: 'Manager approval',
                requestedBy: 'alice',
            },
            {
                runId: 'run-2',
                approvalToken: 'token-2',
                stepName: 'Security approval',
                requestedBy: 'bob',
            },
        ];

        render(<ApprovalQueue items={items} onApprove={onApprove} />);

        expect(screen.getByText('run-1')).toBeInTheDocument();
        expect(screen.getByText('run-2')).toBeInTheDocument();

        await user.click(screen.getByTestId('approval-approve-run-1'));
        expect(onApprove).toHaveBeenCalledTimes(1);
        expect(onApprove).toHaveBeenCalledWith(items[0]);
    });
});

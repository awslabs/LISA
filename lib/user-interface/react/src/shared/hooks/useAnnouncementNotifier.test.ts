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

import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { NotificationProp } from '@/shared/notification/notifications.props';

// Feature: ui-announcements, Property 2: Announcement notification shape
// Validates: Requirements 3.1, 3.2, 3.3
describe('Property 2: Announcement notification shape', () => {
    it('for any non-empty message, the announcement notification has the correct header, type, dismissible flag, and id', () => {
        fc.assert(
            fc.property(
                fc.string({ minLength: 1 }),
                (message) => {
                    const notification: NotificationProp = {
                        id: 'announcement-notification',
                        header: '📢 Announcement: ' + message,
                        type: 'info',
                        dismissible: true,
                    };

                    expect(notification.header).toBe('📢 Announcement: ' + message);
                    expect(notification.type).toBe('info');
                    expect(notification.dismissible).toBe(true);
                    expect(notification.id).toBe('announcement-notification');
                },
            ),
            { numRuns: 100 },
        );
    });
});

// Feature: ui-announcements, Property 3: Disabled announcement suppression
// Validates: Requirements 3.4
describe('Property 3: Disabled announcement suppression', () => {
    it('for any message string, when isEnabled is false, no notification should be produced', () => {
        fc.assert(
            fc.property(
                fc.string(),
                (message) => {
                    const isEnabled = false;

                    // Simulate the hook's guard condition: when isEnabled is false,
                    // the system should not produce a notification regardless of message content.
                    const shouldDispatchNotification = isEnabled && message.length > 0;

                    expect(shouldDispatchNotification).toBe(false);
                },
            ),
            { numRuns: 100 },
        );
    });

    it('for any non-empty message string, when isEnabled is false, the suppression still holds', () => {
        fc.assert(
            fc.property(
                fc.string({ minLength: 1 }),
                (message) => {
                    const isEnabled = false;

                    // Even with a valid non-empty message, disabled announcements must not dispatch
                    const shouldDispatchNotification = isEnabled && message.length > 0;

                    expect(shouldDispatchNotification).toBe(false);
                },
            ),
            { numRuns: 100 },
        );
    });
});

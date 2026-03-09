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

import { describe, it, expect, beforeEach } from 'vitest';
import * as fc from 'fast-check';
import { setDismissedTimestamp, getDismissedTimestamp, shouldShowAnnouncement } from './announcementDismissal';

// Feature: ui-announcements, Property 4: Dismissal timestamp persistence
// Validates: Requirements 4.1
describe('Property 4: Dismissal timestamp persistence', () => {
    beforeEach(() => {
        localStorage.clear();
    });

    it('setDismissedTimestamp then getDismissedTimestamp returns the same value', () => {
        fc.assert(
            fc.property(
                fc.integer({ min: 1 }),
                (timestamp) => {
                    localStorage.clear();
                    setDismissedTimestamp(timestamp);
                    expect(getDismissedTimestamp()).toBe(timestamp);
                },
            ),
            { numRuns: 100 },
        );
    });
});

// Feature: ui-announcements, Property 5: Announcement visibility based on timestamp comparison
// Validates: Requirements 4.3, 5.1
describe('Property 5: Announcement visibility based on timestamp comparison', () => {
    beforeEach(() => {
        localStorage.clear();
    });

    it('returns false when stored timestamp matches config timestamp', () => {
        fc.assert(
            fc.property(
                fc.integer({ min: 1 }),
                (timestamp) => {
                    localStorage.clear();
                    setDismissedTimestamp(timestamp);
                    expect(shouldShowAnnouncement(timestamp)).toBe(false);
                },
            ),
            { numRuns: 100 },
        );
    });

    it('returns true when stored timestamp differs from config timestamp', () => {
        fc.assert(
            fc.property(
                fc.integer({ min: 1 }),
                fc.integer({ min: 1 }),
                (storedTimestamp, configTimestamp) => {
                    fc.pre(storedTimestamp !== configTimestamp);
                    localStorage.clear();
                    setDismissedTimestamp(storedTimestamp);
                    expect(shouldShowAnnouncement(configTimestamp)).toBe(true);
                },
            ),
            { numRuns: 100 },
        );
    });
});

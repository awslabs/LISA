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
import { announcementConfigSchema } from './configuration.model';

// Feature: ui-announcements, Property 1: Announcement schema validation
// Validates: Requirements 1.1, 1.3
describe('Property 1: Announcement schema validation', () => {
    it('parse succeeds iff !isEnabled || message.length >= 1', () => {
        fc.assert(
            fc.property(
                fc.boolean(),
                fc.string(),
                (isEnabled, message) => {
                    const result = announcementConfigSchema.safeParse({ isEnabled, message });
                    const shouldSucceed = !isEnabled || message.length >= 1;
                    expect(result.success).toBe(shouldSucceed);
                },
            ),
            { numRuns: 100 },
        );
    });

    it('parse fails with error on message path when isEnabled && message === ""', () => {
        fc.assert(
            fc.property(
                fc.constant(true),
                fc.constant(''),
                (isEnabled, message) => {
                    const result = announcementConfigSchema.safeParse({ isEnabled, message });
                    expect(result.success).toBe(false);
                    if (!result.success) {
                        const messageErrors = result.error.issues.filter(
                            (issue) => issue.path.includes('message'),
                        );
                        expect(messageErrors.length).toBeGreaterThanOrEqual(1);
                    }
                },
            ),
            { numRuns: 100 },
        );
    });
});

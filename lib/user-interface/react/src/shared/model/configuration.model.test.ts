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
import { announcementConfigSchema, enabledComponentsSchema } from './configuration.model';

describe('announcementConfigSchema', () => {
    it('accepts when isEnabled is false with empty message', () => {
        const result = announcementConfigSchema.safeParse({ isEnabled: false, message: '' });
        expect(result.success).toBe(true);
    });

    it('accepts when isEnabled is false with non-empty message', () => {
        const result = announcementConfigSchema.safeParse({ isEnabled: false, message: 'hello' });
        expect(result.success).toBe(true);
    });

    it('accepts when isEnabled is true with non-empty message', () => {
        const result = announcementConfigSchema.safeParse({ isEnabled: true, message: 'System maintenance' });
        expect(result.success).toBe(true);
    });

    it('rejects when isEnabled is true with empty message', () => {
        const result = announcementConfigSchema.safeParse({ isEnabled: true, message: '' });
        expect(result.success).toBe(false);
        if (!result.success) {
            const messageErrors = result.error.issues.filter(
                (issue) => issue.path.includes('message'),
            );
            expect(messageErrors.length).toBeGreaterThanOrEqual(1);
        }
    });
});

describe('enabledComponentsSchema', () => {
    it('defaults hybridSearch to false', () => {
        const result = enabledComponentsSchema.parse({});
        expect(result.hybridSearch).toBe(false);
    });

    it('accepts hybridSearch set to true', () => {
        const result = enabledComponentsSchema.parse({ hybridSearch: true });
        expect(result.hybridSearch).toBe(true);
    });
});

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
import { deriveRagSearchMode } from './ragSearchMode';

describe('deriveRagSearchMode', () => {
    it('returns hybrid when no user choice and both flags enabled', () => {
        expect(deriveRagSearchMode(undefined, true, true)).toBe('hybrid');
    });

    it('returns vector when no user choice and hybrid not enabled globally', () => {
        expect(deriveRagSearchMode(undefined, false, true)).toBe('vector');
    });

    it('returns vector when no user choice and repo does not support hybrid', () => {
        expect(deriveRagSearchMode(undefined, true, false)).toBe('vector');
    });

    it('returns vector when no user choice and neither flag enabled', () => {
        expect(deriveRagSearchMode(undefined, false, false)).toBe('vector');
    });

    it('respects explicit user choice of vector even when hybrid available', () => {
        expect(deriveRagSearchMode('vector', true, true)).toBe('vector');
    });

    it('respects explicit user choice of hybrid when both flags enabled', () => {
        expect(deriveRagSearchMode('hybrid', true, true)).toBe('hybrid');
    });

    it('forces vector when admin disables hybrid regardless of user choice', () => {
        expect(deriveRagSearchMode('hybrid', false, true)).toBe('vector');
    });

    it('forces vector when repo does not support hybrid regardless of user choice', () => {
        expect(deriveRagSearchMode('hybrid', true, false)).toBe('vector');
    });

    it('forces vector when both flags false regardless of user choice', () => {
        expect(deriveRagSearchMode('hybrid', false, false)).toBe('vector');
    });
});

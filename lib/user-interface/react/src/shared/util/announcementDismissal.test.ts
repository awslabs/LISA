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
import { setDismissedTimestamp, getDismissedTimestamp, shouldShowAnnouncement, clearDismissedTimestamp } from './announcementDismissal';

describe('announcementDismissal', () => {
    beforeEach(() => {
        localStorage.clear();
    });

    describe('getDismissedTimestamp', () => {
        it('returns null when nothing is stored', () => {
            expect(getDismissedTimestamp()).toBeNull();
        });

        it('returns the stored string value', () => {
            setDismissedTimestamp('1773105679.3095705509185791015625');
            expect(getDismissedTimestamp()).toBe('1773105679.3095705509185791015625');
        });
    });

    describe('setDismissedTimestamp / getDismissedTimestamp roundtrip', () => {
        it('preserves high-precision timestamp strings exactly', () => {
            const timestamp = '1773105679.3095705509185791015625';
            setDismissedTimestamp(timestamp);
            expect(getDismissedTimestamp()).toBe(timestamp);
        });
    });

    describe('clearDismissedTimestamp', () => {
        it('removes the stored value', () => {
            setDismissedTimestamp('123456');
            clearDismissedTimestamp();
            expect(getDismissedTimestamp()).toBeNull();
        });
    });

    describe('shouldShowAnnouncement', () => {
        it('returns true when configTimestamp is undefined', () => {
            expect(shouldShowAnnouncement(undefined)).toBe(true);
        });

        it('returns true when no dismissal is stored', () => {
            expect(shouldShowAnnouncement('1773105679.3095705509185791015625')).toBe(true);
        });

        it('returns false when stored timestamp matches config timestamp', () => {
            const ts = '1773105679.3095705509185791015625';
            setDismissedTimestamp(ts);
            expect(shouldShowAnnouncement(ts)).toBe(false);
        });

        it('returns true when stored timestamp differs from config timestamp', () => {
            setDismissedTimestamp('1772740008.1396915912628173828125');
            expect(shouldShowAnnouncement('1773105679.3095705509185791015625')).toBe(true);
        });
    });
});

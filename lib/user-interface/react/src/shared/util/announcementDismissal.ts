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

export const DISMISSAL_KEY = 'lisa-announcement-dismissed-at';

/**
 * Reads the dismissed announcement timestamp from localStorage.
 * Returns the stored string or null if missing.
 */
export function getDismissedTimestamp (): string | null {
    try {
        return localStorage.getItem(DISMISSAL_KEY);
    } catch {
        return null;
    }
}

/**
 * Writes the dismissed announcement timestamp to localStorage.
 * Fails silently if localStorage is unavailable.
 */
export function setDismissedTimestamp (timestamp: string): void {
    try {
        localStorage.setItem(DISMISSAL_KEY, timestamp);
    } catch {
        // Fail silently when localStorage is unavailable
    }
}

/**
 * Removes the dismissed announcement timestamp from localStorage.
 */
export function clearDismissedTimestamp (): void {
    try {
        localStorage.removeItem(DISMISSAL_KEY);
    } catch {
        // Fail silently when localStorage is unavailable
    }
}

/**
 * Determines whether the announcement should be shown.
 * Returns true if there is no stored dismissal timestamp or if the
 * stored timestamp differs from the provided config timestamp.
 */
export function shouldShowAnnouncement (configTimestamp: string | undefined): boolean {
    if (configTimestamp === undefined) {
        return true;
    }
    const dismissed = getDismissedTimestamp();
    if (dismissed === null) {
        return true;
    }
    return dismissed !== configTimestamp;
}

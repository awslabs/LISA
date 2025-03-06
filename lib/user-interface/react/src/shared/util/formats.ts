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

/**
 * Format date to a short date time format
 * @param date EPOCH date string | number
 */
export function formatDate (date: string | number): string {
    const dateObj = new Date(typeof date === 'string' ? Number.parseInt(date) : date);
    return dateObj.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: 'numeric',
    });
}

/**
 * Format JSON object to a string
 * @param data
 */
export function formatObject (data: object): string {
    return JSON.stringify(data)
        .replaceAll(',', ', ')
        .replaceAll('{', '')
        .replaceAll('}', '')
        .replaceAll('"', '');
}

/**
 * Truncates a string to a specified length, adding an ellipsis ("...") if it exceeds the limit.
 *
 * @param {string} text - The input string to truncate.
 * @param {number} [maxLength=32] - The maximum allowed length of the string, including the ellipsis.
 * @param {string} [truncate_text='...'] - The default truncation text to display.
 * @returns {string} - The truncated string with an ellipsis if necessary.
 */
export function truncateText (text?: string, maxLength = 32, truncate_text: string = '...') {
    if (text === undefined) {
        return text;
    }

    return text.length > maxLength ? text.slice(0, maxLength - 3) + (truncate_text || '') : text;
}
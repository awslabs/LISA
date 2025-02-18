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

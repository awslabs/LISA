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

import { LisaChatMessage, MessageTypes } from '@/components/types';

/**
 * True when the last history entry is an assistant message that requested MCP/tools
 * but those calls have not been executed yet (nothing after this message).
 */
export function sessionHistoryHasPendingAssistantToolCalls (history: LisaChatMessage[]): boolean {
    const last = history.at(-1);
    return Boolean(
        last?.type === MessageTypes.AI &&
        Array.isArray(last.toolCalls) &&
        last.toolCalls.length > 0
    );
}

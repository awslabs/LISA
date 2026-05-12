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

import { describe, expect, it } from 'vitest';
import { LisaChatMessage, MessageTypes } from '@/components/types';
import { sessionHistoryHasPendingAssistantToolCalls } from './sessionPersist.utils';

describe('sessionHistoryHasPendingAssistantToolCalls', () => {
    it('is true when last message is ai with tool calls', () => {
        const history = [
            new LisaChatMessage({ type: MessageTypes.HUMAN, content: 'hi' }),
            new LisaChatMessage({
                type: MessageTypes.AI,
                content: '',
                toolCalls: [{ id: '1', name: 'x', args: {} }],
            }),
        ];
        expect(sessionHistoryHasPendingAssistantToolCalls(history)).toBe(true);
    });

    it('is false when last message is ai without tool calls', () => {
        const history = [
            new LisaChatMessage({ type: MessageTypes.HUMAN, content: 'hi' }),
            new LisaChatMessage({ type: MessageTypes.AI, content: 'ok' }),
        ];
        expect(sessionHistoryHasPendingAssistantToolCalls(history)).toBe(false);
    });

    it('is false when last message is tool', () => {
        const history = [
            new LisaChatMessage({
                type: MessageTypes.AI,
                content: '',
                toolCalls: [{ id: '1', name: 'x', args: {} }],
            }),
            new LisaChatMessage({
                type: MessageTypes.TOOL,
                content: 'result',
                metadata: { toolCallId: '1' } as any,
            }),
        ];
        expect(sessionHistoryHasPendingAssistantToolCalls(history)).toBe(false);
    });
});

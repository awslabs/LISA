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
import { batchMessages, parseSessionImport } from './sessionImport.utils';

const validExport = {
    sessionId: 'abc-123',
    userId: 'someone-else',
    startTime: '2025-01-01T00:00:00Z',
    name: 'My Session',
    history: [
        { type: 'human', content: 'Hello there' },
        { type: 'ai', content: 'Hi! How can I help?', usage: { promptTokens: 3, completionTokens: 5 } },
    ],
    configuration: { selectedModel: { modelId: 'some-model' } },
};

describe('parseSessionImport', () => {
    it('parses a valid session export', () => {
        const parsed = parseSessionImport(JSON.stringify(validExport));
        expect(parsed.messages).toHaveLength(2);
        expect(parsed.messages[0]).toMatchObject({ type: 'human', content: 'Hello there' });
        expect(parsed.messages[1].usage).toEqual({ promptTokens: 3, completionTokens: 5 });
        expect(parsed.name).toBe('My Session (imported)');
        expect(parsed.configuration).toEqual({ selectedModel: { modelId: 'some-model' } });
    });

    it('derives name from first human message when unnamed', () => {
        const data = { ...validExport, name: undefined };
        const parsed = parseSessionImport(JSON.stringify(data));
        expect(parsed.name).toBe('Hello there (imported)');
    });

    it('derives name from complex content when unnamed', () => {
        const data = {
            ...validExport,
            name: undefined,
            history: [{ type: 'human', content: [{ type: 'text', text: 'Complex hello' }] }],
        };
        const parsed = parseSessionImport(JSON.stringify(data));
        expect(parsed.name).toBe('Complex hello (imported)');
    });

    it('strips unknown fields from messages', () => {
        const data = {
            ...validExport,
            history: [{ type: 'human', content: 'hi', lc_kwargs: { evil: true }, additional_kwargs: {} }],
        };
        const parsed = parseSessionImport(JSON.stringify(data));
        expect(parsed.messages[0]).not.toHaveProperty('lc_kwargs');
        expect(parsed.messages[0]).not.toHaveProperty('additional_kwargs');
    });

    it('drops non-object metadata and malformed usage fields', () => {
        const data = {
            ...validExport,
            history: [{
                type: 'ai',
                content: 'hi',
                metadata: 'not-an-object',
                usage: { responseTime: '1.5', promptTokens: 3, completionTokens: Infinity, totalTokens: null },
            }],
        };
        const parsed = parseSessionImport(JSON.stringify(data));
        expect(parsed.messages[0].metadata).toEqual({});
        expect(parsed.messages[0].usage).toEqual({ promptTokens: 3 });
    });

    it('drops usage entirely when nothing valid remains', () => {
        const data = {
            ...validExport,
            history: [
                { type: 'ai', content: 'a', usage: { responseTime: 'fast' } },
                { type: 'ai', content: 'b', usage: ['not', 'an', 'object'] },
            ],
        };
        const parsed = parseSessionImport(JSON.stringify(data));
        expect(parsed.messages[0].usage).toBeUndefined();
        expect(parsed.messages[1].usage).toBeUndefined();
    });

    it('drops array configuration', () => {
        const data = { ...validExport, configuration: [{ selectedModel: 'x' }] };
        const parsed = parseSessionImport(JSON.stringify(data));
        expect(parsed.configuration).toBeUndefined();
    });

    it('rejects invalid JSON', () => {
        expect(() => parseSessionImport('not json {')).toThrow('File is not valid JSON');
    });

    it('rejects non-object payloads', () => {
        expect(() => parseSessionImport('[1, 2]')).toThrow('File does not contain a session object');
        expect(() => parseSessionImport('null')).toThrow('File does not contain a session object');
    });

    it('rejects missing or empty history', () => {
        expect(() => parseSessionImport(JSON.stringify({ name: 'x' }))).toThrow(/non-empty "history"/);
        expect(() => parseSessionImport(JSON.stringify({ history: [] }))).toThrow(/non-empty "history"/);
    });

    it('rejects messages with invalid type', () => {
        const data = { history: [{ type: 'robot', content: 'beep' }] };
        expect(() => parseSessionImport(JSON.stringify(data))).toThrow(/invalid type/);
    });

    it('rejects messages without content', () => {
        const data = { history: [{ type: 'human' }] };
        expect(() => parseSessionImport(JSON.stringify(data))).toThrow(/missing content/);
    });
});

describe('batchMessages', () => {
    const message = (text: string) => ({ type: 'human' as const, content: text });

    it('returns a single batch when under the limit', () => {
        const messages = [message('a'), message('b')];
        expect(batchMessages(messages)).toEqual([messages]);
    });

    it('splits into multiple batches preserving order', () => {
        const messages = [message('aaaa'), message('bbbb'), message('cccc')];
        const perMessageBytes = JSON.stringify(messages[0]).length;
        const batches = batchMessages(messages, perMessageBytes * 2);
        expect(batches).toEqual([
            [messages[0], messages[1]],
            [messages[2]],
        ]);
    });

    it('puts an oversized message in its own batch', () => {
        const messages = [message('small'), message('x'.repeat(500)), message('small2')];
        const batches = batchMessages(messages, 100);
        expect(batches).toEqual([
            [messages[0]],
            [messages[1]],
            [messages[2]],
        ]);
    });

    it('measures UTF-8 bytes rather than string length', () => {
        // '😀' is 1 emoji = 2 UTF-16 code units but 4 UTF-8 bytes.
        const emojiMessage = message('😀😀😀😀');
        const perMessageBytes = new TextEncoder().encode(JSON.stringify(emojiMessage)).length;
        const perMessageCodeUnits = JSON.stringify(emojiMessage).length;
        expect(perMessageBytes).toBeGreaterThan(perMessageCodeUnits);

        // A budget that fits one message by byte count but two by code-unit
        // count must split into two batches.
        const batches = batchMessages([emojiMessage, emojiMessage], perMessageBytes + 1);
        expect(batches).toEqual([[emojiMessage], [emojiMessage]]);
    });

    it('returns no batches for empty input', () => {
        expect(batchMessages([])).toEqual([]);
    });
});

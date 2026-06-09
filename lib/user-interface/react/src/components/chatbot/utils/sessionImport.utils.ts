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

import { LisaChatMessageFields, MessageTypes, UsageInfo } from '@/components/types';

export type ParsedSessionImport = {
    messages: LisaChatMessageFields[];
    name: string;
    configuration?: any;
};

const VALID_MESSAGE_TYPES = new Set<string>(Object.values(MessageTypes));

const isPlainObject = (value: unknown): value is Record<string, any> =>
    Boolean(value) && typeof value === 'object' && !Array.isArray(value);

const USAGE_FIELDS: (keyof UsageInfo)[] = ['completionTokens', 'responseTime', 'promptTokens', 'totalTokens', 'outputTokens'];

/**
 * Rebuild usage from untrusted input, keeping only the known numeric fields.
 * Downstream UI does arithmetic/formatting (e.g. responseTime.toFixed) on
 * these values, so anything non-numeric must be dropped.
 */
const sanitizeUsage = (usage: unknown): UsageInfo | undefined => {
    if (!isPlainObject(usage)) {
        return undefined;
    }
    const sanitized: UsageInfo = {};
    for (const field of USAGE_FIELDS) {
        const value = usage[field];
        if (typeof value === 'number' && Number.isFinite(value)) {
            sanitized[field] = value;
        }
    }
    return Object.keys(sanitized).length > 0 ? sanitized : undefined;
};

/** Default per-request byte budget for imported message batches. The backend
 * accepts up to 10 MB but API Gateway/Lambda proxy limits are lower, so stay
 * comfortably under. */
export const DEFAULT_MAX_BATCH_BYTES = 1024 * 1024;

/**
 * Derive a session name from the import payload: explicit name first,
 * then the first human message text, then a generic fallback.
 */
const deriveSessionName = (name: unknown, messages: LisaChatMessageFields[]): string => {
    if (typeof name === 'string' && name.trim()) {
        return name.trim();
    }
    const firstHuman = messages.find((msg) => msg.type === MessageTypes.HUMAN);
    if (firstHuman) {
        const text = typeof firstHuman.content === 'string'
            ? firstHuman.content
            : Array.isArray(firstHuman.content)
                ? ((firstHuman.content.find((c: any) => c?.text) as any)?.text || '')
                : '';
        if (text.trim()) {
            return text.trim().slice(0, 50);
        }
    }
    return 'Imported Session';
};

/**
 * Parse and validate an exported session JSON file (the format produced by
 * "Download Session") into the pieces needed to recreate it via the
 * postMessages API. Throws an Error with a user-displayable message when the
 * file is not a valid session export.
 */
export const parseSessionImport = (fileContents: string): ParsedSessionImport => {
    let data: any;
    try {
        data = JSON.parse(fileContents);
    } catch {
        throw new Error('File is not valid JSON');
    }

    if (!data || typeof data !== 'object' || Array.isArray(data)) {
        throw new Error('File does not contain a session object');
    }

    if (!Array.isArray(data.history) || data.history.length === 0) {
        throw new Error('Session file must contain a non-empty "history" array');
    }

    const messages: LisaChatMessageFields[] = data.history.map((msg: any, index: number) => {
        if (!msg || typeof msg !== 'object') {
            throw new Error(`Message at index ${index} is not an object`);
        }
        if (typeof msg.type !== 'string' || !VALID_MESSAGE_TYPES.has(msg.type)) {
            throw new Error(`Message at index ${index} has an invalid type: ${JSON.stringify(msg.type)}`);
        }
        if (msg.content === undefined || msg.content === null) {
            throw new Error(`Message at index ${index} is missing content`);
        }
        // Keep only the fields the session APIs persist; drop anything else
        // (e.g. langchain serialization artifacts) from untrusted input.
        const sanitized: LisaChatMessageFields = {
            type: msg.type,
            content: msg.content,
            metadata: isPlainObject(msg.metadata) ? msg.metadata : {},
            toolCalls: Array.isArray(msg.toolCalls) ? msg.toolCalls : [],
            usage: sanitizeUsage(msg.usage),
            guardrailTriggered: msg.guardrailTriggered,
            reasoningContent: msg.reasoningContent,
            reasoningSignature: msg.reasoningSignature,
        };
        return sanitized;
    });

    return {
        messages,
        name: `${deriveSessionName(data.name, messages)} (imported)`,
        configuration: isPlainObject(data.configuration) ? data.configuration : undefined,
    };
};

/**
 * Split messages into ordered batches that each stay under the request size
 * limit. A single oversized message still gets its own batch and is left for
 * the backend to accept or reject.
 */
const utf8Encoder = new TextEncoder();

export const batchMessages = (
    messages: LisaChatMessageFields[],
    maxBatchBytes: number = DEFAULT_MAX_BATCH_BYTES,
): LisaChatMessageFields[][] => {
    const batches: LisaChatMessageFields[][] = [];
    let current: LisaChatMessageFields[] = [];
    let currentBytes = 0;

    for (const message of messages) {
        // Measure UTF-8 bytes, not string length: code-unit counts undercount
        // multi-byte characters and could overflow the request-size limit.
        const messageBytes = utf8Encoder.encode(JSON.stringify(message)).length;
        if (current.length > 0 && currentBytes + messageBytes > maxBatchBytes) {
            batches.push(current);
            current = [];
            currentBytes = 0;
        }
        current.push(message);
        currentBytes += messageBytes;
    }
    if (current.length > 0) {
        batches.push(current);
    }
    return batches;
};

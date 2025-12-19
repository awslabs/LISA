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

import { BaseMemory, InputValues, MemoryVariables, OutputValues } from '@langchain/core/memory';
import { BaseChatMessageHistory } from '@langchain/core/chat_history';
import { BaseMessage, HumanMessage, AIMessage } from '@langchain/core/messages';
import { LisaChatMessage } from '@/components/types';

export type ChatMemoryInput = {
    chatHistory: BaseChatMessageHistory;
    returnMessages: boolean;
    memoryKey: string;
    k: number;
    humanPrefix?: string;
    aiPrefix?: string;
};

/**
 * Converts a list of messages into a buffer string format.
 */
export function getBufferString (
    messages: BaseMessage[],
    humanPrefix = 'Human',
    aiPrefix = 'AI'
): string {
    const stringMessages: string[] = [];
    for (const m of messages) {
        let role: string;
        if (m._getType() === 'human') {
            role = humanPrefix;
        } else if (m._getType() === 'ai') {
            role = aiPrefix;
        } else if (m._getType() === 'system') {
            role = 'System';
        } else if (m._getType() === 'function') {
            role = 'Function';
        } else if (m._getType() === 'tool') {
            role = 'Tool';
        } else {
            role = m._getType();
        }
        stringMessages.push(`${role}: ${m.content}`);
    }
    return stringMessages.join('\n');
}

/**
 * Class for managing and storing previous chat messages. This implements a buffer window memory
 * to maintain a sliding window of recent messages.
 */
export class ChatMemory extends BaseMemory {
    chatHistory: BaseChatMessageHistory;
    returnMessages: boolean;
    memoryKey: string;
    k: number;
    humanPrefix: string;
    aiPrefix: string;

    constructor (fields: ChatMemoryInput) {
        super();
        this.chatHistory = fields.chatHistory;
        this.returnMessages = fields.returnMessages;
        this.memoryKey = fields.memoryKey;
        this.k = fields.k;
        this.humanPrefix = fields.humanPrefix ?? 'Human';
        this.aiPrefix = fields.aiPrefix ?? 'AI';
    }

    get memoryKeys (): string[] {
        return [this.memoryKey];
    }

    /**
     * Load memory variables with type conversion of LisaChatMessage
     */
    async loadMemoryVariables (): Promise<MemoryVariables> {
        const messages: BaseMessage[] = await this.chatHistory.getMessages();
        const lisaMessages = messages.map((message) => new LisaChatMessage({ ...message, type: message._getType() }));

        if (this.returnMessages) {
            return {
                [this.memoryKey]: lisaMessages.slice(-this.k * 2),
            };
        }

        return {
            [this.memoryKey]: getBufferString(lisaMessages.slice(-this.k * 2), this.humanPrefix, this.aiPrefix),
        };
    }

    /**
     * Save context from this conversation to buffer
     */
    async saveContext (inputValues: InputValues, outputValues: OutputValues): Promise<void> {
        const input = this.getInputValue(inputValues);
        const output = this.getOutputValue(outputValues);

        await this.chatHistory.addMessage(new HumanMessage(input));
        await this.chatHistory.addMessage(new AIMessage(output));
    }

    /**
     * Clear memory contents
     */
    async clear (): Promise<void> {
        await this.chatHistory.clear();
    }

    private getInputValue (inputValues: InputValues): string {
        const keys = Object.keys(inputValues);
        if (keys.length === 1) {
            return inputValues[keys[0]];
        }
        throw new Error('Multiple input keys found. Please specify inputKey.');
    }

    private getOutputValue (outputValues: OutputValues): string {
        const keys = Object.keys(outputValues);
        if (keys.length === 1) {
            return outputValues[keys[0]];
        }
        throw new Error('Multiple output keys found. Please specify outputKey.');
    }
}

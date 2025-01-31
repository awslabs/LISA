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

import { BufferWindowMemory, getBufferString } from 'langchain/memory';
import { LisaChatMessage } from '../../components/types';
import { BaseMessage } from '@langchain/core/messages';
import { MemoryVariables } from '@langchain/core/memory';

/**
 * Class for managing and storing previous chat messages. This extends BufferWindowMemory to add a transform to ensure
 * json messages are converted into LISA Chat messages.
 */
export class ChatMemory extends BufferWindowMemory {

    /**
     * Override loadMemoryVariables to add type conversion of LisaChatMessage
     */
    async loadMemoryVariables (): Promise<MemoryVariables> {
        const messages: BaseMessage[] = await this.chatHistory.getMessages();
        const lisaMessages = messages.map((message) => new LisaChatMessage({ ...message, type: message['type'] }));
        if (this.returnMessages) {
            return {
                [this.memoryKey]: lisaMessages.slice(-this.k * 2),
            };
        }

        return {
            [this.memoryKey]: getBufferString(lisaMessages.slice(-this.k * 2), this.humanPrefix, this.aiPrefix),
        };
    }
}

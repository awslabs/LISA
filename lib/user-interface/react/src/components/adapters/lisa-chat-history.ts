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

import { BaseChatMessageHistory } from '@langchain/core/chat_history';
import { LisaChatMessage, LisaChatSession } from '../types';

/**
 * Provides the chat message history based on the given LisaChatSession
 */
export class LisaChatMessageHistory extends BaseChatMessageHistory {
    lc_namespace = ['components', 'adapters', 'lisa-chat-history'];

    private session: LisaChatSession;

    constructor (session: LisaChatSession) {

        super(...arguments);
        this.session = session;
    }

    async getMessages (): Promise<LisaChatMessage[]> {
        return this.session.history;
    }

    async addMessage (message: LisaChatMessage) {
        void message;
    // noop since messages are managed at the session level
    }

    async addUserMessage (message: string): Promise<void> {
        void message;
    // noop since messages are managed at the session level
    }

    async addAIChatMessage (message: string): Promise<void> {
        void message;
    // noop since messages are managed at the session level
    }

    async clear () {
    // noop since messages are managed at the session level
    }
}

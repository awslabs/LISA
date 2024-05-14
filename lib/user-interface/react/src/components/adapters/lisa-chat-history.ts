import { BaseChatMessageHistory } from '@langchain/core/chat_history';
import { LisaChatMessage, LisaChatSession } from '../types';

/**
 * Provides the chat message history based on the given LisaChatSession
 */
export class LisaChatMessageHistory extends BaseChatMessageHistory {
  lc_namespace = ['components', 'adapters', 'lisa-chat-history'];

  private session: LisaChatSession;

  constructor(session: LisaChatSession) {
    // eslint-disable-next-line prefer-rest-params
    super(...arguments);
    this.session = session;
  }

  async getMessages(): Promise<LisaChatMessage[]> {
    return this.session.history;
  }

  async addMessage(message: LisaChatMessage) {
    void message;
    // noop since messages are managed at the session level
  }

  async addUserMessage(message: string): Promise<void> {
    void message;
    // noop since messages are managed at the session level
  }
  async addAIChatMessage(message: string): Promise<void> {
    void message;
    // noop since messages are managed at the session level
  }

  async clear() {
    // noop since messages are managed at the session level
  }
}

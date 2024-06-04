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

import { BaseMessage, BaseMessageFields, MessageContent, MessageType } from '@langchain/core/messages';

/**
 * Used to specify additional parameters in how the LLM processes inputs
 */
export type ModelKwargs = {
  max_tokens?: number;
  n?: number | null;
  top_p?: number | null;
  frequency_penalty?: number | null;
  presence_penalty?: number | null;
  temperature?: number | null;
  repetition_penalty?: number | null;
  stop: string[];
  seed?: number | null;
};

/**
 * Stores metadata for messages returned from LISA
 */
export type LisaChatMessageMetadata = {
  modelName?: string;
  modelKwargs?: ModelKwargs;
  userId?: string;
  messages?: string;
  ragContext?: string;
};
/**
 * Interface for storing data for messages
 */
export interface LisaChatMessageFields extends BaseMessageFields {
  type: MessageType;
  content: MessageContent;
  metadata?: LisaChatMessageMetadata;
}

/**
 * Stores data for messages including the message type and message metadata
 */
export class LisaChatMessage extends BaseMessage implements LisaChatMessageFields {
  type: MessageType;
  metadata?: LisaChatMessageMetadata;

  constructor(fields: LisaChatMessageFields) {
    super(fields);
    this.type = fields.type;
    this.metadata = fields.metadata ?? {};
  }

  static lc_name() {
    return 'LisaChatMessage';
  }

  _getType(): MessageType {
    return this.type;
  }
}

/**
 * Stores session data for chats with LISA
 */
export type LisaChatSession = {
  sessionId: string;
  userId: string;
  startTime: string;
  history: LisaChatMessage[];
};

/**
 * Supported model types for LISA
 */
export type ModelTypes = 'textgen' | 'embedding';

/**
 * Supported RAG repository types for LISA
 */
export type RepositoryTypes = 'OpenSearch';

/**
 * Interface for repository
 */
export interface Repository {
  repositoryId: string;
  type: RepositoryTypes;
}

/**
 * Interface for model
 */
export interface Model {
  id: string;
  object: string;
  created: number;
  owned_by: string;
}

/**
 * Interface for the response body received when describing a model
 */
export interface DescribeModelsResponseBody {
  data: Model[];
}

/**
 * Interface for creating a session request body; composed of LisaChatMessageFields
 */
export interface PutSessionRequestBody {
  messages: LisaChatMessageFields[];
}

/**
 * File types that can be uploaded for context or for RAG
 */
export enum FileTypes {
  TEXT = 'text/plain',
  DOCX = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  PDF = 'application/pdf',
}

/**
 * Loading types for status indicator
 */
export enum StatusTypes {
  LOADING = 'loading',
  SUCCESS = 'success',
  ERROR = 'error',
}

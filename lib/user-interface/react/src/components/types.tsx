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
import { IChatConfiguration, IModelConfiguration } from '@/shared/model/chat.configurations.model';
import { MessageContentComplex } from '@langchain/core/dist/messages/base';

/**
 * Used to specify additional parameters to be passed into OpenAI LLM Model Calls
 */
export type ModelConfig = {
    max_tokens?: number;
    modelKwargs?: ModelArgs;
};

/**
 * Used to specify additional parameters in how the LLM processes inputs
 */
export type ModelArgs = {
    n?: number | null;
    top_p?: number | null;
    frequency_penalty?: number | null;
    presence_penalty?: number | null;
    temperature?: number | null;
    stop: string[];
    seed?: number | null;
};


export type ImageGenerationParams = {
    size?: string;
    n?: number;
    quality?: string;
    prompt: string;
};

export type VideoGenerationParams = {
    prompt: string;
    model?: string;
};

/**
 * Stores metadata for messages returned from LISA
 */
export type LisaChatMessageMetadata = {
    modelName?: string;
    modelKwargs?: ModelConfig;
    userId?: string;
    messages?: string;
    ragContext?: string;
    ragDocuments?: string;
    imageGeneration?: boolean;
    imageGenerationParams?: ImageGenerationParams;
    videoGeneration?: boolean;
    videoGenerationParams?: VideoGenerationParams;
    videoId?: string;
    videoStatus?: string;
};
/**
 * Usage information from OpenAI API responses
 */
export type UsageInfo = {
    completionTokens?: number;
    responseTime?: number;
    promptTokens?: number;
    totalTokens?: number;
    outputTokens?: number;
};

/**
 * Interface for storing data for messages
 */
export type LisaChatMessageFields = {
    type: MessageType;
    content: MessageContent;
    metadata?: LisaChatMessageMetadata;
    toolCalls?: any[];
    usage?: UsageInfo;
    guardrailTriggered?: boolean;
    reasoningContent?: string;
    reasoningSignature?: string;
} & BaseMessageFields;

/**
 * Stores data for messages including the message type and message metadata
 */
export class LisaChatMessage extends BaseMessage implements LisaChatMessageFields {
    type: MessageType;
    metadata?: LisaChatMessageMetadata;
    toolCalls?: any[];
    usage?: UsageInfo;
    guardrailTriggered?: boolean;
    reasoningContent?: string;
    reasoningSignature?: string;

    constructor (fields: LisaChatMessageFields) {
        super(fields);
        this.type = fields.type;
        this.metadata = fields.metadata ?? {};
        this.toolCalls = fields.toolCalls ?? [];
        this.usage = fields.usage;
        this.guardrailTriggered = fields.guardrailTriggered ?? false;
        this.reasoningContent = fields.reasoningContent;
        this.reasoningSignature = fields.reasoningSignature;
    }

    static lc_name () {
        return 'LisaChatMessage';
    }

    _getType (): MessageType {
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
    lastUpdated?: string;  // Optional for backward compatibility
    history: LisaChatMessage[];
    name?: string;
    firstHumanMessage?: MessageContent;
    configuration?: IChatConfiguration & IModelConfiguration;
};

export type LisaAttachImageRequest = {
    sessionId: string;
    message: MessageContentComplex;
};

export type LisaAttachImageResponse = {
    body: MessageContentComplex;
};

/**
 * Supported model types for LISA
 */
export type ModelTypes = 'textgen' | 'embedding';

/**
 * Supported RAG repository types for LISA
 */
export type RepositoryTypes = 'OpenSearch' | 'PGVector';

/**
 * Interface for repository
 */
export type Repository = {
    repositoryId: string;
    repositoryName?: string;
    type: RepositoryTypes;
    allowedGroups: string[];
};

/**
 * Ingestion types for RAG Document
 */
export type IngestionType = 'manual' | 'auto';

/**
 * Interface for RAG Document
 */
export type RagDocument = {
    document_id: string,
    document_name: string,
    repository_id: string,
    collection_id: string,
    source: string,
    username: string,
    chunk_strategy: any,
    ingestion_type: IngestionType,
    upload_date: number,
    chunks: number,
};

/**
 * Interface for model
 */
export type Model = {
    id: string;
    modelType: ModelTypes;
    streaming?: boolean;
};

/**
 * Interface for OpenAIModel that is used for OpenAI Model Interactions
 */
export type OpenAIModel = {
    id: string;
    object: string;
    created: number;
    owned_by: string;
};

/**
 * Interface for the response body received when describing a model
 */
export type DescribeModelsResponseBody = {
    data: OpenAIModel[];
};

/**
 * Interface for creating a session request body; composed of LisaChatMessageFields
 */
export type PutSessionRequestBody = {
    messages: LisaChatMessageFields[];
};

/**
 * File types that can be uploaded for context or for RAG
 */
export enum FileTypes {
    TEXT = 'text/plain',
    DOCX = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    PDF = 'application/pdf',
    JPEG = 'image/jpeg',
    JPG = 'image/jpg',
    PNG = 'image/png',
    GIF = 'image/gif',
    WEBP = 'image/webp'
}

/**
 * Loading types for status indicator
 */
export enum StatusTypes {
    LOADING = 'loading',
    SUCCESS = 'success',
    ERROR = 'error',
}

/**
 * Message Types
 */
export enum MessageTypes {
    HUMAN = 'human',
    SYSTEM = 'system',
    AI = 'ai',
    TOOL = 'tool',
}

/**
 * Model Features
 */
export enum ModelFeatures {
    SUMMARIZATION = 'summarization',
    IMAGE_INPUT = 'imageInput',
    TOOL_CALLS = 'toolCalls',
    REASONING = 'reasoning',
}

/**
 * Interface for paginated document list response
 */
export type PaginatedDocumentResponse = {
    documents: RagDocument[];
    lastEvaluated?: {
        pk: string;
        document_id: string;
        repository_id: string;
    } | null;
    totalDocuments?: number;
    hasNextPage?: boolean;
    hasPreviousPage?: boolean;
};

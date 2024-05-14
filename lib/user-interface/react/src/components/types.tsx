import { BaseMessage, BaseMessageFields, MessageContent, MessageType } from '@langchain/core/messages';

/**
 * Used to specify additional parameters in how the LLM processes inputs
 */
export type ModelKwargs = {
  max_new_tokens: number;
  top_k?: number | null;
  top_p?: number | null;
  typical_p?: number | null;
  temperature?: number | null;
  repetition_penalty?: number | null;
  return_full_text: boolean;
  truncate?: number | null;
  stop_sequences: string[];
  seed?: number | null;
  do_sample: boolean;
  watermark: boolean;
};

/**
 * Stores metadata for messages returned from LISA
 */
export type LisaChatMessageMetadata = {
  modelName?: string;
  modelKwargs?: ModelKwargs;
  userId?: string;
  prompt?: string;
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
 * Supported finish reasons for generating a response
 */
export type FinishReasons = 'length' | 'eos_token' | 'stop_sequence';

/**
 * Interface for models
 */
export interface Model {
  modelName: string;
  provider: string;
  streaming: boolean;
  modelKwargs: ModelKwargs;
  modelType: ModelTypes;
}
/**
 * Model provider class for maintaining a list of models associated with a model provider name
 */
export class ModelProvider {
  public name: string;
  public models: Model[];

  constructor(providerName: string, models: Model[]) {
    this.models = models;
    this.name = providerName;
  }
}

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

/*
 * TODO: this isn't easily extensible but eventually we should be
 * generating types from the LISA-serve api spec though
 */
export enum TextGenModelProviderNames {
  EcsTextGenTgi = 'ecs.textgen.tgi',
  SagemakerTextGenTgi = 'sagemaker.textgen.tgi',
}

/**
 * TextGen records. Maps the TextGen provider names to a model
 */
export type TextGenModelRecord = Record<TextGenModelProviderNames, Record<string, Model>>;

/**
 * Interface for the response body received when describing a model
 */
export interface DescribeModelsResponseBody {
  textgen?: TextGenModelRecord;
  embedding?: any; // TODO: providing typing info for embedding models for RAG
}

/**
 * Interface for generating a request body to be sent to a model
 */
export interface GenerateRequestBody {
  provider: string;
  modelName: string;
  text: string;
  modelKwargs: object;
}

/**
 * Interface for generating a response body when receiving a response from a model
 */
export interface GenerateResponseBody {
  finishReason: FinishReasons;
  generatedText: string;
  generatedToken: number;
}

/**
 * Interface for a stream token which is used for generating a stream response
 */
export interface StreamToken {
  text: string;
  special: boolean;
}

/**
 * Interface for generating a response object from a stream request
 */
export interface GenerateStreamResponseBody {
  token: StreamToken;
  generatedTokens?: number;
  finishReason?: string;
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

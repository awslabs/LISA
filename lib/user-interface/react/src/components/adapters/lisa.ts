import { GenerateRequestBody, GenerateResponseBody, GenerateStreamResponseBody, ModelKwargs } from '../types';
import { sendAuthenticatedRequest } from '../utils';
import { fetchEventSource } from '@microsoft/fetch-event-source';
import { Document } from '@langchain/core/documents';
import { BaseRetriever, BaseRetrieverInput } from '@langchain/core/retrievers';
import { CallbackManagerForLLMRun } from '@langchain/core/callbacks/manager';
import { BaseLLMCallOptions, BaseLLMParams, LLM } from '@langchain/core/language_models/llms';

// Custom for whatever model you'll be using
export class LisaContentHandler {
  contentType = 'application/json';
  accepts = 'application/json';

  async transformInput(
    prompt: string,
    modelKwargs: ModelKwargs,
    modelName: string,
    providerName: string,
  ): Promise<string> {
    const payload: GenerateRequestBody = {
      provider: providerName,
      modelName: modelName,
      modelKwargs: modelKwargs,
      text: prompt,
    };

    return JSON.stringify(payload);
  }

  async transformOutput(output: GenerateResponseBody, modelKwargs: ModelKwargs): Promise<string> {
    if (output.generatedText) {
      if (output.finishReason === 'stop_sequence') {
        for (const suffix of modelKwargs.stop_sequences) {
          if (output.generatedText.endsWith(suffix)) {
            // Remove the suffix and break the loop
            output.generatedText = output.generatedText.substring(0, output.generatedText.length - suffix.length);
            break;
          }
        }
      }
      return output.generatedText;
    } else {
      return '';
    }
  }
}

export interface LisaInput extends BaseLLMParams {
  /**
   * The URI of the LISA inference engine
   */
  uri: string;

  /**
   * Key word arguments to pass to the model.
   */
  modelKwargs: ModelKwargs;

  /**
   * Name of model to call generate on
   */
  modelName: string;

  /**
   * Name of model provider
   */
  providerName: string;

  /**
   * The content handler class that provides an input and output transform
   * functions to handle formats between LLM and the endpoint.
   */
  contentHandler: LisaContentHandler;
  streaming?: boolean;
  idToken: string;
}

/**
 * Class for interacting with LISA Serve REST API
 */
export class Lisa extends LLM<BaseLLMCallOptions> {
  static lc_name() {
    return 'LISA';
  }

  public modelKwargs: ModelKwargs;
  public modelName: string;
  public providerName: string;
  public streaming: boolean;
  public idToken: string;
  private uri: string;
  private contentHandler: LisaContentHandler;

  constructor(fields: LisaInput) {
    super(fields);

    const contentHandler = fields?.contentHandler;
    if (!contentHandler) {
      throw new Error(`Please pass a "contentHandler" field to the constructor`);
    }

    this.uri = fields.uri;
    this.contentHandler = fields.contentHandler;
    this.modelName = fields.modelName;
    this.providerName = fields.providerName;
    this.modelKwargs = fields.modelKwargs;
    this.streaming = fields.streaming ?? false;
    this.idToken = fields.idToken;
  }

  _llmType() {
    return 'lisa';
  }

  /**
   * Calls the LISA endpoint and retrieves the result.
   * @param {string} prompt The input prompt.
   * @param {this["ParsedCallOptions"]} options Parsed call options.
   * @param {CallbackManagerForLLMRun} runManager Optional run manager.
   * @returns {Promise<string>} A promise that resolves to the generated string.
   */
  /** @ignore */
  async _call(
    prompt: string,
    options: this['ParsedCallOptions'],
    runManager?: CallbackManagerForLLMRun,
  ): Promise<string> {
    return this.streaming
      ? await this.streamingCall(prompt, options, runManager)
      : await this.noStreamingCall(prompt, options);
  }

  private async streamingCall(
    prompt: string,
    options: this['ParsedCallOptions'],
    runManager?: CallbackManagerForLLMRun,
  ): Promise<string> {
    const body = await this.contentHandler.transformInput(prompt, this.modelKwargs, this.modelName, this.providerName);
    const { contentType, accepts } = this.contentHandler;
    const tokens: string[] = [];
    await fetchEventSource(`${this.uri}/generateStream`, {
      method: 'POST',
      headers: {
        'Content-Type': contentType,
        Accept: accepts,
        Authorization: `Bearer ${this.idToken}`,
      },
      body: body,
      async onopen(res) {
        if (res.status >= 400 && res.status < 500 && res.status !== 429) {
          throw res;
        }
      },
      async onmessage(event) {
        const parsedData = JSON.parse(event.data) as GenerateStreamResponseBody;
        if (!parsedData.token.special && parsedData.finishReason != 'stop_sequence') {
          tokens.push(parsedData.token.text);
          await runManager?.handleLLMNewToken(parsedData.token.text);
        }
      },
      onerror(err) {
        throw err;
      },
    });
    return tokens.join('');
  }

  private async noStreamingCall(prompt: string, options: this['ParsedCallOptions']): Promise<string> {
    void options;
    const body = await this.contentHandler.transformInput(prompt, this.modelKwargs, this.modelName, this.providerName);
    const { contentType, accepts } = this.contentHandler;

    const response = await this.caller.call(() =>
      sendAuthenticatedRequest(`${this.uri}/generate`, 'POST', this.idToken, body, {
        Accept: accepts,
        'Content-Type': contentType,
      }),
    );
    return this.contentHandler.transformOutput(await response.json(), this.modelKwargs);
  }
}

export interface LisaRAGRetrieverInput extends BaseRetrieverInput {
  /**
   * The URI of the LISA RAG API
   */
  uri: string;

  /**
   * Name of model to use for embeddings
   */
  modelName: string;

  /**
   * Name of model provider
   */
  providerName: string;

  /**
   * Authentication token to use when communicating with RAG API
   */
  idToken: string;

  /**
   * Id of the RAG repository to query
   */
  repositoryId: string;

  /**
   * Type of the RAG repository to query
   */
  repositoryType: string;

  /**
   * The number of relevant documents to retrieve
   */
  topK?: number;
}

export class LisaRAGRetriever extends BaseRetriever {
  lc_namespace: string[];

  private uri: string;
  public modelName: string;
  public providerName: string;
  public idToken: string;
  public repositoryId: string;
  public repositoryType: string;
  public topK: number;

  constructor(fields?: LisaRAGRetrieverInput) {
    super(fields);

    this.uri = fields.uri;
    this.modelName = fields.modelName;
    this.providerName = fields.providerName;
    this.idToken = fields.idToken;
    this.repositoryId = fields.repositoryId;
    this.repositoryType = fields.repositoryType;
    this.topK = fields.topK || 3;
  }

  async _getRelevantDocuments(query: string): Promise<Document[]> {
    const resp = await sendAuthenticatedRequest(
      `repository/${this.repositoryId}/similaritySearch?query=${query}&modelName=${this.modelName}&modelProvider=${this.providerName}&repositoryType=${this.repositoryType}&topK=${this.topK}`,
      'GET',
      this.idToken,
    );
    const searchResults = await resp.json();
    return searchResults.docs;
  }
}

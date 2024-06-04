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

import { sendAuthenticatedRequest } from '../utils';
import { Document } from '@langchain/core/documents';
import { BaseRetriever, BaseRetrieverInput } from '@langchain/core/retrievers';

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

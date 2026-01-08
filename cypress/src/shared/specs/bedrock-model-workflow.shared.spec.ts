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

/// <reference types="cypress" />

/**
 * Shared test suite for Bedrock model creation and chat workflow.
 * Can be used by both smoke tests (with fixtures) and e2e tests (with real data).
 */

import { navigateToAdminPage } from '../../support/adminHelpers';
import { navigateAndVerifyChatPage } from '../../support/chatHelpers';
import {
    BedrockModelConfig,
    openCreateModelWizard,
    fillBedrockModelConfig,
    completeBedrockModelWizard,
    waitForModelCreationSuccess,
    verifyModelInList,
    deleteModelIfExists,
    selectModelInChat,
    sendChatMessage,
    verifyChatResponse,
    deleteAllSessions,
} from '../../support/modelFormHelpers';
import {
    RepositoryConfig,
    navigateToRepositoryManagement,
    openCreateRepositoryWizard,
    fillRepositoryConfig,
    selectKnowledgeBase,
    selectDataSource,
    skipToCreateRepository,
    completeRepositoryWizard,
    waitForRepositoryCreationSuccess,
    verifyRepositoryInList,
    deleteRepositoryIfExists,
} from '../../support/repositoryHelpers';

// Amazon Nova Micro - cheapest Bedrock serverless model
const DEFAULT_TEST_MODEL: BedrockModelConfig = {
    modelId: `e2e-nova-micro-${Date.now()}`,
    modelName: 'bedrock/us.amazon.nova-micro-v1:0',
    modelDescription: 'E2E test model - Amazon Nova Micro',
    streaming: true,
};

export type BedrockWorkflowTestOptions = {
    modelConfig?: BedrockModelConfig;
    repositoryConfig?: RepositoryConfig;
    skipChat?: boolean;
    skipCleanup?: boolean;
};

export function runBedrockModelWorkflowTests (options: BedrockWorkflowTestOptions = {}) {
    const testModel = options.modelConfig || DEFAULT_TEST_MODEL;
    const testRepository: RepositoryConfig = options.repositoryConfig || {
        repositoryId: `e2e-repo-${Date.now()}`,
        knowledgeBaseName: 'test-bedrock-kb',
        dataSourceIndex: 0,
    };
    const testPrompt = 'Hello, respond with one word: working';

    it('Admin creates a Bedrock model via wizard', () => {
        navigateToAdminPage('Model Management');

        openCreateModelWizard();
        fillBedrockModelConfig(testModel);
        completeBedrockModelWizard();
        waitForModelCreationSuccess(testModel.modelId);
    });

    it('New model appears in Model Management list', () => {
        navigateToAdminPage('Model Management');
        verifyModelInList(testModel.modelId);
    });

    it('Admin creates a repository with the new Bedrock model', () => {
        navigateToRepositoryManagement();

        openCreateRepositoryWizard();
        fillRepositoryConfig(testRepository);
        selectKnowledgeBase(testRepository.knowledgeBaseName);
        selectDataSource(testRepository.dataSourceIndex);
        skipToCreateRepository();
        completeRepositoryWizard();
        waitForRepositoryCreationSuccess(testRepository.repositoryId);
    });

    it('New repository appears in RAG Management list', () => {
        navigateToRepositoryManagement();
        verifyRepositoryInList(testRepository.repositoryId);
    });

    it('User selects new model in Chat and sends a message', () => {
        navigateAndVerifyChatPage();
        selectModelInChat(testModel.modelId);
        sendChatMessage(testPrompt);
        verifyChatResponse(testPrompt);
    });

    it('Cleanup: delete all chat sessions', () => {
        navigateAndVerifyChatPage();
        deleteAllSessions();
    });

    it('Cleanup: delete test repository', () => {
        navigateToRepositoryManagement();
        cy.wait(2000);
        deleteRepositoryIfExists(testRepository.repositoryId);
    });

    it('Cleanup: delete test model', () => {
        navigateToAdminPage('Model Management');
        cy.wait(2000);
        deleteModelIfExists(testModel.modelId);
    });
}

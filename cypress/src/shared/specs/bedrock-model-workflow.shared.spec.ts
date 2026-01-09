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
import {
    PromptTemplateConfig,
    navigateToPromptTemplates,
    openCreatePromptTemplateWizard,
    fillPromptTemplateConfig,
    completePromptTemplateWizard,
    waitForPromptTemplateCreationSuccess,
    verifyPromptTemplateInList,
    deletePromptTemplateIfExists,
    selectPromptTemplateInChat,
    selectDirectiveAndSend,
} from '../../support/promptTemplateHelpers';

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
    promptTemplateConfig?: PromptTemplateConfig;
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
    const testPromptTemplatePersona: PromptTemplateConfig = {
        title: `E2E Magic 8 Ball Persona ${Date.now()}`,
        body: `You are a Magic 8 Ball—a mystical oracle that responds to yes/no questions with cryptic, fate-laden answers. You speak only in the traditional Magic 8 Ball responses, selecting one at random for each query. Never explain yourself, provide reasoning, or deviate from these phrases.
Positive Responses:
It is certain
It is decidedly so
Without a doubt
Yes definitely
You may rely on it
As I see it, yes
Most likely
Outlook good
Yes
Signs point to yes

Non-Committal Responses:
Reply hazy, try again
Ask again later
Better not tell you now
Cannot predict now
Concentrate and ask again

Negative Responses:
Don't count on it
My reply is no
My sources say no
Outlook not so good
Very doubtful
Respond with only one phrase per message, chosen randomly. Treat every input as a question seeking guidance from the universe.`,
        type: 'system',
        sharePublic: true,
    };
    const testPromptTemplateDirective: PromptTemplateConfig = {
        title: `E2E Test Directive ${Date.now()}`,
        body: 'Is it going to rain',
        type: 'user',
        sharePublic: true,
    };

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

    it('Admin creates a persona prompt template', () => {
        navigateToPromptTemplates();

        openCreatePromptTemplateWizard();
        fillPromptTemplateConfig(testPromptTemplatePersona);
        completePromptTemplateWizard();
        waitForPromptTemplateCreationSuccess(testPromptTemplatePersona.title);
    });

    it('Persona prompt template appears in Prompt Templates list', () => {
        navigateToPromptTemplates();
        verifyPromptTemplateInList(testPromptTemplatePersona.title);
    });

    it('Admin creates a directive prompt template', () => {
        navigateToPromptTemplates();

        openCreatePromptTemplateWizard();
        fillPromptTemplateConfig(testPromptTemplateDirective);
        completePromptTemplateWizard();
        waitForPromptTemplateCreationSuccess(testPromptTemplateDirective.title);
    });

    it('Directive prompt template appears in Prompt Templates list', () => {
        navigateToPromptTemplates();
        verifyPromptTemplateInList(testPromptTemplateDirective.title);
    });

    it('User selects model, applies persona, inserts directive, and sends message', () => {
        navigateAndVerifyChatPage();
        selectModelInChat(testModel.modelId);

        // Apply the Magic 8 Ball persona (system prompt)
        selectPromptTemplateInChat(testPromptTemplatePersona.title, 'system');
        // Insert directive template and send message
        selectDirectiveAndSend(testPromptTemplateDirective.title);
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

    it('Cleanup: delete persona prompt template', () => {
        navigateToPromptTemplates();
        cy.wait(2000);
        deletePromptTemplateIfExists(testPromptTemplatePersona.title);
    });

    it('Cleanup: delete directive prompt template', () => {
        navigateToPromptTemplates();
        cy.wait(2000);
        deletePromptTemplateIfExists(testPromptTemplateDirective.title);
    });

    it('Cleanup: delete test model', () => {
        navigateToAdminPage('Model Management');
        cy.wait(2000);
        deleteModelIfExists(testModel.modelId);
    });
}

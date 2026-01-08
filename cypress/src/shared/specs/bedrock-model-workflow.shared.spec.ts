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
import { insertChatPrompt, navigateAndVerifyChatPage, sendMessageWithButton, verifyChatResponseReceived } from '../../support/chatHelpers';
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
    promptTemplateExists,
    PromptTemplateType,
} from '../../support/promptTemplateHelpers';
import {
    CollectionConfig,
    navigateToRagManagement,
    waitForRepositoryReady,
    getAutoCreatedCollectionInfo,
    renameCollection,
    uploadDocument,
    waitForDocumentIngested,
    selectRagRepositoryInChat,
    selectCollectionInChat,
} from '../../support/collectionHelpers';


// Use date-based naming for easier debugging and test reusability
function getTodayDateString (): string {
    const today = new Date();
    const month = String(today.getMonth() + 1).padStart(2, '0');
    const day = String(today.getDate()).padStart(2, '0');
    const year = today.getFullYear();
    return `${month}-${day}-${year}`;
}

// Amazon Nova Micro - cheapest Bedrock serverless model
const DEFAULT_TEST_MODEL: BedrockModelConfig = {
    modelId: `e2e-nova-micro-${getTodayDateString()}`,
    modelName: 'bedrock/us.amazon.nova-micro-v1:0',
    modelDescription: 'E2E test model - Amazon Nova Micro',
    streaming: true,
};

export type BedrockWorkflowTestOptions = {
    modelConfig?: BedrockModelConfig;
    repositoryConfig?: RepositoryConfig;
    skipChat?: boolean;
    skipCleanup?: boolean;
    testDocumentPath?: string;
};

export function runBedrockModelWorkflowTests (options: BedrockWorkflowTestOptions = {}) {
    const dateString = getTodayDateString();
    const testModel = options.modelConfig || DEFAULT_TEST_MODEL;
    const testRepository: RepositoryConfig = options.repositoryConfig || {
        repositoryId: `e2e-repo-${dateString}`,
        knowledgeBaseName: 'test-bedrock-kb',
        dataSourceIndex: 0,
    };
    const testCollection: CollectionConfig = options.collectionConfig || {
        collectionId: `e2e-collection-${dateString}`,
        collectionName: `E2E Test Collection ${dateString}`,
        repositoryId: testRepository.repositoryId,
    };
    const testDocumentPath = options.testDocumentPath || 'test-document.txt';

    // Track test state for dependencies
    const testState = {
        modelCreated: false,
        repositoryCreated: false,
        repositoryReady: false,
        collectionRenamed: false,
        collectionId: '', // Store the actual collection ID
        documentUploaded: false,
        documentIngested: false,
        personaTemplateCreated: false,
        directiveTemplateCreated: false,
    };

    const testPromptTemplatePersona: PromptTemplateConfig = {
        title: `E2E Magic 8 Ball Persona ${dateString}`,
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
        type: PromptTemplateType.Persona,
        sharePublic: true,
    };
    const testPromptTemplateDirective: PromptTemplateConfig = {
        title: `E2E Test Directive ${dateString}`,
        body: 'Is it going to rain',
        type: PromptTemplateType.Directive,
        sharePublic: true,
    };

    it('Admin creates a Bedrock model via wizard (or uses existing)', () => {
        // Ensure app is fully ready before navigating
        cy.get('header button[aria-label="Libraries"]', { timeout: 30000 }).should('be.visible');
        cy.get('header button[aria-label="Administration"]', { timeout: 30000 }).should('be.visible');

        navigateToAdminPage('Model Management');

        // Wait for models API to load and check if model already exists
        cy.wait('@getModels', { timeout: 30000 }).then((interception) => {
            const models = interception.response?.body || { models: [] };
            const modelExists = models.models.some((model: any) => model.modelId === testModel.modelId);

            if (modelExists) {
                cy.log(`Model ${testModel.modelId} already exists, skipping creation`);
                testState.modelCreated = true;
            } else {
                openCreateModelWizard();
                fillBedrockModelConfig(testModel);
                completeBedrockModelWizard();
                waitForModelCreationSuccess(testModel.modelId);
                testState.modelCreated = true;
            }
        });
    });

    it('New model appears in Model Management list', function () {
        if (!testState.modelCreated) {
            this.skip();
        }

        navigateToAdminPage('Model Management');
        verifyModelInList(testModel.modelId);
    });

    it('Admin creates a Bedrock Knowledgebase repository (or uses existing)', () => {
        navigateToRepositoryManagement();

        // Wait for repositories API to load and check if repository already exists
        cy.wait('@getRepositories', { timeout: 30000 }).then((interception) => {
            const repositories = interception.response?.body || [];
            const repoExists = repositories.some((repo: any) => repo.repositoryId === testRepository.repositoryId);

            if (repoExists) {
                cy.log(`Repository ${testRepository.repositoryId} already exists, skipping creation`);
                testState.repositoryCreated = true;
            } else {
                openCreateRepositoryWizard();
                fillRepositoryConfig(testRepository);
                selectKnowledgeBase(testRepository.knowledgeBaseName);
                selectDataSource(testRepository.dataSourceIndex);
                skipToCreateRepository();
                completeRepositoryWizard();
                waitForRepositoryCreationSuccess(testRepository.repositoryId);
                testState.repositoryCreated = true;
            }
        });
    });

    it('New repository appears in RAG Management list', function () {
        if (!testState.repositoryCreated) {
            this.skip();
        }

        navigateToRepositoryManagement();
        verifyRepositoryInList(testRepository.repositoryId);
    });

    it('Wait for repository to be fully created and ready', function () {
        if (!testState.repositoryCreated) {
            this.skip();
        }

        navigateToRepositoryManagement();
        waitForRepositoryReady(testRepository.repositoryId, 300000);
        testState.repositoryReady = true;
    });

    it('Rename auto-created collection to known name', function () {
        if (!testState.repositoryReady) {
            this.skip();
        }

        navigateToRagManagement();

        // Get the auto-created collection info (name and ID) and rename it
        getAutoCreatedCollectionInfo(testRepository.repositoryId).then((collectionInfo) => {
            cy.log(`Auto-created collection: ${collectionInfo.name} (ID: ${collectionInfo.id})`);
            testState.collectionId = collectionInfo.id; // Store the collection ID
            renameCollection(collectionInfo.name, testCollection.collectionName);
            testState.collectionRenamed = true;
        });
    });

    it('Upload test document to collection via chat page', function () {
        if (!testState.collectionRenamed) {
            this.skip();
        }

        // Navigate to chat page
        navigateAndVerifyChatPage();

        // Select model, repository, and collection
        selectModelInChat(testModel.modelId);
        selectRagRepositoryInChat(testRepository.repositoryId);
        selectCollectionInChat(testCollection.collectionName);

        // Upload the document
        uploadDocument(testDocumentPath);
        testState.documentUploaded = true;
    });

    it('Wait for document to be ingested', function () {
        if (!testState.documentUploaded) {
            this.skip();
        }
        waitForDocumentIngested(testRepository.repositoryId, testState.collectionId, testDocumentPath, 300000);
        testState.documentIngested = true;
    });

    it('Admin creates a persona prompt template', () => {
        navigateToPromptTemplates();

        promptTemplateExists(testPromptTemplatePersona.title).then((exists) => {
            if (exists) {
                cy.log(`Prompt template ${testPromptTemplatePersona.title} already exists, skipping creation`);
                return;
            }

            openCreatePromptTemplateWizard();
            fillPromptTemplateConfig(testPromptTemplatePersona);
            completePromptTemplateWizard();
            waitForPromptTemplateCreationSuccess(testPromptTemplatePersona.title);
        });
    });

    it('Persona prompt template appears in Prompt Templates list', () => {
        navigateToPromptTemplates();
        verifyPromptTemplateInList(testPromptTemplatePersona.title);
    });

    it('Admin creates a directive prompt template', () => {
        navigateToPromptTemplates();

        promptTemplateExists(testPromptTemplateDirective.title).then((exists) => {
            if (exists) {
                cy.log(`Prompt template ${testPromptTemplateDirective.title} already exists, skipping creation`);
                return;
            }

            openCreatePromptTemplateWizard();
            fillPromptTemplateConfig(testPromptTemplateDirective);
            completePromptTemplateWizard();
            waitForPromptTemplateCreationSuccess(testPromptTemplateDirective.title);
        });
    });

    it('Directive prompt template appears in Prompt Templates list', () => {
        navigateToPromptTemplates();
        verifyPromptTemplateInList(testPromptTemplateDirective.title);
    });

    it('Send chat message with persona and directive', () => {
        navigateAndVerifyChatPage();
        selectModelInChat(testModel.modelId);

        // Apply the Magic 8 Ball persona (system prompt)
        selectPromptTemplateInChat(testPromptTemplatePersona.title, PromptTemplateType.Persona);
        selectPromptTemplateInChat(testPromptTemplateDirective.title, PromptTemplateType.Directive);
        sendMessageWithButton();
        verifyChatResponseReceived();
    });

    it('Send chat message with rag response', () => {
        navigateAndVerifyChatPage();
        selectModelInChat(testModel.modelId);
        selectRagRepositoryInChat(testRepository.repositoryId);
        selectCollectionInChat(testCollection.collectionName);
        insertChatPrompt('Who is Whiskers?');
        sendMessageWithButton();
        verifyChatResponseReceived();
    });

    if (!options.skipCleanup) {
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
}

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
 * Shared test suite for Chat Page features.
 * Can be used by both smoke tests (with fixtures) and e2e tests (with real data).
 */

import {
    navigateAndVerifyChatPage,
    selectSessionByName,
    verifySessionLoaded,
    verifyChatHistory,
} from '../../support/chatHelpers';

const MODEL_INPUT_SELECTOR = 'input[placeholder*="model" i], input[aria-label*="model" i]';
const RAG_REPO_SELECTOR = 'input#rag-repository-autosuggest, input[placeholder*="RAG Repository" i]';
const COLLECTION_SELECTOR = 'input#collection-autosuggest, input[placeholder*="collection" i]';
const MESSAGE_INPUT_SELECTOR = 'textarea[placeholder*="message" i]';
const DROPDOWN_OPTION_SELECTOR = '[role="option"], [role="menuitem"]';

export function runChatTests (options: {
    testSessionSelection?: boolean;
    testRAGConfiguration?: boolean;
} = {}) {
    const { testSessionSelection = false, testRAGConfiguration = false } = options;

    it('User can navigate to chat home page', () => {
        navigateAndVerifyChatPage();
    });

    it('Model dropdown is populated and selectable', () => {
        if (testSessionSelection) {
            cy.fixture('env.json').then((env) => {
                const apiBase = env.API_BASE_URL.replace(/\/+$/, '');

                cy.fixture('models.json').then((modelsData) => {
                    cy.intercept('GET', `**/${apiBase}/models*`, {
                        statusCode: 200,
                        body: modelsData,
                    }).as('getModels');
                });

                navigateAndVerifyChatPage();
                cy.wait('@getModels');

                cy.get(MODEL_INPUT_SELECTOR)
                    .first()
                    .should('exist')
                    .click();

                cy.contains('mistral-vllm').should('be.visible');
                cy.contains('claude-3-7').should('be.visible');
            });
        } else {
            navigateAndVerifyChatPage();

            // Wait for models API call to complete
            cy.get(MODEL_INPUT_SELECTOR, { timeout: 45000 })
                .first()
                .should('be.visible')
                .and('not.be.disabled')
                .click({ force: true });

            // Wait for dropdown options to appear
            cy.get(DROPDOWN_OPTION_SELECTOR)
                .should('be.visible')
                .and('have.length.at.least', 1);
        }
    });

    if (testRAGConfiguration) {
        it('RAG repository and collection dropdowns populate when selected', () => {
            cy.fixture('env.json').then((env) => {
                const apiBase = env.API_BASE_URL.replace(/\/+$/, '');

                cy.fixture('repository.json').then((repos) => {
                    cy.intercept('GET', `**/${apiBase}/repository*`, {
                        statusCode: 200,
                        body: repos,
                    }).as('getRepositories');
                });

                cy.fixture('collections.json').then((collections) => {
                    cy.intercept('GET', `**/${apiBase}/repository/repo-001/collection*`, {
                        statusCode: 200,
                        body: collections,
                    }).as('getCollections');
                });

                navigateAndVerifyChatPage();
                cy.wait('@getRepositories');

                cy.get(RAG_REPO_SELECTOR)
                    .should('be.visible')
                    .clear()
                    .type('Technical');

                cy.get(DROPDOWN_OPTION_SELECTOR)
                    .contains('Technical Documentation')
                    .should('be.visible')
                    .click();

                cy.wait('@getCollections');

                cy.get(RAG_REPO_SELECTOR)
                    .should('have.value', 'repo-001');

                cy.get(COLLECTION_SELECTOR)
                    .should('not.be.disabled')
                    .clear()
                    .type('API');

                cy.get(DROPDOWN_OPTION_SELECTOR)
                    .contains('API Documentation Collection')
                    .should('be.visible');
            });
        });
    } else {
        it('RAG repository dropdown is accessible', () => {
            navigateAndVerifyChatPage();

            cy.get(RAG_REPO_SELECTOR)
                .should('be.visible')
                .and('not.be.disabled')
                .click({ force: true });
        });
    }

    it('Chat interface has message input that requires model selection', () => {
        navigateAndVerifyChatPage();

        // Initially, message input should be disabled until model is selected
        cy.get(MESSAGE_INPUT_SELECTOR)
            .should('be.visible')
            .and('be.disabled');

        // Select a model first
        cy.get(MODEL_INPUT_SELECTOR, { timeout: 45000 })
            .first()
            .should('be.visible')
            .and('not.be.disabled')
            .click({ force: true });

        // Wait for dropdown options and select the first available model
        cy.get(DROPDOWN_OPTION_SELECTOR)
            .should('be.visible')
            .and('have.length.at.least', 1)
            .first()
            .click();

        // Now message input should be enabled
        cy.get(MESSAGE_INPUT_SELECTOR)
            .should('be.visible')
            .and('not.be.disabled');
    });

    if (testSessionSelection) {
        it('User can select a session from history', () => {
            cy.fixture('env.json').then((env) => {
                const apiBase = env.API_BASE_URL.replace(/\/+$/, '');

                cy.fixture('session-detail.json').then((session) => {
                    cy.intercept('GET', `**/${apiBase}/session/f56fc284-629c-4ba7-ab3d-56f4a21c13ee`, {
                        statusCode: 200,
                        body: session,
                    }).as('getSession');
                });

                navigateAndVerifyChatPage();
                cy.wait('@stubSession');

                selectSessionByName('Technical Discussion');

                cy.wait('@getSession');
                verifySessionLoaded('f56fc284-629c-4ba7-ab3d-56f4a21c13ee');
            });
        });

        it('Chat interface displays session history when session is loaded', () => {
            cy.fixture('env.json').then((env) => {
                const apiBase = env.API_BASE_URL.replace(/\/+$/, '');

                cy.fixture('session-detail.json').then((session) => {
                    cy.intercept('GET', `**/${apiBase}/session/f56fc284-629c-4ba7-ab3d-56f4a21c13ee`, {
                        statusCode: 200,
                        body: session,
                    }).as('getSession');
                });

                navigateAndVerifyChatPage();
                cy.wait('@stubSession');

                selectSessionByName('Technical Discussion');
                cy.wait('@getSession');

                verifySessionLoaded('f56fc284-629c-4ba7-ab3d-56f4a21c13ee');
                verifyChatHistory([
                    'What is the difference between REST and GraphQL?',
                    'REST and GraphQL are both API architectures'
                ]);
            });
        });

        it('Model selector shows correct model from loaded session', () => {
            cy.fixture('env.json').then((env) => {
                const apiBase = env.API_BASE_URL.replace(/\/+$/, '');

                cy.fixture('session-detail.json').then((session) => {
                    cy.intercept('GET', `**/${apiBase}/session/f56fc284-629c-4ba7-ab3d-56f4a21c13ee`, {
                        statusCode: 200,
                        body: session,
                    }).as('getSession');
                });

                cy.fixture('models.json').then((modelsData) => {
                    cy.intercept('GET', `**/${apiBase}/models*`, {
                        statusCode: 200,
                        body: modelsData,
                    }).as('getModels');
                });

                navigateAndVerifyChatPage();
                cy.visit('#/ai-assistant/f56fc284-629c-4ba7-ab3d-56f4a21c13ee');

                cy.wait('@getSession');
                cy.wait('@getModels');

                cy.get(MODEL_INPUT_SELECTOR)
                    .should('have.value', 'mistral-vllm');
            });
        });

        it('RAG configuration loads from session', () => {
            cy.fixture('env.json').then((env) => {
                const apiBase = env.API_BASE_URL.replace(/\/+$/, '');

                cy.fixture('session-detail.json').then((session) => {
                    cy.intercept('GET', `**/${apiBase}/session/f56fc284-629c-4ba7-ab3d-56f4a21c13ee`, {
                        statusCode: 200,
                        body: session,
                    }).as('getSession');
                });

                cy.fixture('repository.json').then((repos) => {
                    cy.intercept('GET', `**/${apiBase}/repository*`, {
                        statusCode: 200,
                        body: repos,
                    }).as('getRepositories');
                });

                cy.fixture('collections.json').then((collections) => {
                    cy.intercept('GET', `**/${apiBase}/collections*`, {
                        statusCode: 200,
                        body: collections,
                    }).as('getCollections');
                });

                navigateAndVerifyChatPage();
                cy.visit('#/ai-assistant/f56fc284-629c-4ba7-ab3d-56f4a21c13ee');

                cy.wait('@getSession');

                cy.get(RAG_REPO_SELECTOR)
                    .should('have.value', 'repo-001');

                cy.get(COLLECTION_SELECTOR)
                    .should('not.be.disabled')
                    .and('have.value', 'API Documentation Collection');
            });
        });
    }
}

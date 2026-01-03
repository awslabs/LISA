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
 * E2E suite for Chat Page features:
 * - Verifies chat page loads correctly
 * - Tests session selection and loading
 * - Validates model, RAG repository, and collection dropdowns
 */

import {
    navigateAndVerifyChatPage,
    selectSessionByName,
    verifySessionLoaded,
    verifyChatHistory,
} from '../../support/chatHelpers';

describe('Chat Page (Smoke)', () => {
    beforeEach(() => {
        cy.loginAs('user');
    });

    it('User can navigate to chat home page', () => {
        navigateAndVerifyChatPage();
    });

    it('User can select a session from history', () => {
        cy.fixture('env.json').then((env) => {
            const apiBase = env.API_BASE_URL.replace(/\/+$/, '');
            
            // Intercept individual session fetch
            cy.fixture('session-detail.json').then((session) => {
                cy.intercept('GET', `**/${apiBase}/session/f56fc284-629c-4ba7-ab3d-56f4a21c13ee`, {
                    statusCode: 200,
                    body: session,
                }).as('getSession');
            });

            navigateAndVerifyChatPage();
            
            // Wait for sessions to load (from default stub)
            cy.wait('@stubSession');
            
            // Select session from history
            selectSessionByName('Technical Discussion');
            
            // Verify the session loads
            cy.wait('@getSession');
            verifySessionLoaded('f56fc284-629c-4ba7-ab3d-56f4a21c13ee');
        });
    });

    it('Model dropdown is populated and selectable', () => {
        cy.fixture('env.json').then((env) => {
            const apiBase = env.API_BASE_URL.replace(/\/+$/, '');
            
            // Wait for models to load
            cy.fixture('models.json').then((modelsData) => {
                cy.intercept('GET', `**/${apiBase}/models*`, {
                    statusCode: 200,
                    body: modelsData,
                }).as('getModels');
            });

            navigateAndVerifyChatPage();
            cy.wait('@getModels');
            
            // Find and interact with model selector
            // The Chat component uses Autosuggest for model selection
            cy.get('input[placeholder*="model" i], input[aria-label*="model" i]', { timeout: 10000 })
                .first()
                .should('exist')
                .click();
            
            // Verify models appear in dropdown
            cy.contains('mistral-vllm').should('be.visible');
            cy.contains('claude-3-7').should('be.visible');
        });
    });

    it('RAG repository and collection dropdowns populate when selected', () => {
        cy.fixture('env.json').then((env) => {
            const apiBase = env.API_BASE_URL.replace(/\/+$/, '');
            
            // Intercept repository and collection API calls
            cy.fixture('repository.json').then((repos) => {
                cy.intercept('GET', `**/${apiBase}/repository*`, {
                    statusCode: 200,
                    body: repos,
                }).as('getRepositories');
            });

            // Intercept collections for the specific repository
            cy.fixture('collections.json').then((collections) => {
                cy.intercept('GET', `**/${apiBase}/repository/repo-001/collection*`, {
                    statusCode: 200,
                    body: collections,
                }).as('getCollections');
            });

            navigateAndVerifyChatPage();
            
            // Wait for repositories to load
            cy.wait('@getRepositories', { timeout: 10000 });
            
            // Click on the RAG repository input to open dropdown
            cy.get('input#rag-repository-autosuggest, input[placeholder*="RAG Repository" i]')
                .should('be.visible')
                .clear()
                .type('Technical');
            
            // Wait for dropdown to be visible and select repository
            cy.get('[role="option"], [role="menuitem"]')
                .contains('Technical Documentation', { timeout: 10000 })
                .should('be.visible')
                .click();
            
            // Wait for collections to load after repository selection
            cy.wait('@getCollections', { timeout: 10000 });
            
            // Verify the repository was selected
            cy.get('input#rag-repository-autosuggest, input[placeholder*="RAG Repository" i]')
                .should('have.value', 'repo-001');
            
            // Verify collections dropdown is now enabled and populated
            cy.get('input#collection-autosuggest, input[placeholder*="collection" i]')
                .should('not.be.disabled');
            
            // Click on collection input to verify collections are available
            cy.get('input#collection-autosuggest, input[placeholder*="collection" i]')
                .clear()
                .type('API');
            
            cy.get('[role="option"], [role="menuitem"]')
                .contains('API Documentation Collection', { timeout: 10000 })
                .should('be.visible');
        });
    });

    it('Chat interface displays session history when session is loaded', () => {
        cy.fixture('env.json').then((env) => {
            const apiBase = env.API_BASE_URL.replace(/\/+$/, '');
            
            // Intercept session fetch
            cy.fixture('session-detail.json').then((session) => {
                cy.intercept('GET', `**/${apiBase}/session/f56fc284-629c-4ba7-ab3d-56f4a21c13ee`, {
                    statusCode: 200,
                    body: session,
                }).as('getSession');
            });

            navigateAndVerifyChatPage();
            
            // Wait for sessions to load (from default stub)
            cy.wait('@stubSession');
            
            // Click on the session in the history list
            selectSessionByName('Technical Discussion');
            
            // Wait for session to load
            cy.wait('@getSession');
            
            // Verify we're on the correct session URL
            verifySessionLoaded('f56fc284-629c-4ba7-ab3d-56f4a21c13ee');
            
            // Verify chat history is displayed
            verifyChatHistory([
                'What is the difference between REST and GraphQL?',
                'REST and GraphQL are both API architectures'
            ]);
        });
    });

    it('Model selector shows correct model from loaded session', () => {
        cy.fixture('env.json').then((env) => {
            const apiBase = env.API_BASE_URL.replace(/\/+$/, '');
            
            // Intercept session fetch with specific model configuration
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
            
            // Wait for session and models to load
            cy.wait('@getSession');
            cy.wait('@getModels');
            
            // Verify the model from the session is selected
            cy.get('input[placeholder*="model" i], input[aria-label*="model" i]')
                .should('have.value', 'mistral-vllm');
        });
    });

    it('RAG configuration loads from session', () => {
        cy.fixture('env.json').then((env) => {
            const apiBase = env.API_BASE_URL.replace(/\/+$/, '');
            
            // Intercept session fetch with RAG configuration
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
            
            // Wait for session to load
            cy.wait('@getSession');
            
            // Verify RAG repository is loaded in the input (shows repo ID as value)
            cy.get('input#rag-repository-autosuggest, input[placeholder*="RAG Repository" i]', { timeout: 10000 })
                .should('have.value', 'repo-001');
            
            // Verify collection is loaded in the input
            cy.get('input#collection-autosuggest, input[placeholder*="collection" i]', { timeout: 10000 })
                .should('not.be.disabled')
                .and('have.value', 'API Documentation Collection');
        });
    });
});

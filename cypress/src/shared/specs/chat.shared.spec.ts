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
 *
 * Interceptors should be set up in beforeEach by the calling spec.
 */

import {
    navigateAndVerifyChatPage,
    getModelInput,
    getRagRepoInput,
    getMessageInput,
    getDropdownOptions,
    selectModel,
} from '../../support/chatHelpers';

export function runChatTests (options: {
    verifyFixtureData?: boolean;
} = {}) {
    const { verifyFixtureData = false } = options;

    it('Model dropdown is populated and selectable', () => {
        navigateAndVerifyChatPage();

        // Wait for models to load
        cy.wait('@getModels', { timeout: 30000 });

        getModelInput()
            .should('be.visible')
            .and('not.be.disabled')
            .click({ force: true });

        // Wait for dropdown options to appear
        getDropdownOptions()
            .should('be.visible')
            .and('have.length.at.least', 1);

        if (verifyFixtureData) {
            cy.contains('mistral-vllm').should('be.visible');
            cy.contains('claude-3-7').should('be.visible');
        }
    });

    it('RAG repository dropdown is accessible', () => {
        navigateAndVerifyChatPage();

        // Wait for repositories to load
        cy.wait('@getRepositories', { timeout: 30000 });

        getRagRepoInput()
            .should('be.visible')
            .and('not.be.disabled')
            .click({ force: true });

        if (verifyFixtureData) {
            getDropdownOptions()
                .should('be.visible');
            cy.contains('Technical Documentation').should('be.visible');
        }
    });

    it('Chat interface has message input that requires model selection', () => {
        navigateAndVerifyChatPage();

        // Wait for models to load
        cy.wait('@getModels', { timeout: 30000 });

        // Initially, message input should be disabled until model is selected
        getMessageInput()
            .should('be.visible')
            .and('be.disabled');

        // Select a model
        selectModel();

        // Now message input should be enabled
        getMessageInput()
            .should('be.visible')
            .and('not.be.disabled');
    });
}

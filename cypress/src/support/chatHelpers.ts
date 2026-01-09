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

/**
 * chatHelpers.ts
 * Contains reusable helpers for chat page navigation and verification.
 */

// Chat page selectors
export const CHAT_SELECTORS = {
    MODEL_INPUT: 'input[placeholder*="model" i], input[aria-label*="model" i]',
    RAG_REPO_INPUT: 'input#rag-repository-autosuggest, input[placeholder*="RAG Repository" i]',
    COLLECTION_INPUT: 'input#collection-autosuggest, input[placeholder*="collection" i]',
    MESSAGE_INPUT: 'textarea[placeholder*="message" i]',
    DROPDOWN_OPTION: '[role="option"], [role="menuitem"]',
};

/**
 * Navigate to the AI Assistant (chat) page by clicking the menu item
 */
export function navigateToChatPage () {
    // For e2e tests, login should already direct to chat page
    // For smoke tests, we may need to click the menu item
    // Check if we're already on the chat page
    cy.url().then((url) => {
        if (!url.includes('/ai-assistant')) {
            cy.get('a[aria-label="AI Assistant"]')
                .eq(2)
                .should('exist')
                .and('be.visible')
                .click();
        }
    });
}

/**
 * Verify that the chat page has loaded correctly
 */
export function verifyChatPageLoaded () {
    cy.url().should('include', '/ai-assistant');

    // Wait for the prompt input textarea to be visible
    // Use attribute selectors that are stable across builds
    cy.get('textarea[placeholder*="message" i]')
        .first()
        .should('exist')
        .and('be.visible');
}

/**
 * Wait for initial API calls to complete
 * This prevents cancelled requests when interacting with dropdowns too early
 */
export function waitForInitialDataLoad () {
    // Wait for any loading spinners to disappear
    cy.get('[data-testid="loading"], .awsui-spinner, .loading', { timeout: 5000 })
        .should('not.exist');

    // Give the page more time to stabilize after auth and initial API calls
    cy.wait(3000);
}

/**
 * Navigate to chat page and verify it loaded
 */
export function navigateAndVerifyChatPage () {
    navigateToChatPage();
    verifyChatPageLoaded();
    waitForInitialDataLoad();
}

/**
 * Wait for chat sessions to load in the sidebar
 */
export function waitForSessionsToLoad () {
    // Wait for loading state to complete
    cy.get('[data-testid="loading"], .awsui-spinner, .loading')
        .should('not.exist');
}

/**
 * Select a session from the history sidebar by name
 * @param sessionName - The name of the session to select
 */
export function selectSessionByName (sessionName: string) {
    cy.contains(sessionName)
        .should('be.visible')
        .click();
}

/**
 * Verify that a session has loaded with its history
 * @param sessionId - The expected session ID in the URL
 */
export function verifySessionLoaded (sessionId: string) {
    cy.url().should('include', `/ai-assistant/${sessionId}`);
}

/**
 * Verify that chat history messages are displayed
 * @param messageTexts - Array of message text snippets to verify
 */
export function verifyChatHistory (messageTexts: string[]) {
    messageTexts.forEach((text) => {
        cy.contains(text).should('be.visible');
    });
}


/**
 * Get the model input element
 */
export function getModelInput (): Cypress.Chainable {
    return cy.get(CHAT_SELECTORS.MODEL_INPUT).first();
}

/**
 * Get the RAG repository input element
 */
export function getRagRepoInput (): Cypress.Chainable {
    return cy.get(CHAT_SELECTORS.RAG_REPO_INPUT);
}

/**
 * Get the message input textarea
 */
export function getMessageInput (): Cypress.Chainable {
    return cy.get(CHAT_SELECTORS.MESSAGE_INPUT);
}

/**
 * Get dropdown options
 */
export function getDropdownOptions (): Cypress.Chainable {
    return cy.get(CHAT_SELECTORS.DROPDOWN_OPTION);
}

/**
 * Select a model from the dropdown
 * @param modelName - Optional specific model name to select, otherwise selects first available
 */
export function selectModel (modelName?: string) {
    getModelInput()
        .should('be.visible')
        .and('not.be.disabled')
        .click({ force: true });

    if (modelName) {
        getDropdownOptions()
            .contains(modelName)
            .click();
    } else {
        getDropdownOptions()
            .should('be.visible')
            .first()
            .click();
    }
}

/**
 * Send a message that's already in the input field by clicking the send button
 */
export function sendMessageWithButton () {
    cy.get('button[aria-label="Send message"]')
        .should('be.visible')
        .and('not.be.disabled')
        .click();
}

/**
 * Verify that a chat response was received
 * @param minMessages - Minimum number of messages expected (default: 2 for user + assistant)
 */
export function verifyChatResponseReceived (minMessages: number = 2) {
    cy.get('[data-testid="chat-message"]', { timeout: 30000 })
        .should('have.length.at.least', minMessages);
}

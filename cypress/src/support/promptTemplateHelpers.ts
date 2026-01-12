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
 * promptTemplateHelpers.ts
 * Contains reusable helpers for prompt template creation and management.
 */

export type PromptTemplateConfig = {
    title: string;
    body: string;
    type?: 'system' | 'user';
    sharePublic?: boolean;
};

/**
 * Navigate to Prompt Templates Library page
 */
export function navigateToPromptTemplates () {
    cy.get('header button[aria-label="Libraries"]')
        .should('be.visible')
        .click()
        .should('have.attr', 'aria-expanded', 'true');

    cy.get('[role="menu"][aria-label="Libraries"]')
        .should('be.visible')
        .find('[data-testid="prompt-template"]')
        .should('be.visible')
        .click();

    cy.url().should('include', '/prompt-templates');
}

/**
 * Open the Create Prompt Template wizard
 */
export function openCreatePromptTemplateWizard () {
    cy.contains('button', 'Create Prompt Template')
        .should('be.visible')
        .and('not.be.disabled')
        .click();

    cy.url().should('include', '/prompt-templates/new');
}

/**
 * Fill in the prompt template form
 */
export function fillPromptTemplateConfig (config: PromptTemplateConfig) {
    // Wait for form to be ready
    cy.get('[data-testid="prompt-template-title-input"]')
        .should('exist');

    // Fill in title using data-testid - find the actual input element
    cy.get('[data-testid="prompt-template-title-input"]')
        .find('input')
        .should('be.visible')
        .clear()
        .type(config.title);

    // Select type if specified
    if (config.type) {
        cy.get('[data-testid="prompt-template-type-select"]')
            .should('be.visible')
            .click();

        const typeLabel = config.type === 'system' ? 'Persona' : 'Directive';
        cy.get('[role="listbox"]')
            .should('be.visible')
            .contains('[role="option"]', typeLabel)
            .click();
    }

    // Set share public toggle if specified
    if (config.sharePublic !== undefined) {
        cy.get('[data-testid="prompt-template-share-public-toggle"]')
            .find('input[type="checkbox"]')
            .then(($checkbox) => {
                const isChecked = $checkbox.is(':checked');
                if (isChecked !== config.sharePublic) {
                    cy.wrap($checkbox).click({ force: true });
                }
            });
    }

    // Fill in prompt body using data-testid - find the actual textarea element
    cy.get('[data-testid="prompt-template-body-textarea"]')
        .find('textarea')
        .should('be.visible')
        .clear()
        .type(config.body, { delay: 0 });
}

/**
 * Complete the prompt template creation
 */
export function completePromptTemplateWizard () {
    cy.contains('button', 'Create Template')
        .should('be.visible')
        .and('not.be.disabled')
        .click();
}

/**
 * Wait for prompt template creation to succeed
 */
export function waitForPromptTemplateCreationSuccess (templateTitle: string) {
    // Wait for redirect back to list
    cy.url().should('match', /\/prompt-templates\/?$/);

    // Wait for success notification
    cy.contains(`Successfully created Prompt Template: ${templateTitle}`, { timeout: 10000 })
        .should('be.visible');
}

/**
 * Verify prompt template appears in the list
 */
export function verifyPromptTemplateInList (templateTitle: string) {
    cy.contains('td', templateTitle, { timeout: 10000 })
        .should('be.visible');
}

/**
 * Delete a prompt template if it exists
 */
export function deletePromptTemplateIfExists (templateTitle: string) {
    cy.get('body').then(($body) => {
        if ($body.text().includes(templateTitle)) {
            // Select the template by clicking its radio button
            cy.contains('tr', templateTitle)
                .find('input[type="radio"]')
                .click({ force: true });

            // Click the Actions dropdown
            cy.get('[data-testid="prompt-template-actions-dropdown"]')
                .should('be.visible')
                .and('not.be.disabled')
                .click();

            // Click Delete from the dropdown menu
            cy.contains('[role="menuitem"]', 'Delete')
                .should('be.visible')
                .click();

            // Wait for confirmation modal and click Delete button
            cy.get('[data-testid="confirmation-modal-delete-btn"]', { timeout: 5000 })
                .should('be.visible')
                .click();

            // Wait for success notification
            cy.contains(`Successfully deleted Prompt Template: ${templateTitle}`, { timeout: 10000 })
                .should('be.visible');
        }
    });
}

/**
 * Select a prompt template in chat
 * @param templateTitle - The title of the template to select
 * @param templateType - The type of template ('system' for Persona, 'user' for Directive)
 */
export function selectPromptTemplateInChat (templateTitle: string, templateType: 'system' | 'user' = 'user') {
    if (templateType === 'system') {
        // For Persona templates, use the "Edit Persona" button in Additional Configuration dropdown
        cy.contains('button', 'Additional Configuration')
            .should('be.visible')
            .click();

        cy.contains('[role="menuitem"]', 'Edit Persona')
            .should('be.visible')
            .click();
    } else {
        // For Directive templates, use the "Insert Prompt Template" button
        cy.get('button[aria-label="Insert Prompt Template"]')
            .should('be.visible')
            .click();
    }

    // Wait for modal to open
    cy.get('[role="dialog"]')
        .should('be.visible')
        .within(() => {
            // Search for and select the template
            cy.get('input[placeholder="Search by title"]')
                .should('be.visible')
                .type(templateTitle);

            // Select from the dropdown
            cy.contains('[role="option"]', templateTitle)
                .should('be.visible')
                .click();

            // Click the Use button
            const buttonText = templateType === 'system' ? 'Use Persona' : 'Use Prompt';
            cy.contains('button', buttonText)
                .should('be.visible')
                .and('not.be.disabled')
                .click();
        });

    // Wait for modal to close
    cy.get('[role="dialog"]').should('not.exist');
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

/**
 * Select a directive prompt template, which inserts text into the message input, then send it
 * @param templateTitle - The title of the directive template to select
 */
export function selectDirectiveAndSend (templateTitle: string) {
    selectPromptTemplateInChat(templateTitle, 'user');
    sendMessageWithButton();
    verifyChatResponseReceived();
}

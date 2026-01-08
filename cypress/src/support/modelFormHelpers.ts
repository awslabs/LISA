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
 * modelFormHelpers.ts
 * Reusable helpers for model creation wizard interactions.
 */

export type BedrockModelConfig = {
    modelId: string;
    modelName: string;
    modelDescription?: string;
    streaming?: boolean;
};

/**
 * Open the Create Model wizard modal
 */
export function openCreateModelWizard () {
    cy.contains('button', 'Create Model').should('be.visible').click();
    cy.contains('Base Model Configuration').should('be.visible');
}

/**
 * Fill in the base model configuration for a third-party (Bedrock) model
 */
export function fillBedrockModelConfig (config: BedrockModelConfig) {
    cy.get('input[placeholder="mistral-vllm"]').clear().type(config.modelId);
    cy.get('input[placeholder*="mistralai/Mistral"]').clear().type(config.modelName);

    if (config.modelDescription) {
        cy.get('input[placeholder*="Brief description"]').clear().type(config.modelDescription);
    }

    if (config.streaming) {
        cy.get('[data-testid="streaming-toggle"]')
            .find('input[type="checkbox"]')
            .then(($checkbox) => {
                if (!$checkbox.is(':checked')) {
                    cy.wrap($checkbox).click({ force: true });
                }
            });
    }
}

/**
 * Navigate through wizard steps for a third-party model and submit
 */
export function completeBedrockModelWizard () {
    // Step 1 -> Guardrails (skip LISA-hosted steps)
    cy.contains('button', 'Next').click();
    cy.contains('Guardrails Configuration', { timeout: 5000 }).should('be.visible');

    // Guardrails -> Review
    cy.contains('button', 'Next').click();
    cy.contains('Review and Create', { timeout: 5000 }).should('be.visible');

    // Submit - target the primary button within the wizard container
    cy.get('[data-testid="create-model-wizard"]')
        .contains('button', 'Create Model')
        .click();
}

/**
 * Wait for model creation success notification
 */
export function waitForModelCreationSuccess (modelId: string) {
    cy.contains(`Successfully created model: ${modelId}`, { timeout: 30000 }).should('be.visible');
}

/**
 * Verify model appears in the model management list
 */
export function verifyModelInList (modelId: string) {
    cy.contains(modelId, { timeout: 10000 }).should('be.visible');
}

/**
 * Delete a model by ID (for cleanup)
 */
export function deleteModelIfExists (modelId: string) {
    cy.get('body').then(($body) => {
        if ($body.text().includes(modelId)) {
            // Select the model card by clicking its radio button
            cy.get(`[data-testid="model-card-${modelId}"]`)
                .closest('[data-selection-item="item"]')
                .find('input[type="radio"]')
                .click({ force: true });

            // Click the Actions dropdown
            cy.get('[data-testid="model-actions-dropdown"]').click();

            // Click Delete from the dropdown menu
            cy.contains('[role="menuitem"]', 'Delete').click();

            // Wait for confirmation modal and click Delete button
            cy.get('[data-testid="confirmation-modal-delete-btn"]', { timeout: 5000 })
                .should('be.visible')
                .click();

            cy.wait(2000);
        }
    });
}

/**
 * Select a model in the chat interface
 */
export function selectModelInChat (modelId: string) {
    cy.get('input[placeholder*="model" i], input[aria-label*="model" i]', { timeout: 45000 })
        .first()
        .should('not.be.disabled')
        .click({ force: true })
        .type(modelId);

    cy.get('[role="option"], [role="menuitem"]')
        .contains(modelId)
        .should('be.visible')
        .click();
}

/**
 * Send a chat message and wait for response
 * Sets up an intercept for the inference API before sending
 */
export function sendChatMessage (message: string) {
    // Intercept the chat completions API call
    cy.intercept('POST', '**/v2/serve/chat/completions').as('chatInference');

    cy.get('textarea[placeholder*="message" i]')
        .should('not.be.disabled')
        .type(message);

    cy.get('button[aria-label="Send message"]').click();
}

/**
 * Verify chat received a response by waiting for the inference API to complete
 */
export function verifyChatResponse (userMessage: string) {
    // Wait for the inference API call to complete
    cy.wait('@chatInference', { timeout: 60000 }).then((interception) => {
        expect(interception.response.statusCode).to.be.oneOf([200, 201]);
    });

    // Verify the user message is displayed
    cy.contains(userMessage).should('be.visible');

    // Verify at least 2 messages exist (user + AI response)
    cy.get('[class*="message"], [data-testid*="message"]', { timeout: 10000 })
        .should('have.length.at.least', 2);

    // Verify no error indicators
    cy.get('[class*="status-indicator-error"]').should('not.exist');
}

/**
 * Delete all chat sessions for the current user
 */
export function deleteAllSessions () {
    // Click the Delete All Sessions button
    cy.get('button[aria-label="Delete All Sessions"]')
        .should('be.visible')
        .click();

    // Wait for confirmation modal and click Delete button
    cy.get('[data-testid="confirmation-modal-delete-btn"]', { timeout: 5000 })
        .should('be.visible')
        .click();

    // Wait for deletion to complete
    cy.wait(2000);
}

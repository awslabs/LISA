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
 * repositoryHelpers.ts
 * Reusable helpers for repository creation and management interactions.
 */

export type RepositoryConfig = {
    repositoryId: string;
    knowledgeBaseName: string;
    dataSourceIndex?: number;
};

/**
 * Check if a repository exists in the repository management list
 * @returns Cypress.Chainable<boolean>
 */
export function repositoryExists (repositoryId: string): Cypress.Chainable<boolean> {
    return cy.get('body').then(($body) => {
        return $body.text().includes(repositoryId);
    });
}

/**
 * Navigate to the repository management page
 */
export function navigateToRepositoryManagement () {
    cy.visit('/#/repository-management');
    cy.url().should('include', '/repository-management');
    cy.wait(1000);
}

/**
 * Open the Create Repository wizard modal
 */
export function openCreateRepositoryWizard () {
    cy.contains('button', 'Create Repository').should('be.visible').click();
    cy.contains('Repository Configuration').should('be.visible');
}

/**
 * Fill in the repository configuration with Bedrock Knowledge Base type
 */
export function fillRepositoryConfig (config: RepositoryConfig) {
    // Set up intercept for knowledge bases API before selecting repository type
    cy.intercept('GET', '**/bedrock-kb').as('getKnowledgeBases');

    // Fill repository ID
    cy.get('[data-testid="repository-id-input"]')
        .should('be.visible')
        .clear()
        .type(config.repositoryId);

    // Select repository type: BEDROCK_KNOWLEDGE_BASE
    cy.get('[data-testid="repository-type-select"]')
        .find('button')
        .click();

    cy.get('[role="option"]')
        .contains('BEDROCK_KNOWLEDGE_BASE')
        .should('be.visible')
        .click();

    // Wait for knowledge bases to load after selecting repository type
    cy.wait('@getKnowledgeBases', { timeout: 30000 });
}

/**
 * Wait for knowledge bases to load and select a specific one
 */
export function selectKnowledgeBase (knowledgeBaseName: string) {
    // Set up intercept for data sources API before selecting KB
    cy.intercept('GET', '**/bedrock-kb/*/data-sources').as('getDataSources');

    // Wait for the select to be visible (API already loaded in fillRepositoryConfig)
    cy.get('[data-testid="knowledge-base-select"]').should('be.visible');

    // Click the Knowledge Base dropdown button
    cy.get('[data-testid="knowledge-base-select"]')
        .find('button')
        .click();

    // Select the knowledge base by name
    cy.get('[role="option"]')
        .contains(knowledgeBaseName)
        .should('be.visible')
        .click();

    // Wait for data sources to load after selecting KB
    cy.wait('@getDataSources', { timeout: 30000 });
}

/**
 * Wait for data sources to load and select one by index
 */
export function selectDataSource (index: number = 0) {
    // Data sources API already loaded in selectKnowledgeBase
    // Wait for the table to be visible
    cy.get('[data-testid="data-sources-table"]').should('be.visible');

    // Wait for table rows to be present
    cy.get('[data-testid="data-sources-table"] tbody tr[data-selection-item="item"]')
        .should('have.length.at.least', 1);

    // Select the data source checkbox by index
    cy.get('[data-testid="data-sources-table"] tbody tr[data-selection-item="item"]')
        .eq(index)
        .find('input[type="checkbox"]')
        .first()
        .click({ force: true });
}

/**
 * Skip to the create step in the repository wizard
 */
export function skipToCreateRepository () {
    cy.contains('button', 'Skip to Create')
        .scrollIntoView()
        .should('be.visible')
        .click();
}

/**
 * Complete the repository creation wizard
 */
export function completeRepositoryWizard () {
    // Scope the Create Repository button to the modal to avoid clicking the page button
    cy.get('[data-testid="create-repository-modal"]')
        .contains('button', 'Create Repository')
        .should('be.visible')
        .should('not.be.disabled')
        .click();
}

/**
 * Wait for repository creation success notification
 */
export function waitForRepositoryCreationSuccess (repositoryId: string) {
    cy.contains(`Successfully created repository: ${repositoryId}`, { timeout: 30000 })
        .should('be.visible');
}

/**
 * Verify repository appears in the repository management list
 */
export function verifyRepositoryInList (repositoryId: string) {
    cy.contains(repositoryId, { timeout: 10000 }).should('be.visible');
}

/**
 * Delete a repository by ID (for cleanup)
 */
export function deleteRepositoryIfExists (repositoryId: string) {
    cy.get('body').then(($body) => {
        if ($body.text().includes(repositoryId)) {
            // Select the repository
            cy.contains(repositoryId)
                .closest('tr, [data-testid*="repository"]')
                .find('input[type="radio"], input[type="checkbox"]')
                .first()
                .click({ force: true });

            // Click the Actions dropdown or Delete button
            cy.get('[data-testid="repository-actions-dropdown"], button')
                .contains(/actions|delete/i)
                .click();

            // Click Delete from the dropdown menu if needed
            cy.get('body').then(($body) => {
                if ($body.find('[role="menuitem"]').length > 0) {
                    cy.contains('[role="menuitem"]', 'Delete').click();
                }
            });

            // Wait for confirmation modal and click Delete button
            cy.get('[data-testid="confirmation-modal-delete-btn"]', { timeout: 5000 })
                .should('be.visible')
                .click();

            cy.wait(2000);
        }
    });
}

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
 * collectionHelpers.ts
 * Reusable helpers for RAG collection management and document operations.
 */

export type CollectionConfig = {
    collectionId: string;
    collectionName: string;
    repositoryId: string;
};

/**
 * Navigate to the RAG Management page
 */
export function navigateToRagManagement () {
    cy.visit('/#/repository-management');
    cy.url().should('include', '/repository-management');
    cy.wait(1000);
}

/**
 * Get the API base URL from the application's environment
 */
function getApiBaseUrl (): Cypress.Chainable<string> {
    return cy.window().then((win: any) => {
        const apiBaseUrl = win.env?.API_BASE_URL || '';
        return apiBaseUrl.replace(/\/+$/, ''); // Remove trailing slashes
    });
}

/**
 * Get the authentication token from session storage
 */
function getAuthToken (): Cypress.Chainable<string | null> {
    return cy.window().then((win) => {
        // Find the OIDC token in sessionStorage
        const oidcKey = Object.keys(win.sessionStorage).find((key) => key.startsWith('oidc.user:'));
        if (oidcKey) {
            const oidcData = JSON.parse(win.sessionStorage.getItem(oidcKey) || '{}');
            return oidcData.id_token || oidcData.access_token || null;
        }
        return null;
    });
}

/**
 * Make an authenticated API request
 * @param method - HTTP method (GET, POST, PUT, DELETE, etc.)
 * @param path - API path (e.g., '/repository', '/collections')
 * @param options - Additional request options (body, headers, etc.)
 */
function makeAuthenticatedRequest (
    method: string,
    path: string,
    options: Partial<Cypress.RequestOptions> = {}
): Cypress.Chainable<Cypress.Response<any>> {
    return getApiBaseUrl().then((apiBaseUrl) => {
        return getAuthToken().then((token) => {
            return cy.request({
                method,
                url: `${apiBaseUrl}${path}`,
                headers: {
                    ...(token ? { Authorization: `Bearer ${token}` } : {}),
                    ...(options.headers || {}),
                },
                failOnStatusCode: false,
                ...options,
            });
        });
    });
}

/**
 * Wait for repository to be fully created (up to 5 minutes)
 * Checks repository status until it's CREATE_COMPLETE or UPDATE_COMPLETE
 */
export function waitForRepositoryReady (repositoryId: string, timeoutMs: number = 300000) {
    cy.log(`Waiting for repository ${repositoryId} to be ready...`);

    const startTime = Date.now();
    const checkInterval = 10000; // Check every 10 seconds

    function checkRepositoryStatus (): Cypress.Chainable {
        return makeAuthenticatedRequest('GET', '/repository').then((response) => {
            if (response.status === 200 && Array.isArray(response.body)) {
                const repository = response.body.find((repo: any) => repo.repositoryId === repositoryId);

                if (repository) {
                    cy.log(`Repository ${repositoryId} status: ${repository.status}`);

                    if (repository.status === 'CREATE_COMPLETE' || repository.status === 'UPDATE_COMPLETE') {
                        cy.log(`Repository ${repositoryId} is ready with status: ${repository.status}`);
                        return cy.wrap(null); // Success - stop checking
                    }

                    if (repository.status === 'CREATE_FAILED' || repository.status === 'UPDATE_FAILED') {
                        throw new Error(`Repository ${repositoryId} creation failed with status: ${repository.status}`);
                    }
                }
            }

            const elapsed = Date.now() - startTime;
            if (elapsed < timeoutMs) {
                return cy.wait(checkInterval).then(() => checkRepositoryStatus());
            } else {
                throw new Error(`Repository ${repositoryId} did not become ready within ${timeoutMs}ms`);
            }
        });
    }

    checkRepositoryStatus();
}

/**
 * Rename a collection via the collections table
 * Finds the auto-created collection and renames it to a known name
 */
export function renameCollection (oldName: string, newName: string) {
    cy.log(`Renaming collection from "${oldName}" to "${newName}"`);

    // Find the collection row by the link text (collection name is in a link)
    cy.contains('a', oldName)
        .should('be.visible')
        .closest('tr')
        .within(() => {
            // Select the radio button for this row
            cy.get('input[type="radio"]')
                .first()
                .click({ force: true });
        });

    // Click the Actions button using data-testid (find button within the wrapper)
    cy.get('[data-testid="collection-actions-button"]')
        .find('button')
        .should('be.visible')
        .and('not.be.disabled')
        .click();

    // Click Edit from the dropdown menu (data-testid is on the li element)
    cy.get('li[data-testid="edit"]')
        .should('be.visible')
        .click();

    // Wait for the edit modal/wizard to open
    cy.get('[role="dialog"]').should('be.visible');

    // Update the collection name in the form (look for input with label "Collection Name")
    cy.get('label')
        .contains('Collection Name')
        .invoke('attr', 'for')
        .then((inputId) => {
            cy.get(`#${inputId}`)
                .should('be.visible')
                .clear()
                .type(newName);
        });

    // Click "Skip to Update" button to go to final step
    cy.contains('button', 'Skip to Update')
        .scrollIntoView()
        .should('be.visible')
        .click();

    // Click "Update Collection" button to save changes
    cy.contains('button', 'Update Collection')
        .should('be.visible')
        .and('not.be.disabled')
        .click();

    // Wait for success notification
    cy.contains(/successfully.*updated/i, { timeout: 10000 })
        .should('be.visible');
}

/**
 * Upload a document to a collection via the chat page
 * Note: Model, repository, and collection must already be selected in the chat UI
 */
export function uploadDocument (filePath: string) {
    cy.log(`Uploading document: ${filePath}`);

    // Click the "Upload to RAG" button
    cy.get('button[data-testid="upload-to-rag"]')
        .should('be.visible')
        .and('not.be.disabled')
        .click();

    // Wait for upload dialog to open
    cy.get('[role="dialog"]')
        .filter(':visible')
        .first()
        .should('be.visible')
        .within(() => {
            // Select the file using the file input within the data-testid wrapper
            // Path is relative to cypress directory
            cy.get('[data-testid="rag-upload-file-input"]')
                .find('input[type="file"]')
                .selectFile(`src/e2e/fixtures/${filePath}`, { force: true });

            // Wait a moment for file to be attached
            cy.wait(1000);

            // Click the Upload button to submit
            cy.contains('button', 'Upload')
                .should('be.visible')
                .and('not.be.disabled')
                .click();
        });

    // Wait for upload success notification
    cy.contains(/successfully.*uploaded/i, { timeout: 30000 })
        .should('be.visible');
}

/**
 * Wait for document to be ingested (up to 5 minutes)
 * Checks document status until it appears in the documents list
 * @param repositoryId - The repository ID
 * @param collectionId - The collection ID (not the name)
 * @param documentName - The document filename to wait for
 * @param timeoutMs - Maximum time to wait in milliseconds
 */
export function waitForDocumentIngested (repositoryId: string, collectionId: string, documentName: string, timeoutMs: number = 300000) {
    cy.log(`Waiting for document "${documentName}" to be ingested in collection ${collectionId}...`);

    const startTime = Date.now();
    const checkInterval = 10000; // Check every 10 seconds

    function checkDocumentStatus (): any {
        return makeAuthenticatedRequest('GET', `/repository/${repositoryId}/document?collectionId=${collectionId}&pageSize=100`).then((response) => {
            if (response.status === 200 && response.body.documents) {
                // Look for document by name (matches the uploaded filename with timestamp prefix)
                const document = response.body.documents.find((doc: any) =>
                    doc.document_name && doc.document_name.includes(documentName)
                );

                if (document) {
                    cy.log(`Document "${documentName}" found in collection (${document.document_name})`);
                    return; // Success - stop checking
                }
            }

            const elapsed = Date.now() - startTime;
            if (elapsed < timeoutMs) {
                return cy.wait(checkInterval).then(() => checkDocumentStatus());
            } else {
                throw new Error(`Document "${documentName}" was not found in collection within ${timeoutMs}ms`);
            }
        });
    }

    checkDocumentStatus();
}

/**
 * Select RAG repository in chat
 */
export function selectRagRepositoryInChat (repositoryId: string) {
    cy.log(`Selecting RAG repository: ${repositoryId}`);

    // Click the RAG repository input
    cy.get('input#rag-repository-autosuggest, input[placeholder*="RAG Repository" i]')
        .should('be.visible')
        .click({ force: true });

    // Wait for dropdown to appear and select the repository
    cy.get('[role="option"]')
        .contains(repositoryId)
        .should('be.visible')
        .click();
}

/**
 * Select collection in chat
 * If the collection doesn't exist, selects the first available option
 */
export function selectCollectionInChat (collectionName: string) {
    cy.log(`Selecting collection: ${collectionName}`);

    // Click the collection input
    cy.get('input#collection-autosuggest, input[placeholder*="collection" i]')
        .should('be.visible')
        .click({ force: true });

    // Wait for dropdown to appear
    cy.get('[role="option"]', { timeout: 10000 }).should('be.visible');

    // Try to find the collection by name
    cy.get('body').then(($body) => {
        const collectionOption = $body.find(`[role="option"]:contains("${collectionName}")`);

        if (collectionOption.length > 0) {
            // Collection found - click it
            cy.get('[role="option"]')
                .contains(collectionName)
                .click();
        } else {
            // Collection not found - select first option
            cy.log(`⚠️ Collection "${collectionName}" not found. Selecting first available collection.`);
            cy.get('[role="option"]')
                .first()
                .click();
        }
    });
}

/**
 * Send a message and verify RAG response with sources
 */
export function sendMessageAndVerifyRagResponse (message: string) {
    cy.log(`Sending message: ${message}`);

    // Set up intercept for chat completions API
    cy.intercept('POST', '**/chat/completions').as('chatCompletion');

    // Type the message
    cy.get('textarea[placeholder*="message" i]')
        .should('be.visible')
        .clear()
        .type(message);

    // Send the message
    cy.get('button[aria-label="Send message"]')
        .should('be.visible')
        .and('not.be.disabled')
        .click();

    // Wait for the chat completion to finish
    cy.wait('@chatCompletion', { timeout: 60000 });

    // Wait for response to complete (look for chat messages - user + assistant)
    cy.get('[data-testid="chat-message"]', { timeout: 60000 })
        .should('have.length.at.least', 2);

    // Verify source references are present in the response
    cy.contains(/source|reference|citation/i, { timeout: 10000 })
        .should('be.visible');
}

/**
 * Get the auto-created collection name and ID for a repository
 * Returns both the name and ID of the auto-created collection
 */
export function getAutoCreatedCollectionInfo (repositoryId: string): Cypress.Chainable<{name: string, id: string}> {
    return makeAuthenticatedRequest('GET', `/repository/${repositoryId}/collection`).then((response) => {
        if (response.body && response.body.collections && Array.isArray(response.body.collections)) {
            const collections = response.body.collections;

            if (collections.length === 0) {
                throw new Error(`No collections found for repository ${repositoryId}`);
            }

            // Find the auto-created collection (default or has dataSourceId for Bedrock KB)
            const autoCreatedCollection = collections.find(
                (collection: any) => collection.default === true || collection.dataSourceId !== null
            );

            if (autoCreatedCollection) {
                const collectionName = autoCreatedCollection.name;
                const collectionId = autoCreatedCollection.collectionId;
                Cypress.log({ name: 'getAutoCreatedCollectionInfo', message: `Found auto-created collection: ${collectionName} (ID: ${collectionId})` });
                return cy.wrap({ name: collectionName, id: collectionId });
            }

            // Fallback to first collection if no default found
            const firstCollection = collections[0];
            Cypress.log({ name: 'getAutoCreatedCollectionInfo', message: `Using first collection: ${firstCollection.name} (ID: ${firstCollection.collectionId})` });
            return cy.wrap({ name: firstCollection.name, id: firstCollection.collectionId });
        }
        throw new Error(`Failed to fetch collections for repository ${repositoryId}`);
    });
}

/**
 * Get the auto-created collection name for a repository
 * Returns the name of the auto-created collection (typically marked with default: true or has dataSourceId)
 * @deprecated Use getAutoCreatedCollectionInfo instead to get both name and ID
 */
export function getAutoCreatedCollectionName (repositoryId: string): Cypress.Chainable<string> {
    return getAutoCreatedCollectionInfo(repositoryId).then((info) => info.name);
}

/**
 * Delete a collection by name (for cleanup)
 */
export function deleteCollectionIfExists (collectionName: string) {
    cy.get('body').then(($body) => {
        if ($body.text().includes(collectionName)) {
            // Select the collection
            cy.contains(collectionName)
                .closest('tr, [data-testid*="collection"]')
                .find('input[type="radio"], input[type="checkbox"]')
                .first()
                .click({ force: true });

            // Click the Actions dropdown or Delete button
            cy.get('[data-testid="collection-actions-dropdown"], button')
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

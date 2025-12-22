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
 * adminHelpers.ts
 * Contains reusable checks for the Administration button & menu.
 */

export function checkAdminButtonExists () {
    cy.get('button[aria-label="Administration"]')
        .should('exist')
        .and('be.visible')
        .and('have.attr', 'aria-expanded', 'false');
}

export function expandAdminMenu () {
    // click → verify expanded → verify menu items
    cy.get('button[aria-label="Administration"]')
        .filter(':visible')
        .click()
        .should('have.attr', 'aria-expanded', 'true');

    cy.get('[role="menu"]')
        .should('be.visible');

    cy.get('[role="menuitem"]')
        .should('have.length', 5)
        .then(($items) => {
            const labels = $items
                .map((_, el) => Cypress.$(el).text().trim())
                .get();
            expect(labels).to.deep.equal([
                'Configuration',
                'Model Management',
                'RAG Management',
                'API Token Management',
                'MCP Management'
            ]);
        });
}

export function checkNoAdminButton () {
    cy.get('button[aria-label="Administration"]')
        .should('not.exist');
}

/**
 * Navigate to a specific admin page by menu item name
 * @param menuItemName - The exact text of the menu item to click
 */
export function navigateToAdminPage(menuItemName: string) {
    checkAdminButtonExists();
    expandAdminMenu();
    
    cy.get('[role="menuitem"]')
        .contains(menuItemName)
        .click();
}

/**
 * Verify that an admin page has loaded correctly
 * @param urlFragment - The expected URL fragment (e.g., '/admin/configuration')
 * @param pageTitle - Optional expected page title text
 */
export function verifyAdminPageLoaded(urlFragment: string, pageTitle?: string) {
    cy.url().should('include', urlFragment);
    
    if (pageTitle) {
        cy.get('h1, h2, [data-testid="page-title"]')
            .should('be.visible')
            .and('contain.text', pageTitle);
    } else {
        // Just verify some main content is visible
        cy.get('h1, h2, [data-testid="page-title"], main, [role="main"]')
            .should('be.visible');
    }
}

/**
 * Verify that a table contains at least one data row (excluding headers)
 * @param tableSelector - Optional CSS selector for the table (defaults to finding any table)
 * @param minRows - Minimum number of data rows expected (defaults to 1)
 */
export function verifyTableHasData(tableSelector?: string, minRows: number = 1) {
    const selector = tableSelector || 'table, [role="table"]';
    
    cy.get(selector)
        .should('be.visible')
        .within(() => {
            // Check for table rows that contain data (not just headers)
            cy.get('tbody tr, [role="row"]:not([role="columnheader"])')
                .should('have.length.at.least', minRows);
        });
}

/**
 * Verify that a Cloudscape table component has rendered with data
 * Uses Cloudscape-specific selectors for better reliability
 */
export function verifyCloudscapeTableHasData(minRows: number = 1) {
    // Cloudscape tables use specific CSS classes and structure
    cy.get('[data-testid="table"], .awsui-table, table')
        .should('be.visible')
        .within(() => {
            // Look for table body rows or Cloudscape row elements
            cy.get('tbody tr, .awsui-table-row, [data-testid="table-row"]')
                .should('have.length.at.least', minRows);
        });
}

/**
 * Verify that cards (used in model management) have rendered with data
 * @param minCards - Minimum number of cards expected (defaults to 1)
 */
export function verifyCardsHaveData(minCards: number = 1) {
    cy.get('[data-testid="cards"], .awsui-cards, .awsui-cards-card')
        .should('be.visible')
        .and('have.length.at.least', minCards);
}

/**
 * Wait for loading to complete and verify content is rendered
 * @param loadingSelector - Selector for loading indicator (optional)
 */
export function waitForContentToLoad(loadingSelector?: string) {
    if (loadingSelector) {
        cy.get(loadingSelector).should('not.exist');
    }
    
    // Wait for common loading indicators to disappear
    cy.get('[data-testid="loading"], .awsui-spinner, .loading')
        .should('not.exist');
}

/**
 * Combined helper to navigate to admin page and verify it has rendered with data
 * @param menuItemName - The menu item to click
 * @param urlFragment - Expected URL fragment
 * @param pageTitle - Expected page title
 * @param contentType - Type of content to verify ('table', 'cards', or 'custom')
 * @param minItems - Minimum number of items expected
 */
export function navigateAndVerifyAdminPage(
    menuItemName: string,
    urlFragment: string,
    pageTitle?: string,
    contentType: 'table' | 'cards' | 'custom' = 'table',
    minItems: number = 1
) {
    navigateToAdminPage(menuItemName);
    verifyAdminPageLoaded(urlFragment, pageTitle);
    waitForContentToLoad();
    
    switch (contentType) {
        case 'table':
            verifyCloudscapeTableHasData(minItems);
            break;
        case 'cards':
            verifyCardsHaveData(minItems);
            break;
        case 'custom':
            // For custom verification, just ensure page loaded
            break;
    }
}

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

    // Get the button-dropdown container once and reuse it
    cy.get('button[aria-label="Administration"]')
        .closest('[class*="awsui_button-dropdown_"]')
        .as('adminDropdown');

    // Verify menu is visible
    cy.get('@adminDropdown')
        .find('[role="menu"]')
        .should('be.visible');

    // Verify menu items
    cy.get('@adminDropdown')
        .find('[role="menuitem"]')
        .should('have.length', 6)
        .then(($items) => {
            const labels = $items
                .map((_, el) => Cypress.$(el).text().trim())
                .get();
            expect(labels).to.deep.equal([
                'Configuration',
                'Model Management',
                'RAG Management',
                'API Token Management',
                'MCP Management',
                'MCP Workbench'
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
export function navigateToAdminPage (menuItemName: string) {
    checkAdminButtonExists();
    expandAdminMenu();

    // Use the aliased dropdown container to find and click the menu item
    cy.get('@adminDropdown')
        .find('[role="menuitem"]')
        .contains(menuItemName)
        .click();
}

/**
 * Verify that an admin page has loaded correctly
 * @param urlFragment - The expected URL fragment (e.g., '/admin/configuration')
 * @param pageTitle - Optional expected page title text
 */
export function verifyAdminPageLoaded (urlFragment: string, pageTitle?: string) {
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
export function verifyTableHasData (tableSelector?: string, minRows: number = 1) {
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
export function verifyCloudscapeTableHasData (minRows: number = 1) {
    // Cloudscape tables use specific CSS classes and structure
    // Look for table body rows with dynamic class names
    cy.get('tbody tr, [class*="awsui_row_"]')
        .should('have.length.at.least', minRows);
}

/**
 * Verify that cards (used in model management) have rendered with data
 * @param minCards - Minimum number of cards expected (defaults to 1)
 */
export function verifyCardsHaveData (minCards: number = 1) {
    // Cloudscape cards use dynamic class names with hashes
    // Look for list items within the cards container that have the card class pattern
    cy.get('[class*="awsui_card_"][class*="awsui_card-selectable_"]')
        .should('have.length.at.least', minCards);
}

/**
 * Verify that a list component has rendered with data
 * Used for MCP Workbench and similar list-based views
 * @param minItems - Minimum number of list items expected (defaults to 1)
 */
export function verifyListHasData (minItems: number = 1) {
    // Look for list items with data-testid attributes (used in MCP Workbench)
    cy.get('ul[class*="awsui_root_"] li[data-testid]')
        .should('have.length.at.least', minItems);
}

/**
 * Wait for loading to complete and verify content is rendered
 * @param loadingSelector - Selector for loading indicator (optional)
 */
export function waitForContentToLoad (loadingSelector?: string) {
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
 * @param contentType - Type of content to verify ('table', 'cards', 'list', or 'custom')
 * @param minItems - Minimum number of items expected
 */
export function navigateAndVerifyAdminPage (
    menuItemName: string,
    urlFragment: string,
    pageTitle?: string,
    contentType: 'table' | 'cards' | 'list' | 'custom' = 'table',
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
        case 'list':
            verifyListHasData(minItems);
            break;
        case 'custom':
            // For custom verification, just ensure page loaded
            break;
    }
}

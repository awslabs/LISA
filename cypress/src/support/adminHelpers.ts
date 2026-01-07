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

import {
    verifyCardsHaveData,
    verifyCloudscapeTableHasData,
    verifyListHasData,
    waitForContentToLoad,
} from './dataHelpers';

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
        .first()
        .click()
        .should('have.attr', 'aria-expanded', 'true');

    // Wait for dropdown animation to complete
    cy.wait(500);

    // Get the button-dropdown container once and reuse it
    cy.get('button[aria-label="Administration"]')
        .filter(':visible')
        .first()
        .closest('[class*="awsui_button-dropdown_"]')
        .as('adminDropdown');

    // Verify menu is visible - use filter to get only visible menu
    cy.get('@adminDropdown')
        .find('[role="menu"]')
        .filter(':visible')
        .should('exist')
        .and('be.visible');

    // Verify menu items
    cy.get('@adminDropdown')
        .find('[role="menuitem"]')
        .filter(':visible')
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

    // Click to expand menu
    cy.get('button[aria-label="Administration"]')
        .filter(':visible')
        .first()
        .click()
        .should('have.attr', 'aria-expanded', 'true');

    // Wait for dropdown animation
    cy.wait(500);

    // Find and click the menu item
    cy.get('[role="menuitem"]')
        .filter(':visible')
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

// Re-export data helpers for backward compatibility
export {
    verifyTableHasData,
    verifyCloudscapeTableHasData,
    verifyCardsHaveData,
    verifyListHasData,
    waitForContentToLoad,
} from './dataHelpers';

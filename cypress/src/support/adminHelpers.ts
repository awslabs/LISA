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

// Cloudscape TopNavigation selectors
// Use aria-label to target the specific Administration menu, not just any [role="menu"]
const ADMIN_MENU_SELECTOR = '[role="menu"][aria-label="Administration"]';
const MENU_ITEM_SELECTOR = '[role="menuitem"]';

// Core menu items that are always present for admin users
const EXPECTED_MENU_ITEMS = [
    'Configuration',
    'Model Management',
    'RAG Management',
    'API Token Management',
    'MCP Management',
    'MCP Workbench',
];

/**
 * Get the visible admin button with built-in retry.
 * Cloudscape TopNavigation buttons have aria-label for accessibility.
 */
export function getAdminButton (): Cypress.Chainable {
    // Use aria-label which is reliable in Cloudscape TopNavigation
    return cy.get('header button[aria-label="Administration"]');
}

export function getLibraryButton (): Cypress.Chainable {
    // Use aria-label which is reliable in Cloudscape TopNavigation
    return cy.get('header button[aria-label="Libraries"]');
}
/**
 * Expand the admin menu and verify all items are present
 */
export function expandAdminMenu () {
    // Wait for both Administration and Libraries buttons to be visible
    // This prevents clicking Administration before the header is fully rendered
    getLibraryButton().should('be.visible');
    getAdminButton().should('be.visible');

    getAdminButton()
        .click()
        .should('have.attr', 'aria-expanded', 'true');

    // Wait for the Administration menu specifically (not Libraries or other menus)
    cy.get(ADMIN_MENU_SELECTOR)
        .should('be.visible')
        .find(MENU_ITEM_SELECTOR)
        .filter(':visible')
        .should('have.length.at.least', EXPECTED_MENU_ITEMS.length)
        .then(($items) => {
            const labels = $items.map((_, el) => Cypress.$(el).text().trim()).get();
            // Verify core items are present
            EXPECTED_MENU_ITEMS.forEach((item) => {
                expect(labels).to.include(item);
            });
        });
}

/**
 * Collapse the admin menu
 */
export function collapseAdminMenu () {
    getAdminButton()
        .click()
        .should('have.attr', 'aria-expanded', 'false');

    cy.get(ADMIN_MENU_SELECTOR).should('not.be.visible');
}

export function checkNoAdminButton () {
    // Use the specific selector for the Administration button
    cy.get('header button[aria-label="Administration"]').should('not.exist');
}

/**
 * Navigate to a specific admin page by menu item name
 * @param menuItemName - The exact text of the menu item to click
 */
export function navigateToAdminPage (menuItemName: string) {
    // First expand the menu using the same pattern as expandAdminMenu
    expandAdminMenu();

    // Then click the specific menu item
    cy.contains(MENU_ITEM_SELECTOR, menuItemName)
        .filter(':visible')
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

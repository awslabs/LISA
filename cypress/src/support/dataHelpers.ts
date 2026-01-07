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
 * dataHelpers.ts
 * Contains reusable helpers for verifying data rendering in tables, cards, and lists.
 */

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

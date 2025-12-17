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

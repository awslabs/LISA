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

/// <reference types="cypress" />

/**
 * Shared test suite for RAG Admin role features.
 * RAG Admins see the Administration dropdown with only RAG Management.
 * They cannot access admin-only pages but can access chat.
 *
 * Can be used by both smoke tests (with fixtures) and e2e tests (with real data).
 */

import { expandRagAdminMenu } from '../../support/adminHelpers';
import { waitForContentToLoad, verifyCloudscapeTableHasData } from '../../support/dataHelpers';
import { navigateAndVerifyChatPage } from '../../support/chatHelpers';

const ADMIN_MENU_SELECTOR = '[role="menu"][aria-label="Administration"]';
const MENU_ITEM_SELECTOR = '[role="menuitem"]';

export function runRagAdminTests (options: {
    expectMinItems?: boolean;
    verifyFixtureData?: boolean;
} = {}) {
    const { expectMinItems = false, verifyFixtureData = false } = options;

    it('RAG Admin sees Administration button with only RAG Management', () => {
        expandRagAdminMenu();
    });

    it('RAG Admin can navigate to RAG Management page', () => {
        const minItems = expectMinItems ? 3 : 0;

        // Use expandRagAdminMenu to wait for stable header and open the correct menu
        expandRagAdminMenu();

        // Click RAG Management from the open menu
        cy.get(ADMIN_MENU_SELECTOR, { timeout: 10000 })
            .filter(':visible')
            .contains(MENU_ITEM_SELECTOR, 'RAG Management')
            .click();

        cy.url().should('include', '/repository-management');
        cy.wait('@getRepositories', { timeout: 10000 });
        waitForContentToLoad();

        if (minItems > 0) {
            verifyCloudscapeTableHasData(minItems);
        }

        if (verifyFixtureData) {
            cy.contains('Technical Documentation').should('be.visible');
            cy.contains('Product Knowledge Base').should('be.visible');
            cy.contains('Training Materials').should('be.visible');
        }
    });

    it('RAG Admin cannot access admin-only pages', () => {
        const adminOnlyPaths = [
            '#/configuration',
            '#/model-management',
            '#/api-token-management',
            '#/mcp-management',
            '#/mcp-workbench',
            '#/bedrock-agent-management',
        ];

        adminOnlyPaths.forEach((path) => {
            cy.visit(path, { failOnStatusCode: false, timeout: 10000 });
            const stripped = path.replace('#/', '');

            cy.url({ timeout: 10000 }).should('satisfy', (url: string) => {
                return !url.includes(stripped) ||
                       url.includes('access-denied') ||
                       url.includes('unauthorized');
            }, `Expected rag-admin to be redirected from ${path}`);
        });
    });

    it('RAG Admin can access chat', () => {
        navigateAndVerifyChatPage();
    });
}

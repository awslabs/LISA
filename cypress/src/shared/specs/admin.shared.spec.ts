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
 * Shared test suite for Admin Navigation features.
 * Can be used by both smoke tests (with fixtures) and e2e tests (with real data).
 */

import {
    navigateAndVerifyAdminPage,
    checkAdminButtonExists,
    expandAdminMenu,
} from '../../support/adminHelpers';

export function runAdminTests (options: {
    expectMinItems?: boolean;
    verifyFixtureData?: boolean;
} = {}) {
    const { expectMinItems = false, verifyFixtureData = false } = options;

    it('Admin sees the Administration button', () => {
        // Wait for the page to fully load and initial API calls to complete
        // This is especially important for the first test after login
        cy.wait(2000);
        checkAdminButtonExists();
    });

    it('Admin can expand menu and see all menu items', () => {
        expandAdminMenu();
    });

    it('Admin menu collapses when clicked again', () => {
        // Expand menu first
        cy.get('button[aria-label="Administration"]')
            .filter(':visible')
            .click()
            .should('have.attr', 'aria-expanded', 'true');

        cy.get('[role="menu"]')
            .should('be.visible');

        // Collapse menu
        cy.get('button[aria-label="Administration"]')
            .filter(':visible')
            .click()
            .should('have.attr', 'aria-expanded', 'false');

        cy.get('[role="menu"]')
            .should('not.be.visible');
    });

    it('Admin can access Configuration page', () => {
        navigateAndVerifyAdminPage(
            'Configuration',
            '/configuration',
            'Configuration',
            'custom'
        );
    });

    it('Model Management page loads and shows model cards', () => {
        const minItems = expectMinItems ? 2 : 1;
        navigateAndVerifyAdminPage('Model Management', '/model-management', 'Model', 'cards', minItems);

        if (verifyFixtureData) {
            // Verify specific model data from fixtures
            cy.contains('mistral-vllm').should('be.visible');
            cy.contains('claude-3-7').should('be.visible');
            cy.contains('InService').should('be.visible');
        }
    });

    it('API Token Management page loads and shows tokens table', () => {
        const minItems = expectMinItems ? 3 : 0;
        navigateAndVerifyAdminPage('API Token Management', '/api-token-management', 'API Token', 'table', minItems);

        if (verifyFixtureData) {
            // Verify specific token data from fixtures
            cy.contains('Development Token').should('be.visible');
            cy.contains('Production API Key').should('be.visible');
            cy.contains('Test Environment Token').should('be.visible');
        }
    });

    it('RAG Management page loads and shows repositories table', () => {
        const minItems = expectMinItems ? 3 : 0;
        navigateAndVerifyAdminPage('RAG Management', '/repository-management', 'RAG', 'table', minItems);

        if (verifyFixtureData) {
            // Verify specific repository data from fixtures
            cy.contains('Technical Documentation').should('be.visible');
            cy.contains('Product Knowledge Base').should('be.visible');
            cy.contains('Training Materials').should('be.visible');
        }
    });

    it('MCP Management page loads and shows servers table', () => {
        const minItems = expectMinItems ? 3 : 0;
        navigateAndVerifyAdminPage('MCP Management', '/mcp-management', 'MCP', 'table', minItems);

        if (verifyFixtureData) {
            // Verify specific MCP server data from fixtures
            cy.contains('Weather Service').should('be.visible');
            cy.contains('Database Connector').should('be.visible');
            cy.contains('File Processing Service').should('be.visible');
        }
    });

    it('MCP Workbench page loads', () => {
        const minItems = expectMinItems ? 3 : 0;
        const contentType = expectMinItems ? 'list' : 'custom';
        cy.wait('@stubConfiguration');
        navigateAndVerifyAdminPage(
            'MCP Workbench',
            '/mcp-workbench',
            'MCP Workbench',
            contentType,
            minItems
        );

        if (verifyFixtureData) {
            // Verify specific tool files from fixtures
            cy.get('li[data-testid="bad_actors_db.py"]').should('be.visible');
            cy.get('li[data-testid="calculator.py"]').should('be.visible');
            cy.get('li[data-testid="weather.py"]').should('be.visible');
        }
    });
}

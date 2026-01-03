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
 * E2E suite for Admin Navigation features:
 * - Ensures admin users can navigate to all administration pages
 * - Verifies each admin page loads correctly with mock data
 * - Tests that tables and components render properly with fixture data
 */

import {
    navigateAndVerifyAdminPage,
    checkAdminButtonExists,
    expandAdminMenu,
} from '../../support/adminHelpers';

describe('Admin Navigation (Smoke)', () => {
    beforeEach(() => {
        cy.loginAs('admin');
    });
    it('Admin sees the Administration button', () => {
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

    it('Admin can access Configuration page and see configuration data', () => {
        navigateAndVerifyAdminPage(
            'Configuration',
            '/configuration',
            'Configuration',
            'custom' // Configuration page may not have a standard table
        );
    });

    it('Model Management page shows model cards with correct data', () => {
        navigateAndVerifyAdminPage('Model Management', '/model-management', 'Model', 'cards', 2);

        // Verify specific model data from fixtures
        cy.contains('mistral-vllm').should('be.visible');
        cy.contains('claude-3-7').should('be.visible');
        cy.contains('InService').should('be.visible');
    });

    it('API Token Management page shows tokens with correct data', () => {
        navigateAndVerifyAdminPage('API Token Management', '/api-token-management', 'API Token', 'table', 3);

        // Verify specific token data from fixtures
        cy.contains('Development Token').should('be.visible');
        cy.contains('Production API Key').should('be.visible');
        cy.contains('Test Environment Token').should('be.visible');
    });

    it('RAG Management page shows repositories with correct data', () => {
        navigateAndVerifyAdminPage('RAG Management', '/repository-management', 'RAG', 'table', 3);

        // Verify specific repository data from fixtures
        cy.contains('Technical Documentation').should('be.visible');
        cy.contains('Product Knowledge Base').should('be.visible');
        cy.contains('Training Materials').should('be.visible');
    });

    it('MCP Management page shows servers with correct data', () => {
        navigateAndVerifyAdminPage('MCP Management', '/mcp-management', 'MCP', 'table', 3);

        // Verify specific MCP server data from fixtures
        cy.contains('Weather Service').should('be.visible');
        cy.contains('Database Connector').should('be.visible');
        cy.contains('File Processing Service').should('be.visible');
    });

    it('MCP Workbench page shows tool files with correct data', () => {
        navigateAndVerifyAdminPage(
            'MCP Workbench',
            '/mcp-workbench',
            'MCP Workbench',
            'list',
            3 // Expecting at least 3 tool files from fixture
        );

        // Verify specific tool files from fixtures
        cy.get('li[data-testid="bad_actors_db.py"]').should('be.visible');
        cy.get('li[data-testid="calculator.py"]').should('be.visible');
        cy.get('li[data-testid="weather.py"]').should('be.visible');
    });
});
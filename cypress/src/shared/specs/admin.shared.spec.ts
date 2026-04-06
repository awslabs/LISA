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
    navigateToAdminPage,
    expandAdminMenu,
    collapseAdminMenu,
    navigateViaLibraries,
} from '../../support/adminHelpers';
import { waitForContentToLoad, verifyCloudscapeTableHasData } from '../../support/dataHelpers';

export function runAdminTests (options: {
    expectMinItems?: boolean;
    verifyFixtureData?: boolean;
} = {}) {
    const { expectMinItems = false, verifyFixtureData = false } = options;

    it('Admin sees the Administration button and can expand/collapse menu', () => {
        // Expand and verify menu items
        expandAdminMenu();
        // Collapse and verify
        collapseAdminMenu();
    });

    it('Admin can access Configuration page', () => {
        navigateToAdminPage('Configuration');
        cy.url().should('include', '/configuration');

        // Check for the submit button which is always visible
        cy.get('[data-testid="configuration-submit"]').should('be.visible');
    });

    it('Model Management page loads and shows model cards', () => {
        const minItems = expectMinItems ? 2 : 1;
        navigateAndVerifyAdminPage('Model Management', '/model-management', 'Model', 'cards', minItems);

        if (verifyFixtureData) {
            cy.contains('mistral-vllm').should('be.visible');
            cy.contains('claude-3-7').should('be.visible');
            cy.contains('InService').should('be.visible');
        }
    });

    it('API Token Management page loads and shows tokens table', () => {
        const minItems = expectMinItems ? 3 : 0;
        navigateAndVerifyAdminPage('API Token Management', '/api-token-management', 'API Token', 'table', minItems);

        // Wait for API tokens to load
        cy.wait('@getApiTokens', { timeout: 30000 });

        if (verifyFixtureData) {
            cy.contains('Development Token').should('be.visible');
            cy.contains('Production API Key').should('be.visible');
            cy.contains('Test Environment Token').should('be.visible');
        }
    });

    it('RAG Management page loads and shows repositories table', () => {
        const minItems = expectMinItems ? 3 : 0;
        navigateAndVerifyAdminPage('RAG Management', '/repository-management', 'RAG', 'table', minItems);
        cy.wait('@getRepositories', { timeout: 30000 });

        if (verifyFixtureData) {
            cy.contains('Technical Documentation').should('be.visible');
            cy.contains('Product Knowledge Base').should('be.visible');
            cy.contains('Training Materials').should('be.visible');
        }
    });

    it('MCP Management page loads and shows servers table', () => {
        const minItems = expectMinItems ? 3 : 0;
        navigateAndVerifyAdminPage('MCP Management', '/mcp-management', 'MCP', 'table', minItems);
        cy.wait('@getMcp', { timeout: 30000 });

        if (verifyFixtureData) {
            cy.contains('Weather Service').should('be.visible');
            cy.contains('Database Connector').should('be.visible');
            cy.contains('File Processing Service').should('be.visible');
        }
    });

    it('MCP Workbench page loads', () => {
        const minItems = expectMinItems ? 3 : 0;
        const contentType = expectMinItems ? 'list' : 'custom';
        navigateAndVerifyAdminPage(
            'MCP Workbench',
            '/mcp-workbench',
            'MCP Workbench',
            contentType,
            minItems
        );
        cy.wait('@getMcpWorkbench', { timeout: 30000 });

        if (verifyFixtureData) {
            cy.get('li[data-testid="bad_actors_db.py"]').should('be.visible');
            cy.get('li[data-testid="calculator.py"]').should('be.visible');
            cy.get('li[data-testid="weather.py"]').should('be.visible');
        }
    });

    it('Bedrock Agent Catalog page loads; scan populates discovered agents', () => {
        const minRows = expectMinItems ? 1 : 0;
        navigateToAdminPage('Bedrock Agent Catalog');
        cy.url().should('include', '/bedrock-agent-management');
        waitForContentToLoad();
        cy.wait('@getBedrockApprovals', { timeout: 30000 });
        cy.contains('h2', 'Available agents').should('be.visible');
        cy.contains('h2', 'LISA catalog').should('be.visible');
        if (verifyFixtureData) {
            cy.contains('Smoke Test Agent').should('be.visible');
        }
        verifyCloudscapeTableHasData(minRows);

        cy.contains('button', 'Scan account').click();
        cy.wait('@getBedrockDiscovery', { timeout: 30000 });
        if (verifyFixtureData) {
            cy.contains('Discovered Only Agent').should('be.visible');
        }
    });

    it('Agentic Connections shows MCP and Bedrock tabs; agent details page loads', () => {
        navigateViaLibraries('Agentic Connections');
        cy.url().should('include', '/mcp-connections');
        waitForContentToLoad();

        // Chat prefetches MCP servers and user preferences after login, so those APIs may not fire again here.
        cy.contains('[role="tab"]', 'MCP servers').should('be.visible');
        cy.contains('MCP connections').should('be.visible');

        cy.contains('[role="tab"]', 'Bedrock agents').should('be.visible').click();
        cy.wait('@getBedrockAgents', { timeout: 30000 });

        cy.contains('Amazon Bedrock agents').should('be.visible');
        if (verifyFixtureData) {
            cy.contains('Smoke Test Agent').should('be.visible').click();
            cy.url().should('match', /bedrock\//);
            cy.contains('h1', 'Smoke Test Agent').should('be.visible');
            cy.contains('Agent tools').should('be.visible');
            cy.contains('bedrock_smoke_tool').should('be.visible');
        }
    });
}

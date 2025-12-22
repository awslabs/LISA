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
    verifyCloudscapeTableHasData,
    verifyCardsHaveData,
} from '../../support/adminHelpers';

describe('Admin Navigation (Smoke)', () => {
    beforeEach(() => {
        cy.loginAs('admin');
    });

    it('Admin can access Configuration page and see configuration data', () => {
        navigateAndVerifyAdminPage(
            'Configuration',
            '/admin/configuration',
            'Configuration',
            'custom' // Configuration page may not have a standard table
        );
        
        // Verify configuration content is visible
        cy.get('form, .awsui-form-field, [data-testid="configuration"]')
            .should('be.visible');
    });

    it('Admin can access Model Management page and see model cards', () => {
        navigateAndVerifyAdminPage(
            'Model Management',
            '/admin/model',
            'Model',
            'cards',
            2 // Expecting at least 2 models from fixture
        );
    });

    it('Admin can access RAG Management page and see repository table', () => {
        navigateAndVerifyAdminPage(
            'RAG Management',
            '/admin/rag',
            'RAG',
            'table',
            3 // Expecting at least 3 repositories from fixture
        );
    });

    it('Admin can access API Token Management page and see tokens table', () => {
        navigateAndVerifyAdminPage(
            'API Token Management',
            '/admin/api-token',
            'API Token',
            'table',
            3 // Expecting at least 3 tokens from fixture
        );
    });

    it('Admin can access MCP Management page and see MCP servers table', () => {
        navigateAndVerifyAdminPage(
            'MCP Management',
            '/admin/mcp',
            'MCP',
            'table',
            3 // Expecting at least 3 MCP servers from fixture
        );
    });

    it('All admin pages render with proper data from fixtures', () => {
        const adminPages = [
            { 
                name: 'Model Management', 
                urlFragment: '/admin/model', 
                title: 'Model',
                contentType: 'cards' as const,
                minItems: 2
            },
            { 
                name: 'RAG Management', 
                urlFragment: '/admin/rag', 
                title: 'RAG',
                contentType: 'table' as const,
                minItems: 3
            },
            { 
                name: 'API Token Management', 
                urlFragment: '/admin/api-token', 
                title: 'API Token',
                contentType: 'table' as const,
                minItems: 3
            },
            { 
                name: 'MCP Management', 
                urlFragment: '/admin/mcp', 
                title: 'MCP',
                contentType: 'table' as const,
                minItems: 3
            }
        ];

        // Navigate to each page and verify data rendering
        adminPages.forEach((page) => {
            navigateAndVerifyAdminPage(
                page.name,
                page.urlFragment,
                page.title,
                page.contentType,
                page.minItems
            );
        });
    });

    it('Model Management page shows model cards with correct data', () => {
        navigateAndVerifyAdminPage('Model Management', '/admin/model', 'Model', 'cards', 2);
        
        // Verify specific model data from fixtures
        cy.contains('mistral-vllm').should('be.visible');
        cy.contains('claude-3-7').should('be.visible');
        cy.contains('InService').should('be.visible');
    });

    it('API Token Management page shows tokens with correct data', () => {
        navigateAndVerifyAdminPage('API Token Management', '/admin/api-token', 'API Token', 'table', 3);
        
        // Verify specific token data from fixtures
        cy.contains('Development Token').should('be.visible');
        cy.contains('Production API Key').should('be.visible');
        cy.contains('Test Environment Token').should('be.visible');
    });

    it('RAG Management page shows repositories with correct data', () => {
        navigateAndVerifyAdminPage('RAG Management', '/admin/rag', 'RAG', 'table', 3);
        
        // Verify specific repository data from fixtures
        cy.contains('Technical Documentation').should('be.visible');
        cy.contains('Product Knowledge Base').should('be.visible');
        cy.contains('Training Materials').should('be.visible');
    });

    it('MCP Management page shows servers with correct data', () => {
        navigateAndVerifyAdminPage('MCP Management', '/admin/mcp', 'MCP', 'table', 3);
        
        // Verify specific MCP server data from fixtures
        cy.contains('Weather Service').should('be.visible');
        cy.contains('Database Connector').should('be.visible');
        cy.contains('File Processing Service').should('be.visible');
    });
});
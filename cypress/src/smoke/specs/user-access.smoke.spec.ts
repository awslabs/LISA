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
 * E2E suite for User Access Control:
 * - Ensures non-admin users cannot access administration features
 * - Verifies proper access control enforcement
 * - Tests user role restrictions
 */

import { checkNoAdminButton } from '../../support/adminHelpers';

describe('User Access Control (Smoke)', () => {
    beforeEach(() => {
        cy.loginAs('user');
    });

    it('Non-admin user does not see Administration button', () => {
        checkNoAdminButton();
    });

    it('Non-admin user cannot directly access admin pages', () => {
        const adminPaths = [
            '/admin/configuration',
            '/admin/model',
            '/admin/rag',
            '/admin/api-token',
            '/admin/mcp'
        ];

        adminPaths.forEach((path) => {
            cy.visit(path, { failOnStatusCode: false });
            
            // Should be redirected or see access denied
            cy.url().should('not.include', path);
            // Alternative: check for access denied message
            // cy.contains('Access Denied', 'Unauthorized', 'Forbidden').should('be.visible');
        });
    });
});
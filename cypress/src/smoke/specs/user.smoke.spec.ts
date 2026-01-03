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
 * E2E suite for Administration features (User role):
 * - Confirms non-admin users do not see the Administration option
 */

import { checkNoAdminButton } from '../../support/adminHelpers';

describe('User features (Smoke)', () => {
    beforeEach(() => {
        cy.loginAs('user');
    });

    it('Non-admin does not see the button', () => {
        checkNoAdminButton();
    });

    it('Non-admin user cannot directly access admin pages', () => {
        const adminPaths = [
            '#/configuration',
            '#/model-management',
            '#/repository-management',
            '#/api-token-management',
            '#/mcp-management'
        ];

        adminPaths.forEach((path) => {
            cy.visit(path, { failOnStatusCode: false });

            // Should be redirected away from admin path
            // Check that we're either on home page or an error/access denied page
            cy.url().should('satisfy', (url) => {
                // URL should not contain the admin path, or should show access denied
                return !url.includes(path) || url.includes('access-denied') || url.includes('unauthorized');
            });
        });
    });
});

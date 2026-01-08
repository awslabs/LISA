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
 * Shared test suite for User role features.
 * Can be used by both smoke tests (with fixtures) and e2e tests (with real data).
 *
 * Interceptors should be set up in beforeEach by the calling spec.
 */

import { checkNoAdminButton } from '../../support/adminHelpers';

export function runUserTests () {
    it('Non-admin does not see the Administration button', () => {
        // Wait for configuration to load before checking UI
        cy.wait('@getConfiguration', { timeout: 30000 });

        checkNoAdminButton();
    });

    it('Non-admin user cannot directly access admin pages', () => {
        const adminPaths = [
            '#/configuration',
            '#/model-management',
            '#/repository-management',
            '#/api-token-management',
            '#/mcp-management',
            '#/mcp-workbench'
        ];

        adminPaths.forEach((path) => {
            cy.visit(path, { failOnStatusCode: false, timeout: 10000 });

            cy.url({ timeout: 10000 }).should('satisfy', (url: string) => {
                // Should be redirected away from admin path, or show access denied
                // Accept homepage redirect as valid (which is what AdminRoute does)
                return !url.includes(path.replace('#/', '')) ||
                       url.includes('access-denied') ||
                       url.includes('unauthorized');
            });
        });
    });
}

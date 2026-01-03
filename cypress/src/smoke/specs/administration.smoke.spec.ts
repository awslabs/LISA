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
 * E2E suite for Administration Menu:
 * - Ensures admin users can view and interact with the Administration menu
 * - Verifies correct menu items and expansion behavior
 * - Tests basic admin menu functionality
 */

import {
    checkAdminButtonExists,
    expandAdminMenu,
} from '../../support/adminHelpers';

describe('Administration features - Admin (Smoke)', () => {
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
});

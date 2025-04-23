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
 * E2E suite for Administration features:
 * - Ensures admin users can view and interact with the Administration menu
 * - Verifies correct menu items and expansion behavior
 * - Confirms non-admin users do not see the Administration option
 */

import {
    checkAdminButtonExists,
    expandAdminMenu,
    checkNoAdminButton,
} from '../../support/adminHelpers';

describe('Administration features (Smoke)', () => {
    it('Admin sees the button', () => {
        cy.loginAs('admin');
        checkAdminButtonExists();
    });

    it('Admin can expand menu', () => {
        cy.loginAs('admin');
        expandAdminMenu();
    });

    it('Non-admin does not see the button', () => {
        cy.loginAs('user');
        checkNoAdminButton();
    });
});

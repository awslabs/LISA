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

describe('Administration features (E2E)', () => {
    beforeEach(() => {
        cy.clearAllSessionStorage();
    });

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

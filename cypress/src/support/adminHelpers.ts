/**
 * adminHelpers.ts
 * Contains reusable checks for the Administration button & menu.
 */

export function checkAdminButtonExists () {
    cy.get('button[aria-label="Administration"]')
        .should('exist')
        .and('be.visible')
        .and('have.attr', 'aria-expanded', 'false');
}

export function expandAdminMenu () {
    // click → verify expanded → verify menu items
    cy.get('button[aria-label="Administration"]')
        .filter(':visible')
        .click()
        .should('have.attr', 'aria-expanded', 'true');

    cy.get('[role="menu"]')
        .should('be.visible');

    cy.get('[role="menuitem"]')
        .should('have.length', 2)
        .then(($items) => {
            const labels = $items
                .map((_, el) => Cypress.$(el).text().trim())
                .get();
            expect(labels).to.deep.equal([
                'Configuration',
                'Model Management',
            ]);
        });
}

export function checkNoAdminButton () {
    cy.get('button[aria-label="Administration"]')
        .should('not.exist');
}

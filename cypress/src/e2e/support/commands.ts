/// <reference types="cypress" />

// Base application URL from Cypress config
import { getTopLevelDomain } from './utils';

const BASE_URL = Cypress.config('baseUrl') as string;

/**
 * Custom command to log in a user via stubbed OAuth2/OIDC.
 * Can log in as an 'admin' or a normal 'user'.
 *
 * @param {'admin'|'user'} username - The username to simulate (defaults to 'user').
 */
Cypress.Commands.add('loginAs', (username = 'user') => {
    const log = Cypress.log({
        displayName: 'Cognito Login',
        message: [`🔐 Authenticating | ${username}`],
        autoEnd: false,
    });
    let cognitoOathEndpoint = '';
    let cognitoOathClientName = '';
    let cognitoAuthEndpoint = '';
    log.snapshot('before');
    // Temporarily suppress exceptions. We expect to get 401's which will trigger the login redirect
    cy.on('uncaught:exception', () => {
        return false;
    });
    cy.session(
        `cognito-${username}`,
        () => {
            // Handle cognito portal information
            cy.request(BASE_URL + '/env.js').then((resp) => {
                const OIDC_URL_REGEX = /["']?AUTHORITY['"]?:\s*['"]?([A-Za-z:\-._/0-9]+)['"]?/;
                const OIDC_APP_NAME_REGEX = /["']?CLIENT_ID['"]?:\s*['"]?([A-Za-z:\-._/0-9]+)['"]?/;
                const oidcUrlMatches = OIDC_URL_REGEX.exec(resp.body);
                if (oidcUrlMatches && oidcUrlMatches.length === 2) {
                    cognitoOathEndpoint = oidcUrlMatches[1];
                }
                const oidcClientNameMatches = OIDC_APP_NAME_REGEX.exec(resp.body);
                if (oidcClientNameMatches && oidcClientNameMatches.length === 2) {
                    cognitoOathClientName = oidcClientNameMatches[1];
                }
                cy.request(`${cognitoOathEndpoint}/.well-known/openid-configuration`).then((oathResponse) => {
                    cognitoAuthEndpoint = getTopLevelDomain(oathResponse.body.authorization_endpoint);
                    // click the sign in link
                    cy.visit(BASE_URL);
                    cy.contains('button', 'Sign in').click();
                    cy.origin(cognitoAuthEndpoint, { args: username }, (username: string) => {
                        cy.on('uncaught:exception', () => {
                            return false;
                        });
                        // This is a lot of overhead to put in username, but there are intermittent results while waiting
                        // for the DOM to stabilize after the redirect and this way is more foolproof
                        cy.get('input[name="username"]', { timeout: 10000 })
                            .filter(':visible')
                            .first()
                            .as('usernameInput')
                            .then(() => {
                                // click may re‑render; re‑query afterwards
                                cy.get('@usernameInput').click({ force: true });
                            })
                            .then(() => {
                                cy.get('@usernameInput').clear({ force: true });
                                cy.get('@usernameInput').type(username, { force: true });
                            });
                        cy.get('input[name="password"]').filter(':visible').type(Cypress.env('TEST_ACCOUNT_PASSWORD'), { force: true });
                        cy.get('input[aria-label="submit"]').filter(':visible').click({ force: true });
                    },
                    );
                });
                cy.wait(2000);
            });
        },
        {
            validate: () => {
                cy.wrap(sessionStorage)
                    .invoke('getItem', `oidc.user:${cognitoOathEndpoint}:${cognitoOathClientName}`)
                    .should('exist');

            },
        },
    );
    cy.visit(BASE_URL);
    log.snapshot('after');
    log.end();
});

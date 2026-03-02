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

import { getTopLevelDomain } from './utils';

const BASE_URL = Cypress.config('baseUrl') as string;

const APIS = [
    { pattern: '**/configuration*', alias: 'getConfiguration', critical: true },
    { pattern: '**/models*', alias: 'getModels', chat: true },
    { pattern: '**/session*', alias: 'getSessions', chat: true },
    { pattern: '**/api-tokens*', alias: 'getApiTokens' },
    { pattern: '**/repository*', alias: 'getRepositories', chat: true },
    { pattern: '**/collection*', alias: 'getCollections' },
    { pattern: '**/mcp*', alias: 'getMcp' },
    { pattern: '**/mcp-management*', alias: 'getMcpServers' },
    { pattern: '**/mcp-workbench*', alias: 'getMcpWorkbench' },
    { pattern: '**/prompt-templates*', alias: 'getPromptTemplates' },
    { pattern: '**/user-preferences*', alias: 'getUserPreferences' },
];

/**
 * Setup intercepts for critical API calls.
 * Call this before visiting the app.
 */
function setupApiIntercepts () {
    APIS.forEach(({ pattern, alias }) => {
        cy.intercept('GET', pattern).as(alias);
    });
}

/**
 * Wait for all critical API calls to complete.
 */
function waitForCriticalApis () {
    const aliases = APIS.filter(({ critical }) => critical)
        .map(({ alias }) => `@${alias}`);
    cy.wait(aliases, { timeout: 30000 });
}

/**
 * Wait for the app to be fully loaded after authentication.
 */
function waitForAppReady () {
    // Wait for "Loading configuration..." to disappear
    cy.contains('Loading configuration...', { timeout: 15000 }).should('not.exist');

    // Wait for any loading spinners to complete
    cy.get('body').then(($body) => {
        if ($body.find('[class*="awsui_spinner"]').length > 0) {
            cy.get('[class*="awsui_spinner"]', { timeout: 10000 }).should('not.exist');
        }
    });

    // Wait for header to be visible (indicates app is ready)
    cy.get('header', { timeout: 15000 }).should('be.visible');
}

/**
 * Custom command to log in a user via Cognito OAuth2/OIDC.
 * Uses cy.session() for caching and role-specific credentials.
 *
 * @param {'admin'|'user'} role - The role to log in as (defaults to 'user').
 */
Cypress.Commands.add('loginAs', (role = 'user') => {
    const log = Cypress.log({
        displayName: 'Cognito Login',
        message: [`🔐 Authenticating | ${role}`],
        autoEnd: false,
    });

    log.snapshot('before');

    // Temporarily suppress exceptions during login flow
    cy.on('uncaught:exception', () => false);

    cy.session(
        `cognito-${role}`,
        () => {
            cy.request(BASE_URL + '/env.js').then((resp) => {
                const OIDC_URL_REGEX = /["']?AUTHORITY['"]?:\s*['"]?([A-Za-z:\-._/0-9]+)['"]?/;

                const oidcUrlMatches = OIDC_URL_REGEX.exec(resp.body);
                const cognitoOathEndpoint = oidcUrlMatches?.[1] || '';

                cy.request(`${cognitoOathEndpoint}/.well-known/openid-configuration`).then((oathResponse) => {
                    const cognitoAuthEndpoint = getTopLevelDomain(oathResponse.body.authorization_endpoint);

                    // Start the login flow
                    cy.visit(BASE_URL);
                    cy.contains('button', 'Sign in').click();

                    // Perform login on Cognito hosted UI
                    cy.origin(cognitoAuthEndpoint, { args: role }, (userRole: string) => {
                        cy.on('uncaught:exception', () => false);

                        // Get credentials based on role
                        const username = userRole === 'admin'
                            ? Cypress.env('ADMIN_USER_NAME')
                            : Cypress.env('USER_NAME');
                        const password = userRole === 'admin'
                            ? Cypress.env('ADMIN_PASSWORD')
                            : Cypress.env('USER_PASSWORD');

                        // Wait for username field and fill it
                        cy.get('input[name="username"]', { timeout: 10000 })
                            .filter(':visible')
                            .first()
                            .as('usernameInput');
                        cy.get('@usernameInput').click({ force: true });
                        cy.get('@usernameInput').clear({ force: true });
                        cy.get('@usernameInput').type(username, { force: true });

                        // Fill password
                        cy.get('input[name="password"]')
                            .filter(':visible')
                            .type(password, { force: true, log: false });

                        // Submit
                        cy.get('input[type="submit"], input[aria-label="submit"], button[type="submit"]')
                            .filter(':visible')
                            .first()
                            .click({ force: true });
                    });

                    // Wait for redirect back to app and allow configuration to load
                    cy.wait(2000);
                });
            });
        },
        {
            validate: () => {
                // Check that we have an OIDC token in sessionStorage
                // The key format is: oidc.user:<authority>:<client_id>
                // We check for any key starting with 'oidc.user:' since we don't have the exact values here
                cy.window().then((win) => {
                    const hasOidcToken = Object.keys(win.sessionStorage).some((key) =>
                        key.startsWith('oidc.user:')
                    );
                    expect(hasOidcToken).to.equal(true);
                });
            },
            cacheAcrossSpecs: false,
        }
    );

    // After session restore/setup, Cypress clears the page which may have cancelled
    // in-flight API requests. Selectively clear API cache reducers to ensure cancelled
    // requests don't pollute the cache, while preserving user preferences.
    cy.window().then((win) => {
        const persistedState = win.localStorage.getItem('persist:lisa');
        if (persistedState) {
            try {
                const state = JSON.parse(persistedState);
                // Clear only API cache reducers that may have stale/cancelled data
                // Preserve: user, userPreferences, notification, modal, breadcrumbGroup
                const apiReducersToReset = [
                    'models',           // modelManagementApi.reducerPath
                    'configuration',    // configurationApi.reducerPath
                    'sessions',         // sessionApi.reducerPath
                    'rag',              // ragApi.reducerPath
                    'promptTemplates',  // promptTemplateApi.reducerPath
                    'mcpServers',       // mcpServerApi.reducerPath
                    'mcpTools',         // mcpToolsApi.reducerPath
                    'apiTokens',        // apiTokenApi.reducerPath
                    'userPreferences',  // userPreferencesApi.reducerPath
                ];
                apiReducersToReset.forEach((key) => {
                    if (state[key]) {
                        delete state[key];
                    }
                });
                win.localStorage.setItem('persist:lisa', JSON.stringify(state));
            } catch {
                // If parsing fails, remove the entire persisted state
                win.localStorage.removeItem('persist:lisa');
            }
        }
    });

    // Set up intercepts BEFORE visiting so they catch all requests
    // cy.session() clears all intercepts, so we must set them up fresh here
    setupApiIntercepts();

    // Visit the app - intercepts are now ready to catch requests
    cy.visit(BASE_URL);

    // Wait for app to be ready using DOM-based assertions
    waitForAppReady();

    // Now wait for the critical configuration API to complete
    // This ensures the app has loaded its configuration before tests proceed
    // waitForCriticalApis();

    log.snapshot('after');
    log.end();
});

/**
 * Custom command to ensure the app is ready for testing.
 * Use in beforeEach when you need to ensure APIs have loaded.
 * Does not re-visit if already on the app.
 */
Cypress.Commands.add('waitForApp', () => {
    // Check if we're already on the app
    cy.url().then((url) => {
        const isOnApp = url.includes(new URL(BASE_URL).host);

        if (!isOnApp) {
            // Need to visit the app
            setupApiIntercepts();
            cy.visit(BASE_URL);
            waitForCriticalApis();
        }

        waitForAppReady();
    });
});

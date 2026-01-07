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

import { randomUUID, randomString, toBase64Url } from './utils';

// List of endpoints to stub with fixtures
const API_STUBS = [
    { endpoint: 'models', alias: 'getModels' },
    { endpoint: 'prompt-templates', alias: 'getPromptTemplates' },
    { endpoint: 'repository', alias: 'getRepositories' },
    { endpoint: 'configuration', alias: 'getConfiguration' },
    { endpoint: 'health', alias: 'getHealth' },
    { endpoint: 'session', alias: 'getSessions' },
    { endpoint: 'api-tokens', alias: 'getApiTokens' },
    { endpoint: 'mcp', alias: 'getMcp' },
    { endpoint: 'mcp-server', alias: 'getMcpServers' },
    { endpoint: 'mcp-workbench', alias: 'getMcpWorkbench' },
    { endpoint: 'collections', alias: 'getCollections' },
];

/**
 * Setup API stubs for smoke tests.
 */
function setupApiStubs (env: Record<string, unknown>) {
    const script = `window.env = ${JSON.stringify(env)};`;
    const apiBase = String(env.API_BASE_URL).replace(/\/+$/, '');

    cy.intercept('GET', '**/env.js', {
        body: script,
        headers: { 'Content-Type': 'application/javascript' },
    }).as('stubEnv');

    // Stub all API endpoints
    API_STUBS.forEach((name) => {
        const alias = `stub${name.charAt(0).toUpperCase()}${name.slice(1)}`;
        cy.intercept('GET', `**${apiBase}/${name}*`, { fixture: `${name}.json` }).as(alias);
    });
}

/**
 * Build a mock OIDC user object.
 */
function buildOidcUser (role: 'admin' | 'user', env: Record<string, unknown>) {
    const isAdmin = role === 'admin';
    const groups = isAdmin ? ['admin'] : ['user'];
    const now = Math.floor(Date.now() / 1000);

    const jwtPayload = {
        sub: randomUUID(),
        iss: env.AUTHORITY,
        aud: env.CLIENT_ID,
        exp: now + 3600,
        iat: now,
        token_use: 'id',
        'cognito:groups': groups,
        'cognito:username': randomUUID(),
        preferred_username: `test-${role}`,
        name: `Test ${role.charAt(0).toUpperCase() + role.slice(1)}`,
        email: `test-${role}@example.com`,
        origin_jti: randomUUID(),
        event_id: randomUUID(),
    };

    const header = { alg: 'none', typ: 'JWT' };
    const id_token = `${toBase64Url(header)}.${toBase64Url(jwtPayload)}.`;

    return {
        id_token,
        access_token: randomString(30),
        refresh_token: randomString(40),
        token_type: 'Bearer',
        expires_at: now + 3600,
        profile: jwtPayload,
        session_state: null,
        scope: 'openid profile email',
    };
}

/**
 * Setup OIDC stubs for the login flow.
 */
function setupOidcStubs (role: 'admin' | 'user', env: Record<string, unknown>) {
    const oidcUser = buildOidcUser(role, env);

    // Stub OIDC discovery
    cy.intercept('GET', '**/.well-known/openid-configuration', {
        statusCode: 200,
        fixture: 'openid-config.json',
    }).as('stubOidc');

    // Stub the token endpoint to return our mock user
    cy.intercept('POST', '**/token', {
        statusCode: 200,
        headers: { 'Content-Type': 'application/json' },
        body: {
            id_token: oidcUser.id_token,
            access_token: oidcUser.access_token,
            refresh_token: oidcUser.refresh_token,
            token_type: 'Bearer',
            expires_in: 3600,
        },
    }).as('stubToken');

    // Stub the authorize endpoint to redirect back with a code
    cy.intercept('GET', '**/authorize?*', (req) => {
        const url = new URL(req.url);
        const state = url.searchParams.get('state');
        const redirectUri = url.searchParams.get('redirect_uri') || 'http://localhost:3000';
        
        // Redirect back to the app with auth code
        req.redirect(`${redirectUri}?code=mock-auth-code&state=${state}`);
    }).as('stubAuthorize');
}

/**
 * Wait for the app to be fully loaded.
 */
function waitForAppReady () {
    // Wait for "Loading configuration..." to disappear
    cy.contains('Loading configuration...', { timeout: 15000 }).should('not.exist');

    // Wait for spinners to disappear
    cy.get('body').then(($body) => {
        if ($body.find('[class*="awsui_spinner"]').length > 0) {
            cy.get('[class*="awsui_spinner"]', { timeout: 10000 }).should('not.exist');
        }
    });
}

/**
 * Custom command to log in a user via stubbed OIDC flow.
 */
Cypress.Commands.add('loginAs', (role = 'user') => {
    cy.fixture('env.json').then((env) => {
        // Setup all stubs
        setupApiStubs(env);
        setupOidcStubs(role, env);

        // Visit the app
        cy.visit('/');

        // Click sign in to trigger OIDC flow
        cy.contains('Sign in').click();

        // Wait for the redirect and login to complete
        cy.contains('Sign in', { timeout: 10000 }).should('not.exist');

        // Wait for app to be ready
        waitForAppReady();
    });
});

/**
 * Custom command to setup API stubs.
 */
Cypress.Commands.add('setupStubs', () => {
    cy.fixture('env.json').then((env) => {
        setupApiStubs(env);
    });
});

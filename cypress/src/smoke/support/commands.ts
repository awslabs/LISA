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

const API_STUBS = [
    { endpoint: 'models', alias: 'getModels' },
    { endpoint: 'prompt-templates', alias: 'getPromptTemplates' },
    { endpoint: 'repository', alias: 'getRepositories' },
    { endpoint: 'configuration', alias: 'getConfiguration' },
    { endpoint: 'health', alias: 'getHealth' },
    { endpoint: 'api-tokens', alias: 'getApiTokens' },
    { endpoint: 'mcp', alias: 'getMcp' },
    { endpoint: 'mcp-server', alias: 'getMcpServers' },
    { endpoint: 'mcp-workbench', alias: 'getMcpWorkbench' },
    { endpoint: 'collections', alias: 'getCollections' },
];

// Stateful mock data for projects
let mockProjects: Array<{
    projectId: string;
    name: string;
    createTime: string;
    lastUpdated: string;
}> = [];

// Stateful mock data for sessions
let mockSessions: Array<{
    sessionId: string;
    name: string | null;
    firstHumanMessage: string;
    startTime: string;
    createTime: string;
    lastUpdated: string;
    projectId?: string;
    isEncrypted: boolean;
}> = [];

/**
 * Setup stateful project stubs that track mutations.
 */
function setupProjectStubs (apiBase: string) {
    // Initialize from fixture with dynamic dates computed from _*DaysAgo metadata
    cy.fixture('project.json').then((fixtureProjects) => {
        mockProjects = fixtureProjects.map(applyDateOffsets) as typeof mockProjects;
    });

    // GET projects - returns current state
    cy.intercept('GET', `**${apiBase}/project*`, (req) => {
        req.reply({ body: mockProjects });
    }).as('getProjects');

    // POST - create project and add to state
    cy.intercept('POST', `**${apiBase}/project`, (req) => {
        const newProject = {
            projectId: randomUUID(),
            name: req.body?.name || 'New Project',
            createTime: new Date().toISOString(),
            lastUpdated: new Date().toISOString(),
        };
        mockProjects.push(newProject);
        req.reply({ statusCode: 201, body: newProject });
    }).as('createProject');

    // PUT - update project name in state
    cy.intercept('PUT', new RegExp(`${apiBase}/project/[^/]+$`), (req) => {
        const projectId = req.url.split('/').pop()?.split('?')[0];
        const idx = mockProjects.findIndex((p) => p.projectId === projectId);
        if (idx >= 0 && req.body?.name) {
            mockProjects[idx].name = req.body.name;
            mockProjects[idx].lastUpdated = new Date().toISOString();
        }
        req.reply({ statusCode: 200, body: mockProjects[idx] || { message: 'Updated' } });
    }).as('updateProject');

    // DELETE - remove project from state, optionally delete sessions
    cy.intercept('DELETE', `**${apiBase}/project/*`, (req) => {
        const url = new URL(req.url);
        const pathParts = url.pathname.split('/');
        const projectId = pathParts[pathParts.length - 1];
        const deleteSessions = req.body?.deleteSessions === true;

        // Remove project
        mockProjects = mockProjects.filter((p) => p.projectId !== projectId);

        // If deleteSessions is true, remove sessions with this projectId
        if (deleteSessions) {
            mockSessions = mockSessions.filter((s) => s.projectId !== projectId);
        } else {
            // Just unassign sessions from this project
            mockSessions = mockSessions.map((s) =>
                s.projectId === projectId ? { ...s, projectId: undefined } : s
            );
        }

        req.reply({ statusCode: 200, body: { message: 'Deleted' } });
    }).as('deleteProject');

    // PUT session assignment
    cy.intercept('PUT', `**${apiBase}/project/*/session/*`, (req) => {
        const url = new URL(req.url);
        const pathParts = url.pathname.split('/');
        const sessionId = pathParts[pathParts.length - 1];
        const projectId = pathParts[pathParts.length - 3];
        const unassign = req.body?.unassign === true;

        const idx = mockSessions.findIndex((s) => s.sessionId === sessionId);
        if (idx >= 0) {
            mockSessions[idx].projectId = unassign ? undefined : projectId;
        }

        req.reply({ statusCode: 200, body: { message: 'Session assignment updated' } });
    }).as('assignSession');
}

/**
 * Compute a date relative to now, offset by the given number of days.
 */
function daysAgo (days: number): string {
    const date = new Date();
    date.setDate(date.getDate() - days);
    return date.toISOString();
}

/**
 * Transforms a fixture entry by converting underscore-prefixed day-offset
 * metadata fields (_startDaysAgo, _updatedDaysAgo, _createDaysAgo) into
 * real ISO date strings, then strips the metadata fields.
 *
 * This keeps fixture JSON files as the single source of truth for both
 * API shape and timing intent. See Sessions.tsx for bucket boundaries:
 * Last Day (<=1), Last 7 Days (<=7), Last Month (<=30),
 * Last 3 Months (<=90), Older (>90).
 */
function applyDateOffsets (fixture: Record<string, unknown>): Record<string, unknown> {
    const result = { ...fixture };

    if (typeof result._startDaysAgo === 'number') {
        result.startTime = daysAgo(result._startDaysAgo as number);
        result.createTime = daysAgo(result._startDaysAgo as number);
    }
    if (typeof result._createDaysAgo === 'number') {
        result.createTime = daysAgo(result._createDaysAgo as number);
    }
    if (typeof result._updatedDaysAgo === 'number') {
        result.lastUpdated = daysAgo(result._updatedDaysAgo as number);
    }

    // Strip metadata fields before using as mock API response
    delete result._startDaysAgo;
    delete result._createDaysAgo;
    delete result._updatedDaysAgo;
    delete result._expectedBucket;

    return result;
}

/**
 * Setup stateful session stubs that track mutations.
 */
function setupSessionStubs (apiBase: string) {
    // Initialize from fixture with dynamic dates computed from _*DaysAgo metadata
    cy.fixture('session.json').then((fixtureSessions) => {
        mockSessions = fixtureSessions.map(applyDateOffsets) as typeof mockSessions;
    });

    // GET sessions - returns current state
    cy.intercept('GET', `**${apiBase}/session*`, (req) => {
        req.reply({ body: mockSessions });
    }).as('getSessions');
}

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

    // Stub all static API endpoints
    API_STUBS.forEach(({ endpoint, alias }) => {
        cy.intercept('GET', `**${apiBase}/${endpoint}*`, { fixture: `${endpoint}.json` }).as(alias);
    });

    // Setup stateful project stubs
    setupProjectStubs(apiBase);

    // Setup stateful session stubs
    setupSessionStubs(apiBase);
}

/**
 * Build a mock OIDC user object.
 */
function buildOidcUser (role: 'admin' | 'user' | 'rag-admin', env: Record<string, unknown>) {
    const groups = role === 'admin' ? ['admin'] : role === 'rag-admin' ? ['rag-admin'] : ['user'];
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
function setupOidcStubs (role: 'admin' | 'user' | 'rag-admin', env: Record<string, unknown>) {
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
    cy.contains('Loading configuration...', { timeout: 30000 }).should('not.exist');

    // Wait for spinners to disappear
    cy.get('body').then(($body) => {
        if ($body.find('[class*="awsui_spinner"]').length > 0) {
            cy.get('[class*="awsui_spinner"]', { timeout: 15000 }).should('not.exist');
        }
    });
}

/**
 * Custom command to log in a user via stubbed OIDC flow.
 */
Cypress.Commands.add('loginAs', (role: 'admin' | 'user' | 'rag-admin' = 'user') => {
    cy.fixture('env.json').then((env) => {
        // Setup all stubs
        setupApiStubs(env);
        setupOidcStubs(role, env);

        // Visit the app
        cy.visit('/');

        cy.get('button', { timeout: 30000 })
            .contains('Sign in')
            .should('be.visible')
            .click({ force: true });

        // Wait for the redirect and login to complete
        cy.get('button').contains('Sign in', { timeout: 20000 }).should('not.exist');

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

/// <reference types="cypress" />

import { randomUUID, randomString, toBase64Url } from './utils';

// Base application URL from Cypress config
const BASE_URL = Cypress.config('baseUrl');

// List of endpoints to stub with fixtures
const API_STUBS = [
    'models',
    'prompt-templates',
    'repository',
    'configuration',
    'health',
    'session',
];

/**
 * Custom command to log in a user via stubbed OAuth2/OIDC.
 * Can log in as an 'admin' or a normal 'user'.
 *
 * @param {'admin'|'user'} role - The role to simulate (defaults to 'user').
 */
Cypress.Commands.add('loginAs', (role = 'user') => {
    const isAdmin = role === 'admin';

    // --- Stub env.js so window.env is correct ---
    cy.fixture('env.json').then((env) => {
        const script = `window.env = ${JSON.stringify(env)};`;
        cy.intercept('GET', '**/env.js', {
            body: script,
            headers: { 'Content-Type': 'application/javascript' },
        }).as('stubEnv');
    });

    // --- Stub all API endpoints ---
    API_STUBS.forEach((name) => {
        const alias = `stub${name.charAt(0).toUpperCase()}${name.slice(1)}`;
        cy.intercept('GET', `**/${name}*`, { fixture: `${name}.json` }).as(alias);
    });

    // --- Stub the OIDC /token endpoint with a fresh, valid-looking JWT ---
    cy.fixture('oidc-user.json').then((user) => {
        const now = Math.floor(Date.now() / 1000);
        const profile = {
            ...user.profile,
            iat: now,
            exp: now + 3600,
            'cognito:groups': isAdmin ? ['admin'] : ['user'],
            sub: randomUUID(),
            'cognito:username': randomUUID(),
            preferred_username: randomString(8),
            origin_jti: randomUUID(),
            event_id: randomUUID(),
            aud: randomUUID(),
            name: `User ${randomString(5)}`,
            email: `${randomString(6)}@example.com`,
        };

        // --- Build an signed JWT that the OIDC client will accept ---
        const header = { alg: 'none', typ: 'JWT' };
        const payload = { ...profile, token_use: 'id' };
        const id_token = `${toBase64Url(header)}.${toBase64Url(payload)}.`;

        // --- Build the stubbed response ---
        const stubbed = {
            ...user,
            profile,
            id_token,
            access_token: randomString(30),
            refresh_token: randomString(40),
            expires_at: now + 3600,
        };

        cy.intercept('POST', '**/token', {
            statusCode: 200,
            headers: { 'Content-Type': 'application/json' },
            body: stubbed,
        }).as('stubToken');
    });

    // --- Stub the OAuth2 authorize callback to redirect straight into the app ---
    cy.intercept('GET', '**/authorize?*', (req) => {
        const { state } = req.query;
        req.redirect(`${BASE_URL}?code=1234&state=${state}`);
    }).as('stubSigninCallback');

    // --- Stub OIDC discovery document ---
    cy.intercept('GET', '**/.well-known/openid-configuration', {
        statusCode: 200,
        fixture: 'openid-config.json',
    }).as('stubOidc');

    // --- Trigger the login flow in the UI ---
    cy.visit('/');
    cy.contains('Sign in').click();
});

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
 * Pre-test cleanup spec. Runs before other E2E specs to ensure a clean
 * environment by deleting all e2e-* prefixed resources and polling until
 * async deletions (models, repositories) are fully complete.
 *
 * Run this spec first via --spec ordering in CI workflows.
 */

import { makeAuthenticatedRequest } from '../../support/collectionHelpers';

const E2E_PREFIX = 'e2e-';
const E2E_PROMPT_PREFIX = 'E2E ';
const POLL_INTERVAL = 5000;
const DELETION_TIMEOUT = 120000;

describe('E2E Environment Cleanup', () => {
    before(() => {
        Cypress.session.clearAllSavedSessions();
    });

    beforeEach(() => {
        cy.loginAs('admin');
    });

    it('Delete all E2E sessions', () => {
        makeAuthenticatedRequest('DELETE', '/session').then((response) => {
            if (response.status >= 200 && response.status < 300) {
                cy.log('Deleted all sessions');
            } else {
                cy.log(`Session deletion returned status: ${response.status}`);
            }
        });
    });

    it('Delete all E2E repositories and wait for removal', () => {
        makeAuthenticatedRequest('GET', '/repository').then((response) => {
            if (response.status !== 200) {
                cy.log(`Failed to list repositories: ${response.status}`);
                return;
            }

            const repositories = response.body ?? [];
            const e2eRepos = repositories.filter((r: any) =>
                typeof r.repositoryId === 'string' && r.repositoryId.startsWith(E2E_PREFIX)
            );

            if (e2eRepos.length === 0) {
                cy.log('No E2E repositories to clean up');
                return;
            }

            cy.log(`Deleting ${e2eRepos.length} E2E repository(ies)`);

            const repoIds = e2eRepos.map((r: any) => r.repositoryId);

            e2eRepos.forEach((repo: any) => {
                makeAuthenticatedRequest('DELETE', `/repository/${repo.repositoryId}`).then((delResp) => {
                    cy.log(`DELETE /repository/${repo.repositoryId} → ${delResp.status}`);
                });
            });

            // Poll until all e2e repos are fully removed
            pollUntilGone('repositories', '/repository', repoIds, (body) => {
                const repos = body ?? [];
                return repos.filter((r: any) => repoIds.includes(r.repositoryId));
            });
        });
    });

    it('Delete all E2E prompt templates', () => {
        makeAuthenticatedRequest('GET', '/prompt-templates').then((response) => {
            if (response.status !== 200) {
                cy.log(`Failed to list prompt templates: ${response.status}`);
                return;
            }

            const templates = response.body?.templates ?? [];
            const e2eTemplates = templates.filter((t: any) =>
                typeof t.title === 'string' && t.title.startsWith(E2E_PROMPT_PREFIX)
            );

            if (e2eTemplates.length === 0) {
                cy.log('No E2E prompt templates to clean up');
                return;
            }

            cy.log(`Deleting ${e2eTemplates.length} E2E prompt template(s)`);

            e2eTemplates.forEach((template: any) => {
                const templateId = template.promptTemplateId || template.id;
                if (templateId) {
                    makeAuthenticatedRequest('DELETE', `/prompt-templates/${templateId}`).then((delResp) => {
                        cy.log(`DELETE prompt template "${template.title}" → ${delResp.status}`);
                    });
                }
            });
        });
    });

    it('Delete all E2E models and wait for removal', () => {
        makeAuthenticatedRequest('GET', '/models').then((response) => {
            if (response.status !== 200) {
                cy.log(`Failed to list models: ${response.status}`);
                return;
            }

            const models = response.body?.models ?? [];
            const e2eModels = models.filter((m: any) =>
                typeof m.modelId === 'string' && m.modelId.startsWith(E2E_PREFIX)
            );

            if (e2eModels.length === 0) {
                cy.log('No E2E models to clean up');
                return;
            }

            cy.log(`Deleting ${e2eModels.length} E2E model(s)`);

            const modelIds = e2eModels.map((m: any) => m.modelId);

            e2eModels.forEach((model: any) => {
                makeAuthenticatedRequest('DELETE', `/models/${model.modelId}`).then((delResp) => {
                    cy.log(`DELETE /models/${model.modelId} → ${delResp.status}`);
                });
            });

            // Poll until all e2e models are fully removed
            pollUntilGone('models', '/models', modelIds, (body) => {
                const models = body?.models ?? [];
                return models.filter((m: any) => modelIds.includes(m.modelId));
            });
        });
    });
});

/**
 * Poll an API endpoint until none of the target resource IDs remain.
 * Handles async deletion (state machines, CloudFormation teardown).
 */
function pollUntilGone (
    resourceType: string,
    endpoint: string,
    targetIds: string[],
    extractRemaining: (body: any) => any[],
) {
    cy.log(`Waiting for ${targetIds.length} ${resourceType} to be fully removed...`);
    const startTime = Date.now();

    function check (): void {
        makeAuthenticatedRequest('GET', endpoint).then((response) => {
            const remaining = response.status === 200 ? extractRemaining(response.body) : [];

            if (remaining.length === 0) {
                cy.log(`All E2E ${resourceType} fully removed`);
                return;
            }

            const elapsed = Date.now() - startTime;
            if (elapsed < DELETION_TIMEOUT) {
                cy.log(`${remaining.length} ${resourceType} still deleting, polling...`);
                cy.wait(POLL_INTERVAL).then(() => check());
            } else {
                cy.log(`WARNING: ${remaining.length} ${resourceType} still present after ${DELETION_TIMEOUT}ms`);
            }
        });
    }

    check();
}

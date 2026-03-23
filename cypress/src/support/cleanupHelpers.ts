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

/**
 * cleanupHelpers.ts
 * API-based sweep cleanup for E2E test resources.
 * Finds and deletes ALL resources matching the e2e- prefix,
 * regardless of which test run created them.
 */

import { makeAuthenticatedRequest } from './collectionHelpers';

const E2E_PREFIX = 'e2e-';
const E2E_PROMPT_PREFIX = 'E2E ';

/**
 * Delete all models whose modelId starts with the E2E prefix.
 */
export function sweepE2eModels () {
    cy.log('Sweeping E2E models...');
    makeAuthenticatedRequest('GET', '/models').then((response) => {
        if (response.status !== 200) {
            cy.log(`Failed to list models: ${response.status}`);
            return;
        }

        const models = response.body?.models ?? [];
        const e2eModels = models.filter((m: any) =>
            typeof m.modelId === 'string' && m.modelId.startsWith(E2E_PREFIX)
        );

        cy.log(`Found ${e2eModels.length} E2E model(s) to clean up`);

        e2eModels.forEach((model: any) => {
            cy.log(`Deleting model: ${model.modelId}`);
            makeAuthenticatedRequest('DELETE', `/models/${model.modelId}`).then((delResp) => {
                if (delResp.status >= 200 && delResp.status < 300) {
                    cy.log(`Deleted model ${model.modelId}`);
                } else {
                    cy.log(`Failed to delete model ${model.modelId}: ${delResp.status}`);
                }
            });
        });
    });
}

/**
 * Delete all repositories whose repositoryId starts with the E2E prefix.
 * Repository deletion cascades to collections and documents.
 */
export function sweepE2eRepositories () {
    cy.log('Sweeping E2E repositories...');
    makeAuthenticatedRequest('GET', '/repository').then((response) => {
        if (response.status !== 200) {
            cy.log(`Failed to list repositories: ${response.status}`);
            return;
        }

        const repositories = response.body ?? [];
        const e2eRepos = repositories.filter((r: any) =>
            typeof r.repositoryId === 'string' && r.repositoryId.startsWith(E2E_PREFIX)
        );

        cy.log(`Found ${e2eRepos.length} E2E repository(ies) to clean up`);

        e2eRepos.forEach((repo: any) => {
            cy.log(`Deleting repository: ${repo.repositoryId}`);
            makeAuthenticatedRequest('DELETE', `/repository/${repo.repositoryId}`).then((delResp) => {
                if (delResp.status >= 200 && delResp.status < 300) {
                    cy.log(`Deleted repository ${repo.repositoryId}`);
                } else {
                    cy.log(`Failed to delete repository ${repo.repositoryId}: ${delResp.status}`);
                }
            });
        });
    });
}

/**
 * Delete all prompt templates whose title starts with the E2E prefix.
 */
export function sweepE2ePromptTemplates () {
    cy.log('Sweeping E2E prompt templates...');
    makeAuthenticatedRequest('GET', '/prompt-templates').then((response) => {
        if (response.status !== 200) {
            cy.log(`Failed to list prompt templates: ${response.status}`);
            return;
        }

        const templates = response.body?.templates ?? [];
        const e2eTemplates = templates.filter((t: any) =>
            typeof t.title === 'string' && t.title.startsWith(E2E_PROMPT_PREFIX)
        );

        cy.log(`Found ${e2eTemplates.length} E2E prompt template(s) to clean up`);

        e2eTemplates.forEach((template: any) => {
            const templateId = template.promptTemplateId || template.id;
            if (!templateId) {
                cy.log(`Skipping template "${template.title}" - no ID found`);
                return;
            }
            cy.log(`Deleting prompt template: ${template.title} (${templateId})`);
            makeAuthenticatedRequest('DELETE', `/prompt-templates/${templateId}`).then((delResp) => {
                if (delResp.status >= 200 && delResp.status < 300) {
                    cy.log(`Deleted prompt template ${templateId}`);
                } else {
                    cy.log(`Failed to delete prompt template ${templateId}: ${delResp.status}`);
                }
            });
        });
    });
}

/**
 * Delete all sessions for the current user.
 */
export function sweepE2eSessions () {
    cy.log('Sweeping E2E sessions...');
    makeAuthenticatedRequest('DELETE', '/session').then((response) => {
        if (response.status >= 200 && response.status < 300) {
            cy.log('Deleted all sessions');
        } else {
            cy.log(`Failed to delete sessions: ${response.status}`);
        }
    });
}

/**
 * Sweep all E2E test resources. Intended to run in before/after hooks
 * to ensure a clean environment regardless of prior test state.
 *
 * Deletion order matters: sessions first, then repositories (cascades to
 * collections/documents), then prompt templates, then models.
 */
export function sweepAllE2eResources () {
    cy.log('=== Starting E2E resource sweep ===');
    sweepE2eSessions();
    sweepE2eRepositories();
    sweepE2ePromptTemplates();
    sweepE2eModels();
    cy.log('=== E2E resource sweep complete ===');
}

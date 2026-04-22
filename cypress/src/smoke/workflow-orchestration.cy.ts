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

describe('Workflow Orchestration Approval (Smoke)', () => {
    beforeEach(() => {
        cy.loginAs('admin');
    });

    after(() => {
        cy.clearAllSessionStorage();
    });

    it('creates a workflow from the nightly template through UI', () => {
        cy.intercept('POST', '**/workflows', (req) => {
            expect(req.url).to.match(/\/workflows(?:\?|$)/);
            expect(req.body).to.include({
                templateId: 'nightly-rag-summary',
                name: 'Nightly RAG Summary Smoke',
            });
            req.reply({
                statusCode: 201,
                body: {
                    workflowId: 'workflow-smoke-001',
                    name: 'Nightly RAG Summary Smoke (Server Name)',
                    created: '2026-04-22T00:00:00.000Z',
                    state: 'CREATED',
                },
            });
        }).as('createWorkflow');

        cy.visit('/');
        cy.contains('a', 'Workflow Templates')
            .should('be.visible')
            .and('have.attr', 'href')
            .and('include', '/workflow-management')
            .click();
        cy.url().should('include', '/workflow-management');
        cy.get('[data-testid="workflow-template-select"]').should('exist');
        cy.get('[data-testid="workflow-name-input"] input').clear().type('Nightly RAG Summary Smoke');
        cy.get('[data-testid="workflow-create-from-template"]').click();

        cy.wait('@createWorkflow').its('request.url').should('match', /\/workflows(?:\?|$)/);
        cy.contains('No workflows created yet.').should('not.exist');
        cy.contains('Nightly RAG Summary Smoke (Server Name)').should('be.visible');
    });
});

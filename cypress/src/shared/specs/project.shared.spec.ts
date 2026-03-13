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
 * Shared test suite for Projects Organization feature.
 * Can be used by both smoke tests (with fixtures) and e2e tests (with real data).
 */

import {
    navigateToChatPage,
    switchToProjectsView,
    switchToHistoryView,
    verifyCurrentView,
    verifyViewPersistence,
    createProject,
    renameProject,
    deleteProjectOnly,
    deleteProjectWithSessions,
    verifyProjectExists,
    verifyProjectNotExists,
} from '../../support/projectHelpers';

export function runProjectsTests (options: {
    verifyFixtureData?: boolean;
} = {}) {
    const { verifyFixtureData = false } = options;

    describe('View Toggle & Navigation', () => {
        it('should have configuration loaded with projectOrganization enabled', () => {
            // First verify the intercept captured the configuration call
            cy.wait('@getConfiguration', { timeout: 10000 }).its('response.body').then((body) => {
                expect(body).to.be.an('array');
                expect(body[0]).to.have.nested.property('configuration.enabledComponents.projectOrganization', true);
            });
        });

        it('should display segmented control with History and Projects options', () => {
            navigateToChatPage();

            // Wait for projects to load
            cy.wait('@getProjects', { timeout: 30000 });

            // Verify both view options are visible
            cy.get('[data-testid="project-history-toggle"]').should('be.visible');
            cy.get('[data-testid="history"]', { timeout: 5000 }).should('be.visible');
            cy.get('[data-testid="projects"]').should('be.visible');
        });

        it('should switch between History and Projects views', () => {
            navigateToChatPage();
            cy.wait('@getProjects', { timeout: 30000 });

            // Default should be History
            verifyCurrentView('history');

            // Switch to Projects
            switchToProjectsView();
            verifyCurrentView('projects');

            // Switch back to History
            switchToHistoryView();
            verifyCurrentView('history');
        });

        it('should persist view selection to localStorage', () => {
            navigateToChatPage();
            cy.wait('@getProjects', { timeout: 30000 });

            // Switch to Projects view
            switchToProjectsView();
            verifyViewPersistence('projects');

            // Switch to History view
            switchToHistoryView();
            verifyViewPersistence('history');
        });

        it('should restore view selection after page refresh', () => {
            navigateToChatPage();
            cy.wait('@getProjects', { timeout: 30000 });

            // Switch to Projects view
            switchToProjectsView();
            verifyCurrentView('projects');

            // Refresh page
            cy.reload();
            cy.wait('@getProjects', { timeout: 30000 });

            // Should still be on Projects view
            verifyCurrentView('projects');
        });
    });

    describe('Create Projects', () => {
        beforeEach(() => {
            navigateToChatPage();
            cy.wait('@getProjects', { timeout: 30000 });
            switchToProjectsView();
        });

        it('should open New Project modal from New dropdown', () => {
            // Click New button
            cy.contains('button', 'New').click();

            // Click New Project menu item
            cy.get('[data-testid="new-project"]').should('be.visible').click();

            // Verify modal appears with correct header
            cy.contains('h2', 'New Project', { timeout: 5000 }).should('be.visible');

            // Cancel to close modal
            cy.get('[data-testid="create-project-cancel"]').click();
        });

        it('should create a new project successfully', () => {
            const projectName = `Test Project ${Date.now()}`;

            createProject(projectName);

            // Verify project appears in list
            verifyProjectExists(projectName);
        });

        it('should validate empty project name', () => {
            // Open New Project modal
            cy.contains('button', 'New').click();
            cy.get('[data-testid="new-project"]').click();

            // Wait for modal
            cy.contains('h2', 'New Project', { timeout: 5000 }).should('be.visible');

            // Try to confirm with empty name - Create button should be disabled
            cy.get('[data-testid="input-placeholder"]').should('be.visible').clear();
            cy.get('button').filter(':visible').contains('Create').closest('button').should('be.disabled');

            // Cancel to close modal
            cy.get('[data-testid="create-project-cancel"]').click();
        });

        if (verifyFixtureData) {
            it('should display fixture projects', () => {
                verifyProjectExists('Research');
                verifyProjectExists('Product Dev');
            });
        }
    });

    describe('Rename Projects', () => {
        beforeEach(() => {
            navigateToChatPage();
            cy.wait('@getProjects', { timeout: 30000 });
            switchToProjectsView();
        });

        it('should open Rename modal with current name pre-filled', () => {
            const projectName = verifyFixtureData ? 'Research' : 'Test Project';

            // Skip if no projects exist
            cy.get('body').then(($body) => {
                if (!$body.text().includes(projectName)) {
                    cy.log('Skipping: No projects found');
                    return;
                }

                // Open project actions menu
                cy.get(`[aria-label="Project actions for ${projectName}"]`)
                    .first()
                    .should('be.visible')
                    .click();

                // Click Rename
                cy.get('[data-testid="rename"]').click();

                // Verify modal with current name
                cy.contains('h2', 'Rename Project', { timeout: 5000 }).should('be.visible');
                cy.get('[data-testid="rename-project-input"] input').should('have.value', projectName);

                // Cancel
                cy.get('[data-testid="rename-project-cancel"]').click();
            });
        });

        it('should rename a project successfully', () => {
            const originalName = `Original ${Date.now()}`;
            const newName = `Renamed ${Date.now()}`;

            // Create a project first
            createProject(originalName);
            verifyProjectExists(originalName);

            // Rename it
            renameProject(originalName, newName);

            // Verify new name appears and old name is gone
            verifyProjectExists(newName);
            verifyProjectNotExists(originalName);
        });
    });

    describe('Delete Projects', () => {
        beforeEach(() => {
            navigateToChatPage();
            cy.wait('@getProjects', { timeout: 30000 });
            switchToProjectsView();
        });

        it('should show delete modal with two options', () => {
            const projectName = `Delete Test ${Date.now()}`;

            // Create a project
            createProject(projectName);

            // Open delete modal
            cy.get(`[aria-label="Project actions for ${projectName}"]`)
                .first()
                .should('be.visible')
                .click();
            cy.get('[data-testid="delete"]').first().click();

            // Verify modal shows both delete options as buttons
            cy.contains('h2', 'Delete Project', { timeout: 5000 }).should('be.visible');
            cy.contains('button', 'Delete project only').should('be.visible');
            cy.contains('button', 'Delete project and sessions').should('be.visible');

            // Cancel
            cy.get('[data-testid="delete-project-cancel"]').click();
        });

        it('should delete project only (keep sessions)', () => {
            // Use existing Product Dev project - first assign a session to it
            const projectName = 'Product Dev';
            const sessionName = 'How do I get started'; // Partial match for truncated display

            verifyProjectExists(projectName);

            // Assign a session to this project first
            switchToHistoryView();
            cy.contains('Last 3 Months').click(); // Expand section
            // Find session row and click its actions button (3 dots)
            cy.contains('[data-testid="session-item"]', sessionName, { timeout: 5000 })
                .first()
                .should('be.visible')
                .find('[aria-label="Control instance"]')
                .first()
                .click();
            // Projects are listed directly under "Add to Project" category - click the project name
            cy.contains('[role="menuitem"]', projectName).click();
            cy.wait('@assignSession');

            // Switch back to Projects view and delete project only
            switchToProjectsView();
            deleteProjectOnly(projectName);

            // Verify project is gone
            verifyProjectNotExists(projectName);

            // Verify session still exists in History view (no longer has project badge)
            switchToHistoryView();
            cy.contains('Last 3 Months').click(); // Expand section again
            cy.contains('[data-testid="session-item"]', sessionName, { timeout: 5000 }).first().should('be.visible');
        });

        it('should delete project with all sessions', () => {
            // Use existing Research project from fixtures which has sessions assigned
            const projectName = 'Research';
            const sessionName = 'Technical Discussion';

            verifyProjectExists(projectName);

            // Verify session exists before delete
            switchToHistoryView();
            cy.contains('Last 3 Months').click(); // Expand section
            cy.contains(sessionName, { timeout: 5000 }).should('exist');

            // Switch back and delete project with all sessions
            switchToProjectsView();
            deleteProjectWithSessions(projectName);

            // Verify project is gone
            verifyProjectNotExists(projectName);

            // Reload page to force refetch of sessions with updated mock data
            cy.reload();
            cy.wait('@getSessions');
            cy.wait('@getProjects');

            // Verify session is gone from History view
            switchToHistoryView();
            cy.contains('Last 3 Months').click(); // Expand section
            cy.contains(sessionName, { timeout: 5000 }).should('not.exist');
        });
    });

    describe('Assign Sessions to Projects', () => {
        beforeEach(() => {
            navigateToChatPage();
            cy.wait('@getSessions', { timeout: 30000 });
            cy.wait('@getProjects', { timeout: 30000 });
        });

        it('should show "Add to Project" in session context menu', () => {
            switchToHistoryView();
            cy.contains('Last 3 Months').click(); // Expand section

            // Use a session not assigned to a project
            const sessionName = 'How do I get started';

            // Find session and click its actions button
            cy.contains('[data-testid="session-item"]', sessionName, { timeout: 5000 })
                .first()
                .should('be.visible')
                .find('[aria-label="Control instance"]')
                .first()
                .click();

            // Verify "Add to Project" menu category exists (nested dropdown item)
            cy.contains('Add to Project').should('be.visible');

            // Click elsewhere to close menu
            cy.get('body').click();
        });

        if (verifyFixtureData) {
            it('should assign session to project from History view', () => {
                switchToHistoryView();
                cy.contains('Last 3 Months').click(); // Expand section

                // Use a session not already assigned to a project
                const sessionName = 'How do I get started';
                const projectName = 'Research';

                // Find session and click its actions button
                cy.contains('[data-testid="session-item"]', sessionName, { timeout: 5000 })
                    .first()
                    .should('be.visible')
                    .find('[aria-label="Control instance"]')
                    .first()
                    .click();

                // Click the project name in the dropdown menu (not the badge)
                cy.get('[role="menu"]').contains(projectName).click();
                cy.wait('@assignSession');

                // Switch to Projects view and verify session appears there
                switchToProjectsView();
                cy.contains(projectName).should('be.visible');
            });
        }

        it('should display session in both History and Projects views', () => {
            if (!verifyFixtureData) {
                cy.log('Skipping: Requires fixture data');
                return;
            }

            const sessionName = 'Technical Discussion';
            const projectName = 'Research';

            // Verify in History view
            switchToHistoryView();
            cy.contains('Last 3 Months').click(); // Expand section
            cy.contains('[data-testid="session-item"]', sessionName, { timeout: 5000 }).should('be.visible');

            // Verify in Projects view
            switchToProjectsView();
            cy.contains(projectName).should('be.visible');
        });
    });

    describe('Remove Sessions from Projects', () => {
        beforeEach(() => {
            navigateToChatPage();
            cy.wait('@getSessions', { timeout: 30000 });
            cy.wait('@getProjects', { timeout: 30000 });
        });

        if (verifyFixtureData) {
            it('should remove session from project in History view', () => {
                switchToHistoryView();
                cy.contains('Last 3 Months').click(); // Expand section

                // Use a session that is assigned to a project
                const sessionName = 'Technical Discussion';

                // Verify session has project badge before removal
                cy.contains('[data-testid="session-item"]', sessionName, { timeout: 5000 })
                    .first()
                    .should('be.visible')
                    .should('contain', 'Research');

                // Find session and click its actions button
                cy.contains('[data-testid="session-item"]', sessionName, { timeout: 5000 })
                    .first()
                    .find('[aria-label="Control instance"]')
                    .first()
                    .click();

                // Click Remove from Project
                cy.get('[role="menu"]').contains('Remove from Project').click();

                // Verify the unassign API was called with correct body
                cy.wait('@assignSession').its('request.body').should('deep.equal', { unassign: true });
            });
        }
    });

}

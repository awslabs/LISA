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
 * projectHelpers.ts
 * Reusable helpers for Project Organization feature interactions.
 */

// Project feature selectors
export const PROJECT_SELECTORS = {
    // Segmented control for view toggle
    VIEW_TOGGLE: '[data-testid="project-history-toggle"]',
    HISTORY_VIEW_BUTTON: '[data-testid="history"]',
    PROJECTS_VIEW_BUTTON: '[data-testid="projects"]',

    // Buttons and dropdowns
    NEW_SESSION_DROPDOWN: '[data-testid="new-session-dropdown"]',
    NEW_PROJECT_MENU_ITEM: '[data-testid="new-project"]',
    PROJECT_ACTIONS_BUTTON: (projectName: string) => `[aria-label="Project actions for ${projectName}"]`,
    RENAME_MENU_ITEM: '[data-testid="rename"]',
    DELETE_MENU_ITEM: '[data-testid="delete"]',
    ADD_TO_PROJECT_MENU_ITEM: '[data-testid="add-to-project"]',
    REMOVE_FROM_PROJECT_MENU_ITEM: '[data-testid="remove-from-project"]',

    // Modals
    MODAL_DIALOG: '[role="dialog"]',
    MODAL_HEADER: '[class*="awsui_header"] h2',
    PROJECT_NAME_INPUT: 'input[placeholder*="Enter project name"]',
    DELETE_PROJECT_ONLY_RADIO: 'input[value="project-only"]',
    DELETE_PROJECT_WITH_SESSIONS_RADIO: 'input[value="with-sessions"]',

    // Lists and items
    PROJECT_LIST_ITEM: (projectName: string) => `[data-testid="project-${projectName}"]`,
    SESSION_ITEM: '[data-testid="session-item"]',
    SESSION_ITEM_ACTIVE: '[data-testid="session-item-active"]',
    PROJECT_BADGE: '[class*="awsui_badge"]',
    SESSION_ACTIONS_BUTTON: '[aria-label="Session actions"]',

    // Empty states
    EMPTY_STATE: '[class*="awsui_empty"]',
    EMPTY_STATE_TEXT: '[class*="awsui_empty"] [class*="awsui_content"]',
};

/**
 * Navigate to the chat page to access session history and projects
 */
export function navigateToChatPage () {
    cy.url().then((url) => {
        if (!url.includes('/ai-assistant')) {
            cy.get('a[aria-label="AI Assistant"]')
                .eq(2)
                .should('exist')
                .and('be.visible')
                .click();

            // Wait for navigation to complete
            cy.url({ timeout: 10000 }).should('include', '/ai-assistant');
        }
    });

    // Wait for any loading spinners to disappear
    cy.get('body').then(($body) => {
        if ($body.find('[class*="awsui_spinner"]').length > 0) {
            cy.get('[class*="awsui_spinner"]', { timeout: 10000 }).should('not.exist');
        }
    });
}

/**
 * Switch to the Projects view using the segmented control
 */
export function switchToProjectsView () {
    cy.get('[data-testid="project-history-toggle"]', { timeout: 15000 })
        .should('be.visible')
        .contains('button', 'Projects')
        .click();

    // Wait for view toggle to update
    cy.get('[data-testid="project-history-toggle"]')
        .contains('button', 'Projects')
        .should('have.attr', 'aria-pressed', 'true');
}

/**
 * Switch to the History view using the segmented control
 */
export function switchToHistoryView () {
    cy.get('[data-testid="project-history-toggle"]', { timeout: 15000 })
        .should('be.visible')
        .contains('button', 'History')
        .click();

    // Wait for view toggle to update
    cy.get('[data-testid="project-history-toggle"]')
        .contains('button', 'History')
        .should('have.attr', 'aria-pressed', 'true');
}

/**
 * Verify the current active view
 * @param view - Expected view: 'history' or 'projects'
 */
export function verifyCurrentView (view: 'history' | 'projects') {
    const selector = view === 'history'
        ? PROJECT_SELECTORS.HISTORY_VIEW_BUTTON
        : PROJECT_SELECTORS.PROJECTS_VIEW_BUTTON;

    cy.get(selector).should('have.attr', 'aria-pressed', 'true');
}

/**
 * Verify view selection is persisted in localStorage
 * @param view - Expected view: 'history' or 'projects'
 */
export function verifyViewPersistence (view: 'history' | 'projects') {
    cy.window().then((win) => {
        const storedView = win.localStorage.getItem('lisa-history-view');
        expect(storedView).to.equal(view);
    });
}

/**
 * Create a new project
 * @param projectName - Name of the project to create
 */
export function createProject (projectName: string) {
    // Open New dropdown using data-testid
    cy.get(PROJECT_SELECTORS.NEW_SESSION_DROPDOWN).click();

    // Click New Project menu item
    cy.get(PROJECT_SELECTORS.NEW_PROJECT_MENU_ITEM).click();

    // Wait for modal header to appear
    cy.contains('h2', 'New Project', { timeout: 5000 }).should('be.visible');

    // Enter project name
    cy.get(PROJECT_SELECTORS.PROJECT_NAME_INPUT)
        .should('be.visible')
        .clear()
        .type(projectName);

    // Confirm
    cy.get('button').filter(':visible').contains('Create').click();

    // Wait for create API call to complete
    cy.wait('@createProject');

    // Wait for modal to close - check that the visible modal header is gone
    cy.contains('h2', 'New Project').should('not.be.visible');
}

/**
 * Rename an existing project
 * @param currentName - Current project name
 * @param newName - New project name
 */
export function renameProject (currentName: string, newName: string) {
    // Open project actions menu
    cy.get(PROJECT_SELECTORS.PROJECT_ACTIONS_BUTTON(currentName))
        .first()
        .should('be.visible')
        .click();

    // Click Rename
    cy.get(PROJECT_SELECTORS.RENAME_MENU_ITEM).click();

    // Wait for modal header to appear
    cy.contains('h2', 'Rename Project', { timeout: 5000 }).should('be.visible');

    // Verify current name is pre-filled and enter new name
    cy.get('[data-testid="rename-project-input"] input')
        .should('have.value', currentName)
        .clear()
        .type(newName);

    // Confirm - button text is "Rename"
    cy.get('button').filter(':visible').contains('Rename').click();

    // Wait for update API call to complete
    cy.wait('@updateProject');

    // Wait for modal to close
    cy.contains('h2', 'Rename Project').should('not.be.visible');
}

/**
 * Delete a project without deleting its sessions
 * @param projectName - Name of the project to delete
 */
export function deleteProjectOnly (projectName: string) {
    // Open project actions menu
    cy.get(PROJECT_SELECTORS.PROJECT_ACTIONS_BUTTON(projectName))
        .first()
        .should('be.visible')
        .click();

    // Click Delete
    cy.get(PROJECT_SELECTORS.DELETE_MENU_ITEM).first().click();

    // Wait for modal header to appear
    cy.contains('h2', 'Delete Project', { timeout: 5000 }).should('be.visible');

    // Click "Delete project only" button
    cy.get('button').filter(':visible').contains('Delete project only').click();

    // Wait for delete API call to complete
    cy.wait('@deleteProject');

    // Wait for modal to close
    cy.contains('h2', 'Delete Project').should('not.be.visible');
}

/**
 * Delete a project and all its sessions
 * @param projectName - Name of the project to delete
 */
export function deleteProjectWithSessions (projectName: string) {
    // Open project actions menu
    cy.get(PROJECT_SELECTORS.PROJECT_ACTIONS_BUTTON(projectName))
        .first()
        .should('be.visible')
        .click();

    // Click Delete
    cy.get(PROJECT_SELECTORS.DELETE_MENU_ITEM).first().click();

    // Wait for modal header to appear
    cy.contains('h2', 'Delete Project', { timeout: 5000 }).should('be.visible');

    // Click "Delete project and sessions" button
    cy.get('button').filter(':visible').contains('Delete project and sessions').click();

    // Wait for delete API call to complete
    cy.wait('@deleteProject');

    // Wait for modal to close
    cy.contains('h2', 'Delete Project').should('not.be.visible');
}


/**
 * Verify that a project exists in the Projects view
 * @param projectName - Name of the project to verify
 */
export function verifyProjectExists (projectName: string) {
    // Project names are truncated to 15 chars in ExpandableSection header
    const displayName = projectName.length > 15 ? `${projectName.slice(0, 15)}...` : projectName;
    cy.contains(displayName, { timeout: 10000 }).should('be.visible');
}

/**
 * Verify that a project does not exist
 * @param projectName - Name of the project that should not exist
 */
export function verifyProjectNotExists (projectName: string) {
    // Project names are truncated to 15 chars in ExpandableSection header
    const displayName = projectName.length > 15 ? `${projectName.slice(0, 15)}...` : projectName;
    cy.contains(displayName, { timeout: 10000 }).should('not.exist');
}


/**
 * Enable the Projects feature via configuration (admin only)
 */
export function enableProjectsFeature () {
    // Navigate to Configuration page
    cy.get('a[aria-label="Configuration"]')
        .should('be.visible')
        .click();

    cy.url().should('include', '/configuration');

    // Find and enable projectOrganization toggle
    cy.contains('Project Organization')
        .parent()
        .within(() => {
            cy.get('input[type="checkbox"]').then(($checkbox) => {
                if (!$checkbox.is(':checked')) {
                    cy.wrap($checkbox).click({ force: true });
                }
            });
        });

    // Save configuration
    cy.contains('button', 'Save').click();

    // Wait for save to complete
    cy.contains('Configuration saved successfully', { timeout: 10000 })
        .should('be.visible');
}

/**
 * Disable the Projects feature via configuration (admin only)
 */
export function disableProjectsFeature () {
    // Navigate to Configuration page
    cy.get('a[aria-label="Configuration"]')
        .should('be.visible')
        .click();

    cy.url().should('include', '/configuration');

    // Find and disable projectOrganization toggle
    cy.contains('Project Organization')
        .parent()
        .within(() => {
            cy.get('input[type="checkbox"]').then(($checkbox) => {
                if ($checkbox.is(':checked')) {
                    cy.wrap($checkbox).click({ force: true });
                }
            });
        });

    // Save configuration
    cy.contains('button', 'Save').click();

    // Wait for save to complete
    cy.contains('Configuration saved successfully', { timeout: 10000 })
        .should('be.visible');
}

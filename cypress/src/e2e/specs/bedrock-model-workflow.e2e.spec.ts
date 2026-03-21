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
 * Full E2E test for Bedrock model creation and chat workflow.
 * Creates a Bedrock model, repository, collections, documents, and prompt templates.
 * Used by the weekly and release CI workflows.
 *
 * Cleanup strategy:
 * - before(): API sweep deletes all e2e-* resources from previous runs (clean slate)
 * - skipCleanup: false: inline UI-based cleanup runs after tests
 * - after(): API sweep catches anything the inline cleanup missed
 */

import { runBedrockModelWorkflowTests } from '../../shared/specs/bedrock-model-workflow.shared.spec';
import { sweepAllE2eResources } from '../../support/cleanupHelpers';

describe('Bedrock Model Workflow (E2E)', () => {
    before(() => {
        // Clear Cypress session cache to allow fresh login
        Cypress.session.clearAllSavedSessions();

        // Login as admin so we have auth tokens for API cleanup
        cy.loginAs('admin');

        // Sweep orphaned resources from previous runs
        sweepAllE2eResources();
    });

    beforeEach(() => {
        cy.loginAs('admin');
    });

    after(() => {
        // Final sweep to catch anything inline cleanup missed or if tests failed
        cy.loginAs('admin');
        sweepAllE2eResources();
    });

    runBedrockModelWorkflowTests({skipCleanup: false});
});

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
 * Quick E2E test for Bedrock model creation, prompt templates, and chat.
 * No infrastructure provisioning (repositories, collections, documents).
 * Suitable for nightly health check runs.
 */

import { runBedrockQuickTests } from '../../shared/specs/bedrock-model-workflow.shared.spec';

describe('Bedrock Quick Workflow (E2E)', () => {
    before(() => {
        // Clear Cypress session cache to allow fresh login
        Cypress.session.clearAllSavedSessions();
    });

    beforeEach(() => {
        cy.loginAs('admin');
    });

    runBedrockQuickTests({skipCleanup: true});
});

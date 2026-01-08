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
 * E2E test for Bedrock model creation and chat workflow.
 * Creates a Bedrock model, then uses it in chat.
 */

import { runBedrockModelWorkflowTests } from '../../shared/specs/bedrock-model-workflow.shared.spec';

describe('Bedrock Model Workflow (E2E)', () => {
    before(() => {
        cy.clearAllSessionStorage();
    });

    beforeEach(() => {
        cy.loginAs('admin');
    });

    runBedrockModelWorkflowTests();
});

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
 * Smoke test suite for Chat Page features.
 * Uses shared test suite with fixture-based session testing enabled.
 */

import { runChatTests } from '../../shared/specs/chat.shared.spec';

describe('Chat Page (Smoke)', () => {
    beforeEach(() => {
        cy.loginAs('user');
    });
    after(() => {
        cy.clearAllSessionStorage();
    });
    runChatTests({
        testSessionSelection: true,
        testRAGConfiguration: true,
    });
});

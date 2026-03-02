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

import './commands';
import '../../support/adminHelpers';

declare global {
    // eslint-disable-next-line @typescript-eslint/no-namespace
    namespace Cypress {
        // eslint-disable-next-line @typescript-eslint/consistent-type-definitions
        interface Chainable {
            /**
             * Custom command to log in a user via Cognito OAuth2/OIDC.
             * Uses cy.session() for caching across specs.
             * @param role - The role to log in as ('admin' or 'user')
             * @example cy.loginAs('admin')
             */
            loginAs(role?: 'admin' | 'user'): Chainable<void>;

            /**
             * Custom command to ensure the app is ready for testing.
             * Waits for critical APIs to complete without re-visiting if already on app.
             * @example cy.waitForApp()
             */
            waitForApp(): Chainable<void>;
        }
    }
}

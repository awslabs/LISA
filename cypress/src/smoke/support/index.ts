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
    namespace Cypress {
        interface Chainable {
            /**
             * Custom command to log in a user via stubbed OAuth2/OIDC.
             * Should be wrapped in cy.session() for caching.
             * @param role - The role to simulate ('admin' or 'user')
             * @example cy.session('admin', () => cy.loginAs('admin'))
             */
            loginAs(role?: 'admin' | 'user'): Chainable<void>;
            
            /**
             * Custom command to setup API stubs for a given role.
             * Call this after cy.session() to re-establish intercepts.
             * @param role - The role to simulate ('admin' or 'user')
             * @example cy.setupStubs('admin')
             */
            setupStubs(role?: 'admin' | 'user'): Chainable<void>;
        }
    }
}

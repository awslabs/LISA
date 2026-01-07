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

import { AuthProviderProps } from 'react-oidc-context';

interface LisaOidcConfig {
    authority: string;
    client_id: string;
    redirect_uri: string;
    post_logout_redirect_uri: string;
    scope: string;
    response_type: string;
}

export const OidcConfig: AuthProviderProps & LisaOidcConfig = {
    authority: window.env.AUTHORITY,
    client_id: window.env.CLIENT_ID,
    redirect_uri: window.location.toString(),
    post_logout_redirect_uri: window.location.toString(),
    scope: 'openid profile email' + (window.env.CUSTOM_SCOPES ? ' ' + window.env.CUSTOM_SCOPES.join(' ') : ''),
    response_type: 'code',
};

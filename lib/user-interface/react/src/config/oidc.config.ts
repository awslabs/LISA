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

// Common configuration properties shared regardless of auth mode
 const commonConfig = {
   authority: window.env.AUTHORITY,
   redirect_uri: window.location.toString(),
   post_logout_redirect_uri: window.location.toString(),
 };
  
 // Midway-specific auth configuration
 const midwayConfig = {
   client_id: encodeURIComponent(`${window.location.host}`),
   scope: 'openid',
 };
  
 // Standard auth configuration
 const standardConfig = {
   client_id: window.env.CLIENT_ID,
   scope: 'openid profile email' + 
     (window.env.CUSTOM_SCOPES ? ' ' + window.env.CUSTOM_SCOPES.join(' ') : ''),
 };
  
 // Export the final configuration based on whether Midway auth is enabled
 export const OidcConfig: AuthProviderProps = {
   ...commonConfig,
   ...(window.env.MIDWAY_AUTH_ENABLED ? midwayConfig : standardConfig),
} as AuthProviderProps;

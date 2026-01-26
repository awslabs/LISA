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

import React from 'react';
import ReactDOM from 'react-dom/client';
import { Provider } from 'react-redux';
import './index.css';
import AppConfigured from './components/app-configured';

import '@cloudscape-design/global-styles/index.css';
import getStore from './config/store';
import { applyTheme } from '@cloudscape-design/components/theming';

// Conditionally apply custom theme if branding is enabled
if (window.env?.USE_CUSTOM_BRANDING) {
    const { brandTheme } = await import('./theme');
    applyTheme({ theme: brandTheme });
}

declare global {
    // eslint-disable-next-line @typescript-eslint/consistent-type-definitions
    interface Window {
        env: {
            AUTHORITY: string;
            CLIENT_ID: string;
            ADMIN_GROUP?: string;
            USER_GROUP?: string;
            API_GROUP?: string;
            JWT_GROUPS_PROP?: string;
            CUSTOM_SCOPES: string[];
            RESTAPI_URI: string;
            RESTAPI_VERSION: string;
            RAG_ENABLED: boolean;
            HOSTED_MCP_ENABLED: boolean;
            API_BASE_URL: string;
            USE_CUSTOM_BRANDING: boolean;
        };
        gitInfo?: {
            revisionTag?: string;
            gitHash?: string;
        };
    }
}

const store = getStore();

ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
        <Provider store={store}>
            <AppConfigured />
        </Provider>
    </React.StrictMode>,
);

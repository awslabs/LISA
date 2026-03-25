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

import '@cloudscape-design/global-styles/index.css';
import { applyTheme } from '@cloudscape-design/components/theming';
import { Theme } from '@cloudscape-design/components/theming';

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
            MCP_WORKBENCH_URI?: string;
            RESTAPI_VERSION: string;
            RAG_ENABLED: boolean;
            HOSTED_MCP_ENABLED: boolean;
            API_BASE_URL: string;
            USE_CUSTOM_BRANDING: boolean;
            CUSTOM_DISPLAY_NAME: string;
        };
        gitInfo?: {
            revisionTag?: string;
            gitHash?: string;
        };
    }
}

const baseUrl = import.meta.env.BASE_URL || '/';
const normalizedBase = baseUrl.endsWith('/') ? baseUrl : `${baseUrl}/`;

const loadRuntimeScript = async (scriptName: string): Promise<void> => {
    await new Promise<void>((resolve, reject) => {
        const script = document.createElement('script');
        script.src = `${normalizedBase}${scriptName}`;
        script.async = false;
        script.onload = () => resolve();
        script.onerror = () => reject(new Error(`Failed to load ${scriptName}`));
        document.head.appendChild(script);
    });
};

await loadRuntimeScript('env.js');
try {
    await loadRuntimeScript('git-info.js');
} catch {
    // git-info.js is generated at build time; not present in dev/CI
    // App runs fine without it — window.gitInfo remains undefined
}

const favicon = document.getElementById('favicon') as HTMLLinkElement | null;
if (favicon) {
    const brandingDir = window.env?.USE_CUSTOM_BRANDING ? 'custom' : 'base';
    favicon.href = `${normalizedBase}branding/${brandingDir}/favicon.ico`;
}

const pageTitle = document.getElementById('page-title');
if (pageTitle) {
    const displayName = window.env?.CUSTOM_DISPLAY_NAME || 'LISA';
    pageTitle.textContent = `${displayName} AI Chat Assistant`;
}

// Conditionally apply custom theme if branding is enabled
if (window.env?.USE_CUSTOM_BRANDING) {
    try {
        // Vite will only include files that actually exist
        const themeModules = import.meta.glob('./theme*.ts');

        // Try custom first, fall back to base
        const themeModule = themeModules['./theme-custom.ts']
            ? await themeModules['./theme-custom.ts']()
            : await themeModules['./theme.ts']();

        const { brandTheme } = themeModule as { brandTheme: Theme };
        applyTheme({ theme: brandTheme });
        console.log('Theme loaded:', themeModules['./theme-custom.ts'] ? 'custom' : 'base');
    } catch {
        console.warn('No theme file found, using Cloudscape default theme');
    }
}

const [{ default: AppConfigured }, { default: getStore }] = await Promise.all([
    import('./components/app-configured'),
    import('./config/store'),
]);

const store = getStore();

ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
        <Provider store={store}>
            <AppConfigured />
        </Provider>
    </React.StrictMode>,
);

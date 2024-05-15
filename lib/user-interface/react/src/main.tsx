import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import AppConfigured from './components/app-configured';

import '@cloudscape-design/global-styles/index.css';

declare global {
  // eslint-disable-next-line @typescript-eslint/consistent-type-definitions
  interface Window {
    env: {
      AUTHORITY: string;
      CLIENT_ID: string;
      RESTAPI_URI: string;
      RESTAPI_VERSION: string;
      RAG_ENABLED: boolean;
      API_BASE_URL?: string;
      SYSTEM_BANNER?: {
        text: string;
        backgroundColor: string;
        fontColor: string;
      };
    };
  }
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <AppConfigured />
  </React.StrictMode>,
);

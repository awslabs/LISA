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

import 'regenerator-runtime/runtime';
import { useState, useEffect } from 'react';
import { HashRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AppLayout } from '@cloudscape-design/components';
import Spinner from '@cloudscape-design/components/spinner';
import { useAuth } from 'react-oidc-context';

import Home from './pages/Home';
import Chatbot from './pages/Chatbot';
import Topbar from './components/Topbar';
import SystemBanner from './components/system-banner/system-banner';

const PrivateRoute = ({ children }) => {
  const auth = useAuth();
  if (auth.isAuthenticated) {
    return children;
  } else if (auth.isLoading) {
    return <Spinner />;
  } else {
    return <Navigate to={import.meta.env.BASE_URL} />;
  }
};

function App() {
  const [showTools, setShowTools] = useState(false);
  const [tools, setTools] = useState(null);

  useEffect(() => {
    if (tools) {
      setShowTools(true);
    } else {
      setShowTools(false);
    }
  }, [tools]);

  const baseHref = document?.querySelector('base')?.getAttribute('href')?.replace(/\/$/, '');
  return (
    <HashRouter basename={baseHref}>
      {window.env.SYSTEM_BANNER?.text && <SystemBanner position="TOP" />}
      <div
        id="h"
        style={{ position: 'sticky', top: 0, paddingTop: window.env.SYSTEM_BANNER?.text ? '1.5em' : 0, zIndex: 1002 }}
      >
        <Topbar />
      </div>
      <AppLayout
        headerSelector="#h"
        footerSelector="#f"
        navigationHide={true}
        toolsHide={!showTools}
        tools={tools}
        toolsWidth={500}
        content={
          <Routes>
            <Route index path="*" element={<Home setTools={setTools} />} />
            <Route
              path="chatbot"
              element={
                <PrivateRoute>
                  <Chatbot setTools={setTools} />
                </PrivateRoute>
              }
            />
            <Route
              path="chatbot/:sessionId"
              element={
                <PrivateRoute>
                  <Chatbot setTools={setTools} />
                </PrivateRoute>
              }
            />
          </Routes>
        }
      />
      {window.env.SYSTEM_BANNER?.text && <SystemBanner position="BOTTOM" />}
    </HashRouter>
  );
}

export default App;

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

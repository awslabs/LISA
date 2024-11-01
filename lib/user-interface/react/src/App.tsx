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
import { useAppSelector } from './config/store';
import { selectCurrentUserIsAdmin } from './shared/reducers/user.reducer';
import ModelManagement from './pages/ModelManagement';
import NotificationBanner from './shared/notification/notification';
import ConfirmationModal, { ConfirmationModalProps } from './shared/modal/confirmation-modal';
import Configuration from './pages/Configuration';
import { useGetConfigurationQuery } from './shared/reducers/configuration.reducer';

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

const AdminRoute = ({ children }) => {
    const auth = useAuth();
    const isUserAdmin = useAppSelector(selectCurrentUserIsAdmin);
    if (auth.isAuthenticated && isUserAdmin) {
        return children;
    } else if (auth.isLoading) {
        return <Spinner />;
    } else {
        return <Navigate to={import.meta.env.BASE_URL} />;
    }
};

function App () {
    const [showTools, setShowTools] = useState(false);
    const [tools, setTools] = useState(null);
    const confirmationModal: ConfirmationModalProps = useAppSelector((state) => state.modal.confirmationModal);
    const { data: config } = useGetConfigurationQuery("global", {refetchOnMountOrArgChange: 5});

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
            {config && config[0]?.configuration.systemBanner.isEnabled && <SystemBanner position='TOP' />}
            <div
                id='h'
                style={{ position: 'sticky', top: 0, paddingTop: config && config[0]?.configuration.systemBanner.isEnabled ? '1.5em' : 0, zIndex: 1002 }}
            >
                <Topbar />
            </div>
            <AppLayout
                headerSelector='#h'
                footerSelector='#f'
                navigationHide={true}
                toolsHide={!showTools}
                notifications={<NotificationBanner />}
                stickyNotifications={true}
                tools={tools}
                toolsWidth={500}
                content={
                    <Routes>
                        <Route index path='*' element={<Home setTools={setTools} />} />
                        <Route
                            path='chatbot'
                            element={
                                <PrivateRoute>
                                    <Chatbot setTools={setTools} />
                                </PrivateRoute>
                            }
                        />
                        <Route
                            path='chatbot/:sessionId'
                            element={
                                <PrivateRoute>
                                    <Chatbot setTools={setTools} />
                                </PrivateRoute>
                            }
                        />
                        <Route
                            path='model-management'
                            element={
                                <AdminRoute>
                                    <ModelManagement setTools={setTools} />
                                </AdminRoute>
                            }
                        />
                        <Route
                            path='configuration'
                            element={
                                <AdminRoute>
                                    <Configuration setTools={setTools} />
                                </AdminRoute>
                            }
                        />
                    </Routes>
                }
            />
            {confirmationModal && <ConfirmationModal {...confirmationModal} />}
            {config && config[0]?.configuration.systemBanner.isEnabled && <SystemBanner position='BOTTOM' />}
        </HashRouter>
    );
}

export default App;

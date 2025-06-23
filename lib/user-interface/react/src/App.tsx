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
import { ReactElement, useEffect, useState } from 'react';
import { HashRouter, Navigate, Route, Routes } from 'react-router-dom';
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
import { useLazyGetConfigurationQuery } from './shared/reducers/configuration.reducer';
import { IConfiguration } from './shared/model/configuration.model';
import DocumentLibrary from './pages/DocumentLibrary';
import RepositoryLibrary from './pages/RepositoryLibrary';
import { Breadcrumbs } from './shared/breadcrumb/breadcrumbs';
import BreadcrumbsDefaultChangeListener from './shared/breadcrumb/breadcrumbs-change-listener';
import PromptTemplatesLibrary from './pages/PromptTemplatesLibrary';
import { ConfigurationContext } from './shared/configuration.provider';
import McpServers from '@/pages/Mcp';


export type RouteProps = {
    children: ReactElement[] | ReactElement;
    showConfig?: string;
    configs?: IConfiguration
};

const PrivateRoute = ({ children, showConfig, configs }: RouteProps) => {

    const auth = useAuth();
    if (auth.isAuthenticated) {
        if (showConfig && configs?.configuration.enabledComponents[showConfig] === false) {
            return <Navigate to={import.meta.env.BASE_URL} />;
        }
        return children;
    } else if (auth.isLoading) {
        return <Spinner />;
    } else {
        return <Navigate to={import.meta.env.BASE_URL} />;
    }
};

const AdminRoute = ({ children }: RouteProps) => {
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
    const [showNavigation, setShowNavigation] = useState(false);
    const [nav, setNav] = useState(null);
    const confirmationModal: ConfirmationModalProps = useAppSelector((state) => state.modal.confirmationModal);
    const auth = useAuth();
    const [ getConfigurationQuery, {data: fullConfig} ] = useLazyGetConfigurationQuery();
    const config = fullConfig?.[0];

    useEffect(() => {
        if (!auth.isLoading && auth.isAuthenticated && auth.user) {
            getConfigurationQuery('global');
        }
    }, [auth, getConfigurationQuery]);

    useEffect(() => {
        if (nav) {
            setShowNavigation(true);
        } else {
            setShowNavigation(false);
        }
    }, [nav]);

    const baseHref = document?.querySelector('base')?.getAttribute('href')?.replace(/\/$/, '');
    return (
        <HashRouter basename={baseHref}>
            <ConfigurationContext.Provider value={config}>
                {config?.configuration.systemBanner.isEnabled && <SystemBanner position='TOP' />}
                <div
                    id='h'
                    style={{ position: 'sticky', top: 0, paddingTop: config?.configuration.systemBanner.isEnabled ? '1.5em' : 0, zIndex: 1002 }}
                >
                    <Topbar configs={config} />
                </div>
                <BreadcrumbsDefaultChangeListener />
                <AppLayout
                    headerSelector='#h'
                    footerSelector='#f'
                    navigationHide={!showNavigation}
                    breadcrumbs={<Breadcrumbs />}
                    toolsHide={true}
                    notifications={<NotificationBanner />}
                    stickyNotifications={true}
                    navigation={nav}
                    navigationWidth={450}
                    content={
                        <Routes>
                            <Route index path='*' element={<Home setNav={setNav} />} />
                            <Route
                                path='ai-assistant'
                                element={
                                    <PrivateRoute>
                                        <Chatbot setNav={setNav} />
                                    </PrivateRoute>
                                }
                            />
                            <Route
                                path='ai-assistant/:sessionId'
                                element={
                                    <PrivateRoute>
                                        <Chatbot setNav={setNav} />
                                    </PrivateRoute>
                                }
                            />
                            <Route
                                path='model-management'
                                element={
                                    <AdminRoute>
                                        <ModelManagement setNav={setNav} />
                                    </AdminRoute>
                                }
                            />
                            <Route
                                path='document-library'
                                element={
                                    <PrivateRoute showConfig='showRagLibrary' configs={config}>
                                        <RepositoryLibrary setNav={setNav} />
                                    </PrivateRoute>
                                }
                            />
                            <Route
                                path='document-library/:repoId'
                                element={
                                    <PrivateRoute showConfig='showRagLibrary' configs={config}>
                                        <DocumentLibrary setNav={setNav} />
                                    </PrivateRoute>
                                }
                            />
                            <Route
                                path='prompt-templates/*'
                                element={
                                    <PrivateRoute showConfig='showPromptTemplates' configs={config}>
                                        <PromptTemplatesLibrary setNav={setNav} />
                                    </PrivateRoute>
                                }
                            />
                            <Route
                                path='configuration'
                                element={
                                    <AdminRoute>
                                        <Configuration setNav={setNav} />
                                    </AdminRoute>
                                }
                            />
                            <Route
                                path='mcp-servers/*'
                                element={
                                    <PrivateRoute showConfig='showMcpServers' configs={config}>
                                        <McpServers setNav={setNav} />
                                    </PrivateRoute>
                                }
                            />
                        </Routes>
                    }
                />
                {confirmationModal && <ConfirmationModal {...confirmationModal} />}
                {config?.configuration.systemBanner.isEnabled && <SystemBanner position='BOTTOM' />}
            </ConfigurationContext.Provider>
        </HashRouter>
    );
}

export default App;

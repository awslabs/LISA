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
import { Navigate, Route, Routes } from 'react-router-dom';
import { AppLayout } from '@cloudscape-design/components';
import Spinner from '@cloudscape-design/components/spinner';
import { useAuth } from 'react-oidc-context';

import Home from './pages/Home';
import Chatbot from './pages/Chatbot';
import Topbar from './components/Topbar';
import SystemBanner from './components/system-banner/system-banner';
import { useAppSelector } from './config/store';
import { selectCurrentUserIsAdmin, selectCurrentUserIsUser, selectCurrentUserIsApiUser } from './shared/reducers/user.reducer';
import ModelManagement from './pages/ModelManagement';
import McpManagement from './pages/McpManagement';
import ModelLibrary from './pages/ModelLibrary';
import RepositoryManagement from './pages/RepositoryManagement';
import ApiTokenManagement from './pages/ApiTokenManagement';
import UserApiToken from './pages/UserApiToken';
import NotificationBanner from './shared/notification/notification';
import ConfirmationModal, { ConfirmationModalProps } from './shared/modal/confirmation-modal';
import Configuration from './pages/Configuration';
import { useGetConfigurationQuery } from './shared/reducers/configuration.reducer';
import { IConfiguration } from './shared/model/configuration.model';
import DocumentLibrary from './pages/DocumentLibrary';
import CollectionLibrary from './pages/CollectionLibrary';
import { Breadcrumbs } from './shared/breadcrumb/breadcrumbs';
import BreadcrumbsDefaultChangeListener from './shared/breadcrumb/breadcrumbs-change-listener';
import PromptTemplatesLibrary from './pages/PromptTemplatesLibrary';
import { ConfigurationContext } from './shared/configuration.provider';
import McpServers from '@/pages/Mcp';
import ModelComparisonPage from './pages/ModelComparison';
import McpWorkbench from './pages/McpWorkbench';
import ColorSchemeContext from './shared/color-scheme.provider';
import { applyMode, Mode } from '@cloudscape-design/global-styles';


export type RouteProps = {
    children: ReactElement[] | ReactElement;
    showConfig?: string;
    configs?: IConfiguration
};

const PrivateRoute = ({ children }: RouteProps) => {

    const auth = useAuth();
    const isUserAdmin = useAppSelector(selectCurrentUserIsAdmin);
    const isUser = useAppSelector(selectCurrentUserIsUser);

    if (auth.isAuthenticated && (isUserAdmin || isUser)) {
        return children;
    } else if (auth.isLoading) {
        return <Spinner />;
    } else if (auth.isAuthenticated && !isUserAdmin && !isUser) {
        return (
            <div style={{ padding: '20px', textAlign: 'center' }}>
                <h2>Access Denied</h2>
                <p>You do not have permission to access this application. Please contact your administrator.</p>
            </div>
        );
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

const ApiUserRoute = ({ children }: RouteProps) => {
    const auth = useAuth();
    const isUserAdmin = useAppSelector(selectCurrentUserIsAdmin);
    const isApiUser = useAppSelector(selectCurrentUserIsApiUser);
    if (auth.isAuthenticated && (isUserAdmin || isApiUser)) {
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
    const { data: fullConfig, isLoading: configLoading } = useGetConfigurationQuery('global', {
        skip: !auth.isAuthenticated || auth.isLoading || !auth.user
    });
    const config = fullConfig?.[0];

    const [colorScheme, setColorScheme] = useState(() => {
        // Check to see if Media-Queries are supported
        if (window.matchMedia) {
            // Check if the dark-mode Media-Query matches
            if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
                // Dark
                return Mode.Dark;
            }
        }

        return Mode.Light;
    });

    useEffect(() => {
        applyMode(colorScheme);
    }, [colorScheme]);

    useEffect(() => {
        if (nav) {
            setShowNavigation(true);
        } else {
            setShowNavigation(false);
        }
    }, [nav]);

    return (
        <ColorSchemeContext.Provider value={{ colorScheme, setColorScheme }}>
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
                    navigationWidth={300}
                    content={
                        <Routes>
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
                            {window.env.HOSTED_MCP_ENABLED && <Route
                                path='mcp-management'
                                element={
                                    <AdminRoute>
                                        <McpManagement setNav={setNav} />
                                    </AdminRoute>
                                }
                            />}
                            <Route
                                path='repository-management'
                                element={
                                    <AdminRoute>
                                        <RepositoryManagement setNav={setNav} />
                                    </AdminRoute>
                                }
                            />
                            <Route
                                path='api-token-management'
                                element={
                                    <AdminRoute>
                                        <ApiTokenManagement setNav={setNav} />
                                    </AdminRoute>
                                }
                            />
                            {config?.configuration?.enabledComponents?.enableUserApiTokens && <Route
                                path='user-api-token'
                                element={
                                    <ApiUserRoute showConfig='enableUserApiTokens' configs={config}>
                                        <UserApiToken setNav={setNav} />
                                    </ApiUserRoute>
                                }
                            />}
                            {config?.configuration?.enabledComponents?.modelLibrary && <Route
                                path='model-library'
                                element={
                                    <PrivateRoute showConfig='modelLibrary' configs={config}>
                                        <ModelLibrary setNav={setNav} />
                                    </PrivateRoute>
                                }
                            />}
                            {config?.configuration?.enabledComponents?.showRagLibrary &&
                                <>
                                    <Route
                                        path='document-library'
                                        element={
                                            <PrivateRoute showConfig='showRagLibrary' configs={config}>
                                                <CollectionLibrary setNav={setNav} />
                                            </PrivateRoute>
                                        }
                                    />
                                    <Route
                                        path='document-library/:repoId/:collectionId?'
                                        element={
                                            <PrivateRoute showConfig='showRagLibrary' configs={config}>
                                                <DocumentLibrary setNav={setNav} />
                                            </PrivateRoute>
                                        }
                                    />
                                </>}
                            {config?.configuration?.enabledComponents?.showPromptTemplateLibrary && <Route
                                path='prompt-templates/*'
                                element={
                                    <PrivateRoute showConfig='showPromptTemplates' configs={config}>
                                        <PromptTemplatesLibrary setNav={setNav} />
                                    </PrivateRoute>
                                }
                            />}
                            <Route
                                path='configuration'
                                element={
                                    <AdminRoute>
                                        <Configuration setNav={setNav} />
                                    </AdminRoute>
                                }
                            />
                            {config?.configuration?.enabledComponents?.mcpConnections && <Route
                                path='mcp-connections/*'
                                element={
                                    <PrivateRoute showConfig='showMcpServers' configs={config}>
                                        <McpServers setNav={setNav} />
                                    </PrivateRoute>
                                }
                            />}
                            {config?.configuration?.enabledComponents?.showMcpWorkbench &&
                                <Route
                                    path='mcp-workbench/*'
                                    element={
                                        <McpWorkbench setNav={setNav} />
                                    }
                                />
                            }
                            {config?.configuration?.enabledComponents?.enableModelComparisonUtility && <Route
                                path='model-comparison'
                                element={
                                    <PrivateRoute>
                                        <ModelComparisonPage />
                                    </PrivateRoute>
                                }
                            />
                            }
                            <Route path='*' element={
                                configLoading ?
                                    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
                                        <Spinner size='large' />
                                        <span style={{ marginLeft: '10px' }}>Loading configuration...</span>
                                    </div>
                                    :
                                    <Home setNav={setNav} />
                            } />
                        </Routes>
                    }
                />
                {confirmationModal && <ConfirmationModal {...confirmationModal} />}
                {config?.configuration.systemBanner.isEnabled && <SystemBanner position='BOTTOM' />}
            </ConfigurationContext.Provider>
        </ColorSchemeContext.Provider>
    );
}

export default App;

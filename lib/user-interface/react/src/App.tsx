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
import { lazy, ReactElement, Suspense, useEffect, useState } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { AppLayout, Box } from '@cloudscape-design/components';
import Spinner from '@cloudscape-design/components/spinner';
import { useAuth } from './auth/useAuth';

import Topbar from './components/Topbar';
import SystemBanner from './components/system-banner/system-banner';
import { useAppSelector } from './config/store';
import { selectCurrentUserIsAdmin, selectCurrentUserIsUser, selectCurrentUserIsApiUser, selectCurrentUserIsRagAdmin } from './shared/reducers/user.reducer';
import NotificationBanner from './shared/notification/notification';
import ConfirmationModal, { ConfirmationModalProps } from './shared/modal/confirmation-modal';
import { useGetConfigurationQuery } from './shared/reducers/configuration.reducer';
import { IConfiguration } from './shared/model/configuration.model';
import { Breadcrumbs } from './shared/breadcrumb/breadcrumbs';
import BreadcrumbsDefaultChangeListener from './shared/breadcrumb/breadcrumbs-change-listener';
import { ConfigurationContext } from './shared/configuration.provider';
import ColorSchemeContext from './shared/color-scheme.provider';
import { applyMode, Mode } from '@cloudscape-design/global-styles';
import { useAnnouncementNotifier } from './shared/hooks/useAnnouncementNotifier';

const Home = lazy(() => import('./pages/Home'));
const Chatbot = lazy(() => import('./pages/Chatbot'));
const ModelManagement = lazy(() => import('./pages/ModelManagement'));
const McpManagement = lazy(() => import('./pages/McpManagement'));
const ModelLibrary = lazy(() => import('./pages/ModelLibrary'));
const RepositoryManagement = lazy(() => import('./pages/RepositoryManagement'));
const ApiTokenManagement = lazy(() => import('./pages/ApiTokenManagement'));
const UserApiToken = lazy(() => import('./pages/UserApiToken'));
const Configuration = lazy(() => import('./pages/Configuration'));
const DocumentLibrary = lazy(() => import('./pages/DocumentLibrary'));
const CollectionLibrary = lazy(() => import('./pages/CollectionLibrary'));
const PromptTemplatesLibrary = lazy(() => import('./pages/PromptTemplatesLibrary'));
const McpServers = lazy(() => import('@/pages/Mcp'));
const ModelComparisonPage = lazy(() => import('./pages/ModelComparison'));
const McpWorkbench = lazy(() => import('./pages/McpWorkbench'));
const ChatAssistantStacks = lazy(() => import('./pages/ChatAssistantStacks'));
const BedrockAgentManagement = lazy(() => import('./pages/BedrockAgentManagement'));

export type RouteProps = {
    children: ReactElement[] | ReactElement;
    showConfig?: string;
    configs?: IConfiguration
};

const PrivateRoute = ({ children }: RouteProps) => {

    const auth = useAuth();
    const isUserAdmin = useAppSelector(selectCurrentUserIsAdmin);
    const isUser = useAppSelector(selectCurrentUserIsUser);
    const isRagAdmin = useAppSelector(selectCurrentUserIsRagAdmin);

    if (auth.isAuthenticated && (isUserAdmin || isUser || isRagAdmin)) {
        return children;
    } else if (auth.isLoading) {
        return <Spinner />;
    } else if (auth.isAuthenticated && !isUserAdmin && !isUser && !isRagAdmin) {
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

const RagAdminRoute = ({ children }: RouteProps) => {
    const auth = useAuth();
    const isUserAdmin = useAppSelector(selectCurrentUserIsAdmin);
    const isRagAdmin = useAppSelector(selectCurrentUserIsRagAdmin);
    if (auth.isAuthenticated && (isUserAdmin || isRagAdmin)) {
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

const RouteLoadingFallback = () => (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <Spinner size='large' />
        <Box margin={{ left: 's' }}>Loading page...</Box>
    </div>
);

function App () {
    const [nav, setNav] = useState(null);
    const confirmationModal: ConfirmationModalProps = useAppSelector((state) => state.modal.confirmationModal);
    const auth = useAuth();
    const { data: fullConfig, isLoading: configLoading } = useGetConfigurationQuery('global', {
        skip: !auth.isAuthenticated || auth.isLoading || !auth.user
    });
    const config = fullConfig?.[0];

    useAnnouncementNotifier(config);

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

    const showNavigation = !!nav;

    const enabledComponents = config?.configuration?.enabledComponents;
    const showAgenticConnectionsPage =
        Boolean(enabledComponents?.mcpConnections) || Boolean(enabledComponents?.bedrockAgents);

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
                        <Suspense fallback={<RouteLoadingFallback />}>
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
                                {window.env.RAG_ENABLED && <Route
                                    path='repository-management'
                                    element={
                                        <RagAdminRoute>
                                            <RepositoryManagement setNav={setNav} />
                                        </RagAdminRoute>
                                    }
                                />}
                                <Route
                                    path='api-token-management'
                                    element={
                                        <AdminRoute>
                                            <ApiTokenManagement setNav={setNav} />
                                        </AdminRoute>
                                    }
                                />
                                <Route
                                    path='mcp-workbench'
                                    element={
                                        config?.configuration?.enabledComponents?.showMcpWorkbench ? (
                                            <AdminRoute>
                                                <McpWorkbench setNav={setNav} />
                                            </AdminRoute>
                                        ) : (
                                            <Navigate to={import.meta.env.BASE_URL} replace />
                                        )
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
                                {showAgenticConnectionsPage && <Route
                                    path='mcp-connections/*'
                                    element={
                                        <PrivateRoute showConfig='showMcpServers' configs={config}>
                                            <McpServers setNav={setNav} />
                                        </PrivateRoute>
                                    }
                                />}
                                <Route
                                    path='bedrock-agent-management'
                                    element={
                                        config?.configuration?.enabledComponents?.bedrockAgents ? (
                                            <AdminRoute>
                                                <BedrockAgentManagement setNav={setNav} />
                                            </AdminRoute>
                                        ) : (
                                            <Navigate to={import.meta.env.BASE_URL} replace />
                                        )
                                    }
                                />
                                {config?.configuration?.enabledComponents?.enableModelComparisonUtility && <Route
                                    path='model-comparison'
                                    element={
                                        <PrivateRoute>
                                            <ModelComparisonPage />
                                        </PrivateRoute>
                                    }
                                />
                                }
                                {config?.configuration?.enabledComponents?.chatAssistantStacks && <Route
                                    path='chat-assistant-stacks'
                                    element={
                                        <AdminRoute>
                                            <ChatAssistantStacks setNav={setNav} />
                                        </AdminRoute>
                                    }
                                />}
                                <Route path='*' element={
                                    configLoading ?
                                        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
                                            <Spinner size='large' />
                                            <Box margin={{ left: 's' }}>Loading configuration...</Box>
                                        </div>
                                        :
                                        <Home setNav={setNav} />
                                } />
                            </Routes>
                        </Suspense>
                    }
                />
                {confirmationModal && <ConfirmationModal {...confirmationModal} />}
                {config?.configuration.systemBanner.isEnabled && <SystemBanner position='BOTTOM' />}
            </ConfigurationContext.Provider>
        </ColorSchemeContext.Provider>
    );
}

export default App;

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

/**
 * Import factories are kept as named constants so the exact same function
 * reference is used for both `React.lazy` and the idle-time prefetch pass
 * below. Rollup/Vite de-duplicates dynamic imports by string literal, so
 * calling the factory a second time after prefetch is a cache hit and
 * subsequent route navigation is instant.
 */
const importers = {
    Home: () => import('./pages/Home'),
    Chatbot: () => import('./pages/Chatbot'),
    ModelManagement: () => import('./pages/ModelManagement'),
    McpManagement: () => import('./pages/McpManagement'),
    ModelLibrary: () => import('./pages/ModelLibrary'),
    RepositoryManagement: () => import('./pages/RepositoryManagement'),
    ApiTokenManagement: () => import('./pages/ApiTokenManagement'),
    UserApiToken: () => import('./pages/UserApiToken'),
    Configuration: () => import('./pages/Configuration'),
    DocumentLibrary: () => import('./pages/DocumentLibrary'),
    CollectionLibrary: () => import('./pages/CollectionLibrary'),
    PromptTemplatesLibrary: () => import('./pages/PromptTemplatesLibrary'),
    McpServers: () => import('@/pages/Mcp'),
    ModelComparisonPage: () => import('./pages/ModelComparison'),
    McpWorkbench: () => import('./pages/McpWorkbench'),
    ChatAssistantStacks: () => import('./pages/ChatAssistantStacks'),
    BedrockAgentManagement: () => import('./pages/BedrockAgentManagement'),
} as const;

const Home = lazy(importers.Home);
const Chatbot = lazy(importers.Chatbot);
const ModelManagement = lazy(importers.ModelManagement);
const McpManagement = lazy(importers.McpManagement);
const ModelLibrary = lazy(importers.ModelLibrary);
const RepositoryManagement = lazy(importers.RepositoryManagement);
const ApiTokenManagement = lazy(importers.ApiTokenManagement);
const UserApiToken = lazy(importers.UserApiToken);
const Configuration = lazy(importers.Configuration);
const DocumentLibrary = lazy(importers.DocumentLibrary);
const CollectionLibrary = lazy(importers.CollectionLibrary);
const PromptTemplatesLibrary = lazy(importers.PromptTemplatesLibrary);
const McpServers = lazy(importers.McpServers);
const ModelComparisonPage = lazy(importers.ModelComparisonPage);
const McpWorkbench = lazy(importers.McpWorkbench);
const ChatAssistantStacks = lazy(importers.ChatAssistantStacks);
const BedrockAgentManagement = lazy(importers.BedrockAgentManagement);

/**
 * Schedule a callback for when the browser is idle, falling back to a
 * small timeout on browsers (e.g. Safari) without `requestIdleCallback`.
 */
const scheduleIdle = (callback: () => void, timeout = 2000): number => {
    const w = window as typeof window & {
        requestIdleCallback?: (cb: () => void, opts?: { timeout: number }) => number;
    };
    if (typeof w.requestIdleCallback === 'function') {
        return w.requestIdleCallback(callback, { timeout });
    }
    return window.setTimeout(callback, timeout);
};

/**
 * Warm the Vite/Rollup dynamic-import cache for every routable page while
 * the browser is idle. Triggered after authentication + configuration load,
 * so that clicking any top-nav item after the initial load feels instant.
 *
 * Ordered by expected user priority: the chatbot is the default landing
 * surface, then the library pages an ordinary user typically visits next,
 * then admin pages last.
 */
const prefetchRouteChunks = (config?: IConfiguration, isAdmin?: boolean): void => {
    const enabled = config?.configuration?.enabledComponents;
    const plan: Array<() => Promise<unknown>> = [
        importers.Chatbot,
        importers.Home,
    ];

    if (enabled?.modelLibrary) plan.push(importers.ModelLibrary);
    if (enabled?.showRagLibrary) plan.push(importers.CollectionLibrary, importers.DocumentLibrary);
    if (enabled?.showPromptTemplateLibrary) plan.push(importers.PromptTemplatesLibrary);
    if (enabled?.mcpConnections || enabled?.bedrockAgents) plan.push(importers.McpServers);
    if (enabled?.enableUserApiTokens) plan.push(importers.UserApiToken);
    if (enabled?.enableModelComparisonUtility) plan.push(importers.ModelComparisonPage);

    if (isAdmin) {
        plan.push(
            importers.Configuration,
            importers.ModelManagement,
            importers.ApiTokenManagement,
        );
        if (window.env.RAG_ENABLED) plan.push(importers.RepositoryManagement);
        if (window.env.HOSTED_MCP_ENABLED) plan.push(importers.McpManagement);
        if (enabled?.showMcpWorkbench) plan.push(importers.McpWorkbench);
        if (enabled?.bedrockAgents) plan.push(importers.BedrockAgentManagement);
        if (enabled?.chatAssistantStacks) plan.push(importers.ChatAssistantStacks);
    }

    // Fetch chunks one at a time during idle windows so prefetching never
    // competes with user-initiated requests or the main thread.
    let index = 0;
    const pump = () => {
        if (index >= plan.length) return;
        const next = plan[index++];
        scheduleIdle(() => {
            next().catch(() => { /* Swallow prefetch failures; the real navigation will surface errors. */ }).finally(pump);
        });
    };
    pump();
};

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

/**
 * Rendered while a not-yet-cached route chunk is downloading. Kept deliberately
 * unobtrusive: route chunks are prefetched during idle time (see
 * `prefetchRouteChunks`), so in practice this fallback only appears briefly on
 * the very first navigation after login. A small inline indicator preserves
 * layout context and is less jarring than blanking the content area.
 */
const RouteLoadingFallback = () => (
    <Box textAlign='center' padding={{ vertical: 'xl' }}>
        <Spinner size='normal' />
        <Box variant='small' color='text-status-inactive' padding={{ top: 'xs' }}>
            Loading…
        </Box>
    </Box>
);

function App () {
    const [nav, setNav] = useState(null);
    const confirmationModal: ConfirmationModalProps = useAppSelector((state) => state.modal.confirmationModal);
    const auth = useAuth();
    const isAdmin = useAppSelector(selectCurrentUserIsAdmin);
    const { data: fullConfig, isLoading: configLoading } = useGetConfigurationQuery('global', {
        skip: !auth.isAuthenticated || auth.isLoading || !auth.user
    });
    const config = fullConfig?.[0];

    useAnnouncementNotifier(config);

    // Prefetch every route chunk the signed-in user can reach, once, during
    // idle time. Turns subsequent route navigation into a cache hit.
    const [prefetchTriggered, setPrefetchTriggered] = useState(false);
    useEffect(() => {
        if (prefetchTriggered) return;
        if (!auth.isAuthenticated || !config) return;
        setPrefetchTriggered(true);
        prefetchRouteChunks(config, isAdmin);
    }, [auth.isAuthenticated, config, isAdmin, prefetchTriggered]);

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

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

// es-lint-disable
import { AuthProvider } from 'react-oidc-context';
import { HashRouter, Routes, Route } from 'react-router-dom';
import App from '../App';
import { onMcpAuthorization } from 'use-mcp';
import { useEffect, useState } from 'react';
import Spinner from '@cloudscape-design/components/spinner';

import { OidcConfig } from '../config/oidc.config';
import { User, UserProfile } from 'oidc-client-ts';
import { useAppDispatch } from '../config/store';
import { updateUserState } from '../shared/reducers/user.reducer';
import { useAuth } from '../auth/useAuth';

function UserStateSync () {
    const dispatch = useAppDispatch();
    const auth = useAuth();

    useEffect(() => {
        if (auth.user) {
            const userGroups = getGroups(auth.user.profile);
            dispatch(updateUserState({
                name: auth.user.profile.name,
                preferred_username: auth.user.profile.preferred_username,
                email: auth.user.profile.email,
                groups: userGroups,
                isAdmin: userGroups ? isAdmin(userGroups) : false,
                isUser: window.env.USER_GROUP ? userGroups && isUser(userGroups) : true,
                isApiUser: window.env.API_GROUP ? userGroups && isApiUser(userGroups) : false,
                isRagAdmin: userGroups ? isRagAdmin(userGroups) : false,
            }));
        }
    }, [auth.user, dispatch]);

    return null;
}

// Pure synchronous validation of the OAuth callback URL and localStorage
// state. Runs before delegating to use-mcp so unsanitized query params can
// never reach innerHTML (XSS mitigation — covers `error`/`error_description`
// and an unknown-`state` vector).
//
// NOTE: The localStorage key format `mcp:auth:state_${state}` is coupled to
// the use-mcp library's internal storage convention. If the library changes
// its key naming this check may incorrectly block legitimate callbacks. The
// patched escapeHtml in patches/use-mcp+0.0.21.patch is the primary XSS fix;
// this pre-validation is a defense-in-depth layer.
function validateOAuthCallback (): string | null {
    const queryParams = new URLSearchParams(window.location.search);
    const error = queryParams.get('error');
    if (error) {
        const errorDescription = queryParams.get('error_description');
        const safeMessage = `OAuth error: ${error} - ${errorDescription || 'No description provided.'}`;
        console.error('[OAuthCallback]', safeMessage);
        return safeMessage;
    }
    const code = queryParams.get('code');
    const state = queryParams.get('state');
    if (code && state) {
        const stateKey = `mcp:auth:state_${state}`;
        if (!localStorage.getItem(stateKey)) {
            console.error('[OAuthCallback] Invalid or expired state parameter');
            return 'Invalid or expired OAuth state parameter. No matching state found in storage.';
        }
    }
    return null;
}

function OAuthCallback () {
    // Synchronous validation happens during render via the lazy state
    // initializer — no cascading effect, no setState-in-effect.
    const [oauthError, setOauthError] = useState<string | null>(validateOAuthCallback);

    useEffect(() => {
        // Skip the async authorization flow if URL/state validation
        // already produced an error during the initial render.
        if (validateOAuthCallback()) return;
        // setState inside the Promise rejection callback runs after the
        // async boundary, which is permitted by react-hooks/set-state-in-effect.
        onMcpAuthorization().catch((err) => {
            console.error('OAuth callback error:', err);
            setOauthError(err instanceof Error ? err.message : String(err));
        });
    }, []);

    if (oauthError) {
        return (
            <div style={{ fontFamily: 'sans-serif', padding: '20px' }}>
                <h1>Authentication Error</h1>
                <p style={{ color: 'red', backgroundColor: '#ffebeb', border: '1px solid red', padding: '10px', borderRadius: '4px' }}>
                    {oauthError}
                </p>
                <p>You can close this window or try again.</p>
            </div>
        );
    }

    return (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
            <Spinner size='large' />
            <span style={{ marginLeft: '10px' }}>Processing OAuth callback...</span>
        </div>
    );
}

const getGroups = (oidcUserProfile: UserProfile): any => {
    if (window.env.JWT_GROUPS_PROP) {
        const props: string[] = window.env.JWT_GROUPS_PROP.split('.');
        let currentNode: any = oidcUserProfile;
        let found = true;
        props.forEach((prop) => {
            if (prop in currentNode) {
                currentNode = currentNode[prop];
            } else {
                found = false;
            }
        });
        return found ? currentNode : undefined;
    } else {
        return undefined;
    }
};

const isAdmin = (userGroups: any): boolean => {
    return window.env.ADMIN_GROUP ? userGroups.includes(window.env.ADMIN_GROUP) : false;
};

const isUser = (userGroups: any): boolean => {
    return window.env.USER_GROUP ? userGroups.includes(window.env.USER_GROUP) : false;
};

const isApiUser = (userGroups: any): boolean => {
    return window.env.API_GROUP ? userGroups.includes(window.env.API_GROUP) : false;
};

const isRagAdmin = (userGroups: any): boolean => {
    return window.env.RAG_ADMIN_GROUP ? userGroups.includes(window.env.RAG_ADMIN_GROUP) : false;
};

function AppConfigured () {
    const dispatch = useAppDispatch();
    const [oidcUser, setOidcUser] = useState<User | void>();

    useEffect(() => {
        if (oidcUser) {
            const userGroups = getGroups(oidcUser.profile);
            dispatch(
                updateUserState({
                    name: oidcUser.profile.name,
                    preferred_username: oidcUser.profile.preferred_username,
                    email: oidcUser.profile.email,
                    groups: userGroups,
                    isAdmin: userGroups ? isAdmin(userGroups) : false,
                    isUser: window.env.USER_GROUP ? userGroups && isUser(userGroups) : true,
                    isApiUser: window.env.API_GROUP ? userGroups && isApiUser(userGroups) : false,
                    isRagAdmin: userGroups ? isRagAdmin(userGroups) : false,
                }),
            );
        }
    }, [dispatch, oidcUser]);

    const baseHref = document?.querySelector('base')?.getAttribute('href')?.replace(/\/$/, '');

    // Check if we're on an OAuth callback URL (without hash)
    const isOAuthCallback = window.location.pathname.includes( '/oauth/callback');

    if (isOAuthCallback) {
        return <OAuthCallback />;
    }

    return (
        <HashRouter basename={baseHref}>
            <Routes>
                <Route path='/oauth/callback' element={<OAuthCallback />} />
                <Route path='oauth/callback' element={<OAuthCallback />} />
                <Route path='*' element={
                    <AuthProvider
                        {...OidcConfig}
                        onSigninCallback={async (user: User | void) => {
                            const userGroups = user ? getGroups(user.profile) : undefined;
                            const hasAccess = userGroups && (isUser(userGroups) || isRagAdmin(userGroups) || isAdmin(userGroups));
                            if ((window.env.USER_GROUP && user && hasAccess) || !window.env.USER_GROUP) {
                                window.history.replaceState({}, document.title, `${window.location.pathname}${window.location.hash}`);
                                setOidcUser(user);
                            } else {
                                // Clear OIDC session storage to force re-authentication
                                const oidcStorageKey = `oidc.user:${window.env.AUTHORITY}:${window.env.CLIENT_ID}`;
                                sessionStorage.removeItem(oidcStorageKey);
                                window.location.href = window.location.origin;
                            }
                        }}
                    >
                        <UserStateSync />
                        <App />
                    </AuthProvider>
                } />
            </Routes>
        </HashRouter>
    );
}

export default AppConfigured;

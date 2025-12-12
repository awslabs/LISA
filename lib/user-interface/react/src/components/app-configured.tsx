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
import { AuthProvider, useAuth } from 'react-oidc-context';
import { HashRouter, Routes, Route } from 'react-router-dom';
import App from '../App';
import { onMcpAuthorization } from 'use-mcp';
import { useCallback, useEffect, useState } from 'react';
import Spinner from '@cloudscape-design/components/spinner';

import { OidcConfig } from '../config/oidc.config';
import { User, UserProfile } from 'oidc-client-ts';
import { purgeStore, useAppDispatch } from '../config/store';
import { updateUserState } from '../shared/reducers/user.reducer';

function OAuthCallback () {
    useEffect(() => {
        // Handle MCP OAuth authorization
        try {
            onMcpAuthorization();
        } catch (error) {
            console.error('OAuth callback error:', error);
        }
    }, []);

    return (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
            <Spinner size='large' />
            <span style={{ marginLeft: '10px' }}>Processing OAuth callback...</span>
        </div>
    );
}

function AppConfigured () {
    const dispatch = useAppDispatch();
    const [oidcUser, setOidcUser] = useState<User | void>();
    const auth = useAuth();

    // Define helper functions before they are used
    const getGroups = useCallback((oidcUserProfile: UserProfile): any => {
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
    }, []);

    const isAdmin = useCallback((userGroups: any): boolean => {
        return window.env.ADMIN_GROUP ? userGroups.includes(window.env.ADMIN_GROUP) : false;
    }, []);

    const isUser = useCallback((userGroups: any): boolean => {
        return window.env.USER_GROUP ? userGroups.includes(window.env.USER_GROUP) : false;
    }, []);

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
                }),
            );
        }
    }, [dispatch, oidcUser, getGroups, isAdmin, isUser]);

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
                            if ((window.env.USER_GROUP && user && isUser(getGroups(user.profile))) || !window.env.USER_GROUP){
                                window.history.replaceState({}, document.title, `${window.location.pathname}${window.location.hash}`);
                                setOidcUser(user);
                            } else  {
                                await purgeStore();
                                await auth.signoutSilent();
                            }
                        }}
                    >
                        <App />
                    </AuthProvider>
                } />
            </Routes>
        </HashRouter>
    );
}

export default AppConfigured;

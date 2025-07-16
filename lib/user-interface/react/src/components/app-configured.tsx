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
import App from '../App';

import { OidcConfig } from '../config/oidc.config';
import { User, UserProfile } from 'oidc-client-ts';
import { useAppDispatch } from '../config/store';
import { updateUserState } from '../shared/reducers/user.reducer';
import { useEffect, useState } from 'react';

function AppConfigured () {
    const dispatch = useAppDispatch();
    const [oidcUser, setOidcUser] = useState<User | void>();
    const auth = useAuth();

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
                }),
            );
        }
    }, [dispatch, oidcUser]);

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
        return window.env.USER_GROUP ? userGroups.includes(window.env.ADMIN_GROUP) : false;
    };

    return (
        <AuthProvider
            {...OidcConfig}
            onSigninCallback={async (user: User | void) => {
                if ((window.env.USER_GROUP && user && isUser(getGroups(user.profile))) || !window.env.USER_GROUP){
                    window.history.replaceState({}, document.title, `${window.location.pathname}${window.location.hash}`);
                    setOidcUser(user);
                } else  {
                    await auth.signoutSilent();
                }
            }}
        >
            <App />
        </AuthProvider>
    );
}

export default AppConfigured;

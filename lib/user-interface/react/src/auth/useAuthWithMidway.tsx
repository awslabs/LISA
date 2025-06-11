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
 
 import { useAuth as useOidcAuth } from 'react-oidc-context';
 import { useState, useEffect } from 'react';
 import { getMidwayJwtToken, getMidwayUser } from './MidwayJwtToken';
 import { useAppDispatch } from '../config/store';
 import { updateUserState } from '../shared/reducers/user.reducer';
 
 // Custom authentication hook that supports both OIDC and Midway authentication
 export function useAuth() {
     const oidcAuth = useOidcAuth();
     const dispatch = useAppDispatch();
     const [isMidwayAuthenticated, setIsMidwayAuthenticated] = useState<boolean | null>(null);
     const [isLoading, setIsLoading] = useState<boolean>(true);
     const isMidwayEnabled = window.env.MIDWAY_AUTH_ENABLED === true;
     const [midwayUser, setMidwayUser] = useState<string>();
     const [midwayToken, setMidwayToken] = useState<string>();
 
     useEffect(() => {
         // Only check Midway authentication if the feature flag is enabled
         if (isMidwayEnabled) {
             const checkMidwayAuth = async () => {
                 try {
                     const midwayUser = await getMidwayUser();
                     if(['batzela', 'evmann', 'dustinps', 'jmharold', 'amescyn'].includes(midwayUser)) {
                        setIsMidwayAuthenticated(!!midwayUser);
                        setMidwayUser(midwayUser);
                        const midwayToken = await getMidwayJwtToken();
                        setMidwayToken(midwayToken);
                        dispatch(
                            updateUserState({
                                name: midwayUser,
                                preferred_username: midwayUser,
                                email: `${midwayUser}@amazon.com`,
                                groups: [],
                                isAdmin: ['batzela', 'evmann', 'dustinps', 'jmharold', 'amescyn'].includes(midwayUser),
                            }),
                        )
                    } else {
                        throw new Error('User is not an authorized');
                    }
                 } catch (error) {
                     console.error('Error checking Midway authentication:', error);
                     setIsMidwayAuthenticated(false);
                 } finally {
                     setIsLoading(false);
                 }
             };
             
             checkMidwayAuth();
         } else {
             // If Midway is not enabled, we're not loading for Midway auth
             setIsLoading(oidcAuth.isLoading);
         }
     }, [isMidwayEnabled]);
 
     // Update loading state when OIDC auth state changes
     useEffect(() => {
         if (!isMidwayEnabled) {
             setIsLoading(oidcAuth.isLoading);
         } else {
             // If Midway is enabled, we're only done loading when we know both auth states
             if (isMidwayAuthenticated !== null) {
                 setIsLoading(false);
             }
         }
     }, [oidcAuth.isLoading, isMidwayAuthenticated, isMidwayEnabled]);
 
     return {
         // Use Midway authentication status if enabled, otherwise use OIDC
         isAuthenticated: isMidwayEnabled ? isMidwayAuthenticated : oidcAuth.isAuthenticated,
         isLoading: isLoading,
         // Pass through the original OIDC auth methods and properties
         user: isMidwayEnabled ? { profile: { email: `${midwayUser}@amazon.com`, sub: midwayUser }, id_token: midwayToken } : oidcAuth.user,
         signinRedirect: oidcAuth.signinRedirect,
         signoutRedirect: oidcAuth.signoutRedirect,
         signoutSilent: oidcAuth.signoutSilent,
         // Custom isAdmin property based on the user state
         isAdmin: true
         // isAdmin: currentUser?.isAdmin || false
     };
 }
 
 export default useAuth;
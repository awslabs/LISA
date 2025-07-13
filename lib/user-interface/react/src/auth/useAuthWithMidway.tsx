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
 import { useState, useEffect, useRef } from 'react';
 import { getMidwayJwtToken, getMidwayUser } from './MidwayJwtToken';
 import { useAppDispatch } from '../config/store';
 import { updateUserState } from '../shared/reducers/user.reducer';
 import BrassClient from '../auth/BrassClient';

 // Cache for authentication results to prevent duplicate API calls
 interface AuthCache {
     midwayUser?: string;
     midwayToken?: string;
     isAuthenticated?: boolean;
     isAdminUser?: boolean;
     authError?: {type: 'oidc' | 'bindle', message: string, bindleGuid?: string} | null;
     timestamp: number;
 }

 let globalAuthCache: AuthCache | null = null;
 let authPromise: Promise<AuthCache> | null = null;
 const CACHE_DURATION = 5 * 60 * 1000; // 5 minutes cache

 // Custom authentication hook using Midway authentication with BRASS authorization
 export function useAuth() {
     const oidcAuth = useOidcAuth();
     const dispatch = useAppDispatch();
     const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
     const [isLoading, setIsLoading] = useState<boolean>(true);
     const [midwayUser, setMidwayUser] = useState<string>();
     const [midwayToken, setMidwayToken] = useState<string>();
     const [isAdminUser, setIsAdminUser] = useState<boolean>(false);
     const [authError, setAuthError] = useState<{type: 'oidc' | 'bindle', message: string, bindleGuid?: string} | null>(null);
     const isInitialized = useRef(false);
 
     // Cached authentication function to prevent duplicate API calls
     const performAuthentication = async (): Promise<AuthCache> => {
         console.info('[useAuth] Performing fresh authentication check');
         
         try {
             const midwayUser = await getMidwayUser();
             if (!midwayUser) {
                 throw new Error('No Midway user found');
             }
             
             // Get bindle GUIDs from environment
             const appAccessBindle = window.env.APP_ACCESS_BINDLE;
             const adminAccessBindle = window.env.ADMIN_ACCESS_BINDLE;
             
             if (!appAccessBindle) {
                 throw new Error('APP_ACCESS_BINDLE not configured in environment');
             }
             
             const brassClient = new BrassClient();
             
             // Check app access (required for all users)
             const appAccessResult = await brassClient.isAuthorizedToUnlockBindle(midwayUser, appAccessBindle);
             
             if (appAccessResult.authorized) {
                 // User has app access, now check admin access if configured
                 let hasAdminAccess = false;
                 if (adminAccessBindle) {
                     try {
                         const adminAccessResult = await brassClient.isAuthorizedToUnlockBindle(midwayUser, adminAccessBindle);
                         hasAdminAccess = adminAccessResult.authorized;
                     } catch (adminError) {
                         console.warn('Error checking admin access:', adminError);
                         // Continue with non-admin access
                     }
                 }
                 
                 const midwayToken = await getMidwayJwtToken();
                 
                 return {
                     midwayUser,
                     midwayToken,
                     isAuthenticated: true,
                     isAdminUser: hasAdminAccess,
                     authError: null,
                     timestamp: Date.now()
                 };
             } else {
                 // User doesn't have app access
                 return {
                     midwayUser,
                     midwayToken: undefined,
                     isAuthenticated: false,
                     isAdminUser: false,
                     authError: {
                         type: 'bindle',
                         message: `You don't have access to the required app bindle lock. Please request access to bindle: ${appAccessBindle}`,
                         bindleGuid: appAccessBindle
                     },
                     timestamp: Date.now()
                 };
             }
         } catch (error) {
             console.error('Error checking Midway authentication:', error);
             
             // Check if this is a bindle lock error or a general auth error
             let authError;
             if (error.message?.includes('bindle') || error.message?.includes('authorized')) {
                 const appAccessBindle = window.env.APP_ACCESS_BINDLE || 'unknown';
                 authError = {
                     type: 'bindle' as const,
                     message: `Access denied: ${error.message}`,
                     bindleGuid: appAccessBindle
                 };
             } else {
                 authError = {
                     type: 'oidc' as const,
                     message: 'Authentication failed. Please try signing in again.'
                 };
             }
             
             return {
                 midwayUser: undefined,
                 midwayToken: undefined,
                 isAuthenticated: false,
                 isAdminUser: false,
                 authError,
                 timestamp: Date.now()
             };
         }
     };

     useEffect(() => {
         // Prevent multiple simultaneous auth checks
         if (isInitialized.current) {
             return;
         }
         isInitialized.current = true;

         const checkMidwayAuth = async () => {
             try {
                 // Check if we have valid cached data
                 if (globalAuthCache && Date.now() - globalAuthCache.timestamp < CACHE_DURATION) {
                     console.info('[useAuth] Using cached authentication data');
                     const cached = globalAuthCache;
                     setIsAuthenticated(cached.isAuthenticated ?? false);
                     setMidwayUser(cached.midwayUser);
                     setMidwayToken(cached.midwayToken);
                     setIsAdminUser(cached.isAdminUser ?? false);
                     setAuthError(cached.authError ?? null);
                     
                     if (cached.isAuthenticated && cached.midwayUser) {
                         dispatch(
                             updateUserState({
                                 name: cached.midwayUser,
                                 preferred_username: cached.midwayUser,
                                 email: `${cached.midwayUser}@amazon.com`,
                                 groups: [],
                                 isAdmin: cached.isAdminUser ?? false,
                             }),
                         );
                     }
                     return;
                 }

                 // If there's already an auth promise in progress, wait for it
                 if (authPromise) {
                     console.info('[useAuth] Waiting for existing authentication check');
                     const result = await authPromise;
                     globalAuthCache = result;
                 } else {
                     // Start new authentication check
                     authPromise = performAuthentication();
                     const result = await authPromise;
                     globalAuthCache = result;
                     authPromise = null;
                 }

                 // Update component state from cache
                 const cached = globalAuthCache!;
                 setIsAuthenticated(cached.isAuthenticated ?? false);
                 setMidwayUser(cached.midwayUser);
                 setMidwayToken(cached.midwayToken);
                 setIsAdminUser(cached.isAdminUser ?? false);
                 setAuthError(cached.authError ?? null);
                 
                 if (cached.isAuthenticated && cached.midwayUser) {
                     dispatch(
                         updateUserState({
                             name: cached.midwayUser,
                             preferred_username: cached.midwayUser,
                             email: `${cached.midwayUser}@amazon.com`,
                             groups: [],
                             isAdmin: cached.isAdminUser ?? false,
                         }),
                     );
                 }
             } catch (error) {
                 console.error('Error in auth check:', error);
                 setIsAuthenticated(false);
                 setAuthError({
                     type: 'oidc',
                     message: 'Authentication failed. Please try again.'
                 });
             } finally {
                 setIsLoading(false);
             }
         };
         
         checkMidwayAuth();
     }, []); // Empty dependency array - only run once per component mount
 
     return {
         // Use Midway authentication status
         isAuthenticated: isAuthenticated,
         isLoading: isLoading,
         // Midway user profile
         user: { profile: { email: `${midwayUser}@amazon.com`, sub: midwayUser }, id_token: midwayToken },
         // Pass through OIDC auth methods for sign-in/out
         signinRedirect: oidcAuth.signinRedirect,
         signoutRedirect: oidcAuth.signoutRedirect,
         signoutSilent: oidcAuth.signoutSilent,
         // Admin status based on BRASS admin bindle access
         isAdmin: isAdminUser,
         // Authentication error information
         authError: authError
     };
 }
 
 export default useAuth;

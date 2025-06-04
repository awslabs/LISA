/*
   https://code.amazon.com/packages/GenesisWebAppAssets/blobs/mainline/--/src/auth/MidwayJwtToken.ts
 */
 import jwtDecode, {JwtPayload} from 'jwt-decode';
 
 const TIMEOUT_BUFFER_SECONDS =  30;
 const RETRY_ATTEMPTS = 3;
 const ID_TOKEN = 'id_token';
 const STATE = 'state';
 
 const token = { value: '', sub: '' };
 const midwayParams = {
   scope: 'openid',
   response_type: ID_TOKEN,
   client_id: encodeURIComponent(`${window.location.host}`),
   redirect_uri: '',
   nonce: '',
 };
 
 export interface JwtMidwayPayload extends JwtPayload {
   nonce: string
 }
 
 export async function getMidwayJwtToken(): Promise<string> {
   if (!token.value) {
     await refreshToken();
     }
 
   return token.value;
 }
 
 // Gets the Midway user that came from the Midway JWT token
 export async function getMidwayUser(): Promise<string> {
   if (!token.sub) {
     await refreshToken();
   }
 
   return token.sub;
 }
 
 async function refreshToken() {
   updateMidwayParams();
   // Save the current nonce for verification later - this prevents issues when function is called multiple times
   const currentNonce = midwayParams.nonce;
   const queryParams =
     Object.keys(midwayParams).map((key) => `${key}=${midwayParams[key]}`).join('&');
   const url = `${window.env.AUTHORITY}/SSO?${queryParams}`;
   token.value = await fetch(url, { credentials: 'include' })
     .then((response) => {
       if (response.status === 401) {
         // Redirect the user to Midway login
         window.location.replace(`${window.env.AUTHORITY}/SSO/redirect?${queryParams}`);
       }
       removeMidwaySearchParams();
       return response.text();
     });
     const decodedToken = jwtDecode<JwtMidwayPayload>(token.value);
   token.sub = decodedToken.sub!; // The midway user
   // Verify nonce against the saved nonce value, not the potentially updated midwayParams.nonce
   if (decodedToken.nonce != currentNonce) {
     // Clear the token if nonce doesn't match, otherwise store it
     token.value = '';
     token.sub = '';
     console.error('Error when verifying token nonce');
   } else {
     sessionStorage.setItem(`oidc.user:${window.env.AUTHORITY}:${window.env.CLIENT_ID}`, JSON.stringify({id_token: token.value}))
   }
   const expiration = decodedToken.exp!;
   window.setTimeout(
     () => retryWithJitter(refreshToken),
     ((expiration - Math.round(Date.now() / 1000)) - TIMEOUT_BUFFER_SECONDS) * 1000,
   );
 }
 
 /**
    * Calls an asynchronous function with retries and jitter built in using timeouts to simulate recursion
    * @param func Function reference to the function that should be executed
    * @param attempt The attempt number
    * @param error The last error that was received
    * @returns {Promise<void>}
    * @private
    */
 async function retryWithJitter(func: Function, attempt: number = 0, error: any | unknown = null): Promise<void> {
   if (attempt === RETRY_ATTEMPTS - 1) {
     throw error;
   }
   try {
     await func();
   } catch (e: any | unknown) {
     window.setTimeout(() => retryWithJitter(func, attempt + 1, e), 500);
   }
 }
 
 function randomString() {
   return Math.random().toString(36).substring(2);
 }
 
 function updateMidwayParams() {
   midwayParams.nonce = randomString() + randomString();
   midwayParams.redirect_uri = encodeURIComponent(`${window.location}`);
 }
 
 /**
  * Removes from current location the URL params retuned by Midway (e.g. 'id_token',
  * 'state') after login redirection and updates browser history so they do not
  * appear in the current URL
  */
 function removeMidwaySearchParams() {
   const newLocation = removeLocationSearchParameters(ID_TOKEN, STATE);
   window.history.replaceState({}, '', newLocation);
 }
 
 /**
  * Removes the passed keys from the current location search (query)
  * @param keys
  * @returns a new location without the keys
  */
 function removeLocationSearchParameters(...keys: string[]): string {
   const location = window.location;
   const queryParams = new URLSearchParams(location.search);
   keys.forEach(key => queryParams.delete(key));
   const queryString = queryParams.toString();
   const base = location.href.replace(location.search, '');
   const newUrl = `${base}${queryString === '' ? '' : '?'}${queryString}`;
   return newUrl;
 }
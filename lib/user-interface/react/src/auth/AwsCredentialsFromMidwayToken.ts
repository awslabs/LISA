/*
   https://code.amazon.com/packages/GenesisWebAppAssets/blobs/mainline/--/src/auth/AwsCredentialsFromMidwayToken.ts
 */
 
 import { fromWebToken } from '@aws-sdk/credential-providers';
 import { getMidwayJwtToken, getMidwayUser } from './MidwayJwtToken';
 import { AwsCredentialIdentity } from '@aws-sdk/types';
 
 let credentials: AwsCredentialIdentity;  // Cached AWS sigv4 credentials
 
 // Gets AWS sigv4 credentials from a Midway JWT token
 export default async () => {
   if (! areCredentialsFresh()) {
     await refreshCredentials();
     console.log(`Refreshed AWS credentials on ${new Date()}`);
   }
   return credentials;
 }
 
 // Checks the cached credentials are not expired
 function areCredentialsFresh(): boolean {
   const expirationMarginMillisecs = 30 * 1000;
   return (
     credentials &&
     credentials.expiration !== undefined &&
     new Date().getTime() + expirationMarginMillisecs < credentials.expiration.getTime() // Not expired
   );
 }
 
 // This is what actually calls STS to exchange a Midway token with AWS sigv4 credentials from an assumed role
 async function refreshCredentials() {
   const midwayToken = await getMidwayJwtToken();
   const midwayUser = await getMidwayUser();
 
   credentials = await fromWebToken({
     roleArn: window.env.OPEN_ID_CONNECT_ROLE,  // Role to assume comes from the app settings json
     roleSessionName: midwayUser,     // Add the Midway alias as role session name so backend has caller's identity
     webIdentityToken: midwayToken,  // The midway JWT token that is exchanged for AWS credentials to call the API
     durationSeconds: 3600  // If not present the default is 1 hour
   })();
 
   if (!credentials) {
     throw new Error("Failed to get aws credentials from midway token");
   }
 }

# Example IdP Configurations

## Amazon Cognito

If using Amazon Cognito, the `authority` will be the URL to your User Pool. As an example, if your User Pool ID, not
the name, is `us-east-1_example`, and is running in `us-east-1` then the URL for the `authority` field would be
`https://cognito-idp.us-east-1.amazonaws.com/us-east-1_example`. The `clientId` can be found in your User Pool's
"App integration" tab from within the AWS Management Console. At the bottom of the page you will see the list of
clients and their associated Client IDs. The ID here is what we will need for the `clientId` field.


```
authConfig:
  authority: https://cognito-idp.us-east-1.amazonaws.com/us-east-1_example
  clientId: your-client-id
  adminGroup: AdminGroup
  userGroup: UserGroup
  jwtGroupsProperty: cognito:groups
```

## Keycloak

If using Keycloak, the `authority` will be the URL to your Keycloak server. The `clientId` is likely not a random string
like in the Cognito clients. Instead, it will be a string configured by your Keycloak Administrator. Your Administrator
will be able to provide you with a client name or create a client for you to use for this application. Once you have this
string, use that as the `clientId` within the `authConfig` block.


```
authConfig:
  authority: https://your-keycloak-server.com
  clientId: your-client-name
  adminGroup: AdminGroup
  userGroup: UserGroup
  jwtGroupsProperty: realm_access.roles
```

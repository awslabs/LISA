# IDP Configuration Examples

## AWS Cognito Example:

In Cognito, the `authority` will be the URL to your User Pool. As an example, if your User Pool ID, not the name, is
`us-east-1_example`, and if it is
running in `us-east-1`, then the URL to put in the `authority` field would be
`https://cognito-idp.us-east-1.amazonaws.com/us-east-1_example`. The `clientId`
can be found in your User Pool's "App integration" tab from within the AWS Management Console, and at the bottom of the
page, you will see the list of clients
and their associated Client IDs. The ID here is what we will need for the `clientId` field.

```yaml
authConfig:
  authority: https://cognito-idp.us-east-1.amazonaws.com/us-east-1_example
  clientId: your-client-id
  adminGroup: AdminGroup
  userGroup: UserGroup
  jwtGroupsProperty: cognito:groups
```

## Keycloak Example:

In Keycloak, the `authority` will be the URL to your Keycloak server. The `clientId` is likely not a random string like
in the Cognito clients, and instead
will be a string configured by your Keycloak administrator. Your administrator will be able to give you a client name or
create a client for you to use for
this application. Once you have this string, use that as the `clientId` within the `authConfig` block.

```yaml
authConfig:
  authority: https://your-keycloak-server.com
  clientId: your-client-name
  adminGroup: AdminGroup
  userGroup: UserGroup
  jwtGroupsProperty: realm_access.roles
```

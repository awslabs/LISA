# API Token Management

## Overview

LISA's API Token Management system provides secure, programmatic access to LISA APIs outside the Chat UI. This enables integration with external tools and custom applications. The system features both administrative and self-service token management through the UI and REST APIs, with enterprise-grade security including token hashing, expiration, and group-based access control.

## Key Features

- **Secure Token Storage**: Tokens are hashed using SHA-256 before storage
- **UI-Based Management**: Interfaces for both administrators and end users
- **REST API Access**: Programmatic token management via REST endpoints
- **Token Types**: Support for user tokens and system tokens
- **Group-Based Access Control**: Tokens inherit user group permissions, unless assigned by admin
- **Automatic Expiration**: Configurable token expiration (default: 90 days)
- **Self-Service**: Users can create and manage their own tokens if enabled by the admin

## Architecture

### Data Storage

API tokens are stored in the DynamoDB `APITokenTable` with enhanced security and metadata:

**Table Schema:**
- **Partition Key**: `token` (SHA-256 hash of the actual token)
- **Attributes**:
  - `tokenUUID`: Unique identifier for the token
  - `username`: User token belongs to
  - `createdBy`: User who created the token (admin or self)
  - `createdDate`: Unix timestamp when token was created
  - `tokenExpiration`: Unix timestamp when token expires
  - `name`: Human-readable token name
  - `groups`: Array of group memberships
  - `isSystemToken`: Boolean indicating if it's a system token
- **Global Secondary Index**: `username-index` (allows querying tokens by username)

### Security Model

1. **Token Generation**: Cryptographically secure 128-character hexadecimal tokens
2. **Token Hashing**: SHA-256 hashing before database storage
3. **One-Time Display**: Plain-text token shown only at creation
4. **Group Inheritance**: Tokens inherit user's group permissions at creation time (unless admin specifies custom groups)
5. **Expiration Enforcement**: Expired tokens automatically rejected during authorization
6. **Legacy Rejection**: Prior manually created and unhashed (legacy tokens) are rejected

## Configuration

### Enabling User Token Management

To allow users to create and manage their own tokens via the UI, configure the following settings:

**1. Add API Group Into Config**

Edit your `config-custom.yaml`:

```yaml
deploymentName: my-deployment
deploymentStage: prod

authConfig:
  authority: https://your-oidc-provider.com
  clientId: your-client-id
  adminGroup: lisa-admins
  userGroup: lisa-users
  apiGroup: lisa-api-users  # Add this line - users in this group can create tokens programmatically

# ... other configuration ...
```

**2. Enable in UI Configuration Page**

If using LISA's UI, the `Allow user managed API tokens` UI configuration must be enabled for users to manage tokens via the UI:

Navigate to **Configuration** → **User Components** and enable:
- `Allow user managed API tokens`

### Role Configuration

The API Token Management system requires the `ApiTokensApiRole` IAM role. This is automatically created during deployment. If using role overrides:

```yaml
roles:
  ApiTokensApiRole: CustomApiTokensRole
```

## Managing Tokens via UI

### Admin: Token Management Page

Administrators have full visibility and control over all tokens in the system.

#### Accessing the Administrative Token Management Page

1. Navigate to **Administration** → **API Token Management**

#### Creating Tokens for Users (Admin)

1. Click **Create Token**
2. **Step 1: Basic Information**
   - `Username`: Enter the username for whom the token is being created
   - `Token Name`: Descriptive name (e.g., "CI/CD Pipeline Token")
   - `System Token`: Toggle ON to denote token as being for a system / service
3. **Step 2: Permissions**
   - `Groups`: Add groups permissions this token should have (can differ from user's groups)
   - `Expiration Date`: Select when token expires (default: 90 days)
4. **Step 3: Review**
   - Review all settings
   - Click **Create Token**
5. **Token Display Modal**

> [!WARNING]
> Token is displayed **ONLY ONCE**. Copy the token immediately or download it.

   - Copy the token immediately or download it
   - Check "I have securely saved this token"
   - Click **Close**

#### Viewing All Tokens

The token table displays:
- `Token Name`: Descriptive name
- `Username`: User token belongs to
- `Created By`: Who created the token
- `Created Date`: When token was created
- `Expiration`: When token expires
- `Status`: Active, Expired, or Legacy
- `Groups`: Associated groups
- `System Token`: Badge if system token
- `Token UUID`: Unique identifier

**Features:**
- **Search**: Filter tokens by name, username, creator, or groups
- **Pagination**: Navigate through pages of tokens
- **Sort**: Click column headers to sort
- **Refresh**: Update the token list
- **Customize View**: Select which columns to display

#### Deleting Tokens (Admin)

1. Select a token from the table
2. Click **Delete**
3. Confirm the deletion

### User: Self-Service Token Management

Users in the API group can create and manage their own tokens.

#### Accessing Your Token

1. Click the user-profile icon (top-right)
2. Select **API Token**

This opens a view which shows the user their API token.

#### Creating Your Own Token

1. Click **Create Token**
2. **Token Details:**
   - **Token Name**: Enter a descriptive name (e.g., "My VSCode Token")
   - **Expiration Date**: Select when token expires (default: 90 days)

> [!NOTE]
> Token will automatically inherit your current groups.
3. Click **Create Token**
4. **Token Display Modal** (see Admin section above)

**Limitations:**
- Users can create only ONE token
- Users cannot create system tokens
- User tokens inherit the user's group memberships at point of creation (admins can create tokens with custom groups on behalf of users)
- To create a new token, a user must first delete their existing token

#### Viewing Your Token

The interface shows:
- Your token details
- Current status (Active/Expired)
- Expiration date
- Associated groups

#### Deleting Your Token

1. Select your token
2. Click **Delete**
3. Confirm deletion

## Managing Tokens via API

Token management via API will always be available to admins. Users need to be members of the API Group in order to utilize the `/api-tokens` endpoint.

If no API tokens exist it is required to authenticate via JWT token.

### API Endpoints

**Base URL**: `https://<your-lisa-domain>/api-tokens`

### Create Token for User (Admin Only)

Create a token for any user. Only administrators can use this endpoint.

```bash
POST /api-tokens/{username}
Content-Type: application/json
Authorization: Bearer <your-jwt-token> || <your-api-token>

{
  "name": "CI/CD Pipeline Token",
  "groups": ["developers", "api-users"],
  "isSystemToken": false,
  "tokenExpiration": 1735689600
}
```

**Request Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `username` | string | Yes | Username to create token for (path parameter) |
| `name` | string | Yes | Human-readable token name |
| `groups` | array | No | Groups to assign (default: []) |
| `isSystemToken` | boolean | No | Allow multiple tokens per user (default: false) |
| `tokenExpiration` | number | No | Unix timestamp (default: 90 days from now) |

**Response (201 Created):**

```json
{
  "token": "a1b2c3d4e5f6...",
  "tokenUUID": "550e8400-e29b-41d4-a716-446655440000",
  "tokenExpiration": 1735689600,
  "createdDate": 1704067200,
  "username": "johndoe",
  "name": "CI/CD Pipeline Token",
  "groups": ["lisa-users", "lisa-api-users"],
  "isSystemToken": false
}
```

> [!WARNING]
> The `token` field contains the plain-text token and will **NEVER** be returned again.

**Error Responses:**

- `400 Bad Request`: Validation errors (e.g., expiration in past)
- `400 Bad Request`: User already has a token (for non-system tokens)
- `401 Unauthorized`: Not an admin user
- `422 Unprocessable Entity`: Invalid request format

### Create Your Own Token

Create a token for yourself.

```bash
POST /api-tokens/
Content-Type: application/json
Authorization: Bearer <your-jwt-token> || <your-api-token>

{
  "name": "My Development Token",
  "tokenExpiration": 1735689600
}
```

**Request Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | Yes | Human-readable token name |
| `tokenExpiration` | number | No | Unix timestamp (default: 90 days from now) |

**Response (201 Created):**

```json
{
  "token": "a1b2c3d4e5f6...",
  "tokenUUID": "660e8400-e29b-41d4-a716-446655440001",
  "tokenExpiration": 1735689600,
  "createdDate": 1704067200,
  "username": "john.doe",
  "name": "My Development Token",
  "groups": ["api-users"],
  "isSystemToken": false
}
```

**Error Responses:**

- `400 Bad Request`: User already has a token
- `403 Forbidden`: User not in API group

### List Tokens

List tokens. Admins see all tokens; users see their own.

```bash
GET /api-tokens/
Authorization: <your-api-token>
```

**Response (200 OK):**

```json
{
  "tokens": [
    {
      "tokenUUID": "550e8400-e29b-41d4-a716-446655440000",
      "tokenExpiration": 1735689600,
      "createdDate": 1704067200,
      "username": "johndoe",
      "createdBy": "admin",
      "name": "CI/CD Pipeline Token",
      "groups": ["developers"],
      "isSystemToken": false,
      "isExpired": false,
      "isLegacy": false
    }
  ]
}
```

**Token Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `tokenUUID` | string | Unique identifier |
| `tokenExpiration` | number | Unix timestamp |
| `createdDate` | number | Unix timestamp |
| `username` | string | Token owner |
| `createdBy` | string | Creator username |
| `name` | string | Token name |
| `groups` | array | Associated groups |
| `isSystemToken` | boolean | System token flag |
| `isExpired` | boolean | Whether token is expired |
| `isLegacy` | boolean | Legacy token (no UUID) |

### Get Token Details

Get details for a specific token.

```bash
GET /api-tokens/{tokenUUID}
Authorization: <your-api-token>
```

**Response (200 OK):** Same structure as individual token in list response.

**Error Responses:**

- `404 Not Found`: Token doesn't exist or user lacks permission

### Delete Token

Delete a token. Users can delete only their own tokens; admins can delete any token.

```bash
DELETE /api-tokens/{tokenUUID}
Authorization: Bearer <your-api-token>
```

**Response (200 OK):**

```json
{
  "message": "Token deleted successfully",
  "tokenUUID": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Error Responses:**

- `403 Forbidden`: User trying to delete legacy token (admin only)
- `404 Not Found`: Token doesn't exist or user lacks permission

## Using API Tokens

### Making API Requests

Once you have a token, use it in API requests via the `Authorization` header:

```bash
# List available models
curl https://<your-lisa-domain>/v2/serve/models \
  -H "Authorization:<your-api-token>" \
  -H "Content-Type: application/json"

# Chat completion request
curl https://<your-lisa-domain>/v2/serve/chat/completions \
  -H "Authorization: <your-api-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "your-model-id",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

## Token Types

### User Tokens

**Characteristics:**
- One token per user
- Automatically inherits user's groups (unless created by admin with custom groups)
- Created by user (self-service) or admin
- Cannot be created if user already has a token

**Use Cases:**
- Personal development
- Individual tool integration
- User-specific automation

### System Tokens

**Characteristics:**
- Admin-only creation
- Customizable group assignments
- Ideal for service accounts

**Use Cases:**
- Multiple services needing separate tokens
- Shared service accounts
- Production automations

**Example: Creating a System Token**

```bash
POST /api-tokens/ci-bot
Content-Type: application/json

{
  "name": "Production Pipeline",
  "isSystemToken": true,
  "groups": ["ci-cd", "production"],
  "tokenExpiration": 1767225600
}
```

## Group-Based Access Control

Tokens inherit and enforce group-based permissions.

### How Group Permissions Work

1. **At Creation**: Token captures groups
   - User tokens: Inherit user's current groups
   - System tokens: Admin specifies groups

2. **At Request Time**: Token's groups determine access
   - Checked against model permissions
   - Checked against API endpoint permissions
   - Checked against resource access policies

3. **Group Updates**: Token groups are **STATIC**
   - Changing user's groups doesn't update token groups
   - Create a new token to reflect updated permissions

## Legacy Token Migration

Legacy tokens are no longer supported and will need to be recreated.

### Identifying Legacy Tokens

Legacy tokens have:
- Token values stored as-is (not hashed)
- No metadata (name, groups, etc.)
- "Legacy" badge in UI

### Legacy Token Limitations

1. **No Modern Security**: Tokens not hashed
2. **No Group Control**: No group associations
3. **Deprecated**: Will be rejected

### Migration Steps

1. **Identify Legacy Tokens**: Check UI for "Legacy" badge or call API to list tokens and identify tokens with non-hashed values and no metadata.
2. **Create Modern Tokens**: Use UI or API to create replacements
3. **Update Applications**: Switch to new tokens
4. **Delete Legacy Tokens**: Admin deletes old tokens
5. **Verify**: Ensure applications work with new tokens

## Troubleshooting

### Token Not Working

**Symptom**: API requests return 401 Unauthorized

**Possible Causes:**

1. Token expired
2. Token is legacy
3. Token incorrectly copied (whitespace/truncation)
4. Token doesn't have required groups
5. Token deleted

**Resolution:**

1. Check token expiration in UI
2. Verify token is not marked as "Legacy"
3. Ensure token is complete
4. Verify user/token has required groups for the API
5. Check token exists in token list
6. Create new token if needed

### Token Permissions Not Working

**Symptom**: Token cannot access certain models/APIs

**Possible Causes:**

1. Token groups don't include required group
2. User's groups changed after token creation
3. Model/API requires different permissions

**Resolution:**

1. Check token groups in UI
2. Create new token (self-service tokens inherit current groups)
3. Contact admin to create token with specific groups
4. Verify model/API group requirements

### UI Not Showing Token Management

**Symptom**: Token management menu items missing

**Possible Causes:**

1. Feature not enabled in configuration
2. User not in admin or API group
3. Authentication configuration issues

**Resolution:**

1. Check `config-custom.yaml` for `apiGroup` setting
2. Enable "Allow user managed API tokens" in Configuration
3. Verify user group memberships
4. Check admin group configuration

### Legacy Tokens Being Rejected

**Symptom**: Previously working tokens are now failing

**Expected Behavior**: Legacy tokens are intentionally rejected as part of security improvements.

**Resolution:**

1. Migrate to modern tokens immediately
2. Follow migration steps above

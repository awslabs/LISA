# Session API

LISA uses session APIs to persist and manage chat session state, including metadata updates and media attachment workflows.

## Overview

Session endpoints power core chat lifecycle behavior in LISA:

- Listing a user's existing sessions
- Creating or updating a session
- Renaming sessions for better organization
- Attaching generated or uploaded images to session history
- Deleting one or all sessions for the user

These APIs are used by the chat UI and can also be used programmatically.

## API Reference

Base path: `/session`

### List Sessions

- Method: `GET`
- Path: `/session`
- Description: Lists sessions available to the caller.

### Delete All Caller Sessions

- Method: `DELETE`
- Path: `/session`
- Description: Deletes all sessions for the caller.

### Get Session

- Method: `GET`
- Path: `/session/{sessionId}`
- Description: Returns a specific session by ID.

Path parameters:

- `sessionId` (string, required): Session identifier

### Create or Update Session

- Method: `PUT`
- Path: `/session/{sessionId}`
- Description: Creates or updates a specific session.

Path parameters:

- `sessionId` (string, required): Session identifier

### Delete Session

- Method: `DELETE`
- Path: `/session/{sessionId}`
- Description: Deletes a specific session.

Path parameters:

- `sessionId` (string, required): Session identifier

### Rename Session

- Method: `PUT`
- Path: `/session/{sessionId}/name`
- Description: Updates a session display name.

Path parameters:

- `sessionId` (string, required): Session identifier

### Attach Image to Session

- Method: `PUT`
- Path: `/session/{sessionId}/attachImage`
- Description: Attaches image metadata/content to a session.

Path parameters:

- `sessionId` (string, required): Session identifier

Example:

```bash
curl -X GET "https://<api-gateway-domain>/<stage>/session" \
  -H "Authorization: Bearer <token>"
```

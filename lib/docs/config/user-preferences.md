# User Preferences API

LISA persists user-specific behavior and UI preferences through a dedicated user preferences API.

## Overview

User Preferences are used to retain per-user settings across sessions, including preferences that affect chat and MCP behavior. This API provides:

- Retrieval of current caller preferences
- Creation or update of caller preferences

These endpoints are user-scoped and designed for personalized experience management.

## API Reference

Base path: `/user-preferences`

### Get User Preferences

- Method: `GET`
- Path: `/user-preferences`
- Description: Returns preferences for the calling user.

### Create or Update User Preferences

- Method: `PUT`
- Path: `/user-preferences`
- Description: Creates or updates preferences for the calling user.

Example:

```bash
curl -X GET "https://<api-gateway-domain>/<stage>/user-preferences" \
  -H "Authorization: Bearer <token>"
```

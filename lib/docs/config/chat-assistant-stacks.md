# Chat Assistant Stacks

**Chat Assistant Stacks** let LISA admins define preconfigured assistants that bundle models, RAG repositories and collections, MCP servers and tools, and prompt templates. Users see only the stacks they have access to and can start chat sessions from them with everything preconfigured. Access is controlled by enterprise user groups.

---

## Overview

- **Admins** enable the feature in Configuration, then create and manage stacks from **Administration → Chat Assistant Stack Management**. Each stack has a name, description, and selections for models, repos, collections, MCP, and prompts. Stacks can be activated or deactivated without losing configuration.
- **Users** see a **Chat Assistants** section in the Chat UI left pane (above History). Clicking an assistant opens a new session preconfigured with that assistant. Sessions appear in History like other chats.

---

## Enabling the feature

1. Go to **Configuration** in the LISA UI.
2. In the **Advanced** section, turn on the **Chat Assistant Stacks** toggle.
3. Save configuration.

When enabled:

- **Administration** shows a **Chat Assistant Stack Management** entry so admins can manage stacks.
- The Chat UI shows the **Chat Assistants** section in the left pane for users who have access to at least one active stack.

---

## Administrator guide

### Chat Assistant Stack Management

With Chat Assistant Stacks enabled, open **Administration** and select **Chat Assistant Stack Management**. The page lists stacks as cards (similar to Model Management) and includes:

- **Refresh** – Reload the stack list.
- **Actions** – Per-stack actions (edit, delete, activate/deactivate).
- **Create Stack** – Start the create-stack flow.

You can search stacks by name or description to find them quickly.

### Creating a stack

1. Click **Create Stack**.
2. Fill in the form (see [Stack form fields](#stack-form-fields) below). Steps typically group fields as **Models**, **RAG** (repos and collections), **Agents** (MCP servers and tools), **Prompts**, and **Access**.
3. **Required:** Stack Assistant Name, Description, and at least one **Model**. All other multi-select fields are optional (0 or more).
4. If you add at least one **MCP Server**, at least one selected model must support MCP tools; the UI will guide or validate this.
5. Save. The stack is created in **active** state unless you deactivate it.

### Updating a stack

From stack actions, choose **Edit** (or equivalent). You can change any updateable field (see table). Save to apply. Deactivated stacks remain visible and editable to admins.

### Deleting a stack

Use the delete action for the stack. Deletion removes the stack from the system. Users can no longer start new sessions from it; existing sessions follow normal LISA session behavior.

### Activating and deactivating stacks

- **Deactivate:** The stack stays in the system and visible to admins, but it no longer appears in the Chat Assistants list for users. Use this to temporarily hide an assistant without losing its configuration.
- **Activate:** The stack becomes available again to users who have access (see [Access control](#access-control)).

---

## Stack form fields

| Field | Type | Required | Updateable | Notes |
|-------|------|----------|------------|--------|
| **Stack Assistant Name** | Text | Yes | Yes | Shown to users. Subject to a maximum length (e.g. 256 characters). |
| **Description** | Text | Yes | Yes | |
| **Models** | Multiselect | Yes (≥1) | Yes | Any model (including embeddings for RAG). No default. |
| **Repos** | Multiselect | No (0 or ≥1) | Yes | RAG repositories. |
| **Collections** | Multiselect | No (0 or ≥1) | Yes | RAG collections. |
| **MCP Servers** | Multiselect | No (0 or ≥1) | Yes | From LISA MCP, Workbench, or Connections. If ≥1 selected, at least one model must support MCP tools. |
| **MCP Tools** | Multiselect | No (0 or ≥1) | Yes | |
| **Persona Prompts** | Single select | No | Yes | One prompt applied in the background (e.g. developer persona). |
| **Directive Prompts** | Multiselect | No (0 or ≥1) | Yes | User can choose from these in the session. |
| **Allowed Groups** | Multiselect | No (0 or ≥1) | Yes | LISA standard group selection. If **0 groups**, the stack is **global** (all users who can see Chat Assistants). Otherwise only users in at least one listed group see this stack. Users still only see resources they have permission to access. |

---

## Access control

- **Allowed Groups:** If you leave **Allowed Groups** empty, the stack is **global**—any user who has the Chat Assistants feature and can list stacks will see it (subject to resource-level permissions). If you add one or more groups, only users in at least one of those groups see this stack.
- **Resource permissions:** Stacks reference models, repos, collections, MCP servers, and prompts. Users only see stacks they have access to; when they open a session, they only see and use the underlying resources they are allowed to use. The UI may restrict choices (e.g. which models or prompts) to what the user can access.

---

## User guide

### Discovering assistants

When Chat Assistant Stacks is enabled and you have access to at least one **active** stack:

1. Open the **Chat** UI (e.g. LISA Chat or AI Assistant).
2. In the **left pane**, find the **Chat Assistants** section—it appears **above** the **History** search bar.
3. Expand **Chat Assistants** to see the list of assistants available to you (by allowed groups and resource permissions).

If no assistants are available, the section will indicate that no assistants are available.

### Starting a chat from an assistant

1. Click an assistant name in the **Chat Assistants** list.
2. A **new chat session** opens with that assistant’s stack preconfigured (models, repos, collections, MCP, persona and directive prompts, etc.).
3. You can start chatting; the assistant’s configuration is applied in the background.

### Choices within a stack

When a stack includes multiple options (e.g. several models, repos, or directive prompts) and you have access to all of them:

- You can **choose** which to use in that session (e.g. switch repos, collections, or directive prompts) where the UI allows.
- **Model:** Once you select a model for that session, you **cannot change it** for the rest of the session, consistent with existing LISA chat behavior.

### Session and history

- Sessions started from an assistant are saved under **History** like any other chat.
- **Session name:** Typically follows the pattern **[Assistant name] + initial prompt** (same as other sessions). You can rename sessions as supported by the UI.

---

## API Reference

The Chat Assistant Stacks API is exposed at `/chat-assistant-stacks` under the LISA API Gateway. All endpoints require a valid Bearer token. Most operations are admin-only; the list endpoint returns different results based on role and group membership.

### Base URL

```
https://<apigw_endpoint>/chat-assistant-stacks
```

### Authentication

All requests require the `Authorization: Bearer <token>` header with a valid LISA/OIDC token.

### Endpoints

| Method | Path | Description | Access |
|--------|------|-------------|--------|
| GET | `/chat-assistant-stacks` | List stacks | Admins: all stacks. Users: active stacks (allowedGroups empty or user in group). |
| GET | `/chat-assistant-stacks/{stackId}` | Get a single stack | Admin only |
| POST | `/chat-assistant-stacks` | Create a stack | Admin only |
| PUT | `/chat-assistant-stacks/{stackId}` | Update a stack | Admin only |
| DELETE | `/chat-assistant-stacks/{stackId}` | Delete a stack | Admin only |
| PUT | `/chat-assistant-stacks/{stackId}/status` | Activate or deactivate a stack | Admin only |

---

### List Stacks

Returns stacks. Admins receive all stacks; non-admin users receive only active stacks where they have access (empty `allowedGroups` or user in at least one group).

#### Request Example

```bash
curl -s -H "Authorization: Bearer <token>" -X GET https://<apigw_endpoint>/chat-assistant-stacks
```

#### Response Example

```json
{
  "Items": [
    {
      "stackId": "abc-123-def",
      "name": "Developer Assistant",
      "description": "Preconfigured for code-related tasks with RAG and MCP tools.",
      "modelIds": ["mistral-vllm"],
      "repositoryIds": ["repo-1"],
      "collectionIds": ["coll-1"],
      "mcpServerIds": [],
      "mcpToolIds": [],
      "personaPromptId": "prompt-1",
      "directivePromptIds": ["dir-1", "dir-2"],
      "allowedGroups": ["developers"],
      "isActive": true,
      "created": "2024-01-15T10:00:00Z",
      "updated": "2024-01-15T10:00:00Z"
    }
  ]
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `stackId` | string | Unique identifier for the stack |
| `name` | string | Display name (max 256 characters) |
| `description` | string | Description of the assistant |
| `modelIds` | string[] | IDs of models the stack uses (≥1 required) |
| `repositoryIds` | string[] | RAG repository IDs |
| `collectionIds` | string[] | RAG collection IDs |
| `mcpServerIds` | string[] | MCP server IDs |
| `mcpToolIds` | string[] | MCP tool IDs |
| `personaPromptId` | string \| null | Optional persona prompt ID |
| `directivePromptIds` | string[] | Directive prompt IDs |
| `allowedGroups` | string[] | User groups with access (empty = global) |
| `isActive` | boolean | Whether the stack is visible to users |
| `created` | string | ISO timestamp when created |
| `updated` | string | ISO timestamp when last updated |

---

### Get Stack

Retrieves a single stack by ID. Admin only.

#### Request Example

```bash
curl -s -H "Authorization: Bearer <admin_token>" -X GET https://<apigw_endpoint>/chat-assistant-stacks/{stackId}
```

#### Response Example

```json
{
  "stackId": "abc-123-def",
  "name": "Developer Assistant",
  "description": "Preconfigured for code-related tasks.",
  "modelIds": ["mistral-vllm"],
  "repositoryIds": ["repo-1"],
  "collectionIds": ["coll-1"],
  "mcpServerIds": [],
  "mcpToolIds": [],
  "personaPromptId": "prompt-1",
  "directivePromptIds": ["dir-1"],
  "allowedGroups": ["developers"],
  "isActive": true,
  "created": "2024-01-15T10:00:00Z",
  "updated": "2024-01-15T10:00:00Z"
}
```

---

### Create Stack

Creates a new Chat Assistant Stack. Admin only. The `stackId` is auto-generated if not provided.

#### Request Example

```bash
curl -s -H "Authorization: Bearer <admin_token>" -H "Content-Type: application/json" \
  -X POST https://<apigw_endpoint>/chat-assistant-stacks \
  -d '{
    "name": "Developer Assistant",
    "description": "Preconfigured for code-related tasks.",
    "modelIds": ["mistral-vllm"],
    "repositoryIds": [],
    "collectionIds": [],
    "mcpServerIds": [],
    "mcpToolIds": [],
    "directivePromptIds": [],
    "allowedGroups": ["developers"]
  }'
```

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Display name (max 256 characters) |
| `description` | string | Yes | Description of the assistant |
| `modelIds` | string[] | Yes | At least one model ID |
| `repositoryIds` | string[] | No | RAG repository IDs (default: []) |
| `collectionIds` | string[] | No | RAG collection IDs (default: []) |
| `mcpServerIds` | string[] | No | MCP server IDs (default: []) |
| `mcpToolIds` | string[] | No | MCP tool IDs (default: []) |
| `personaPromptId` | string \| null | No | Persona prompt ID |
| `directivePromptIds` | string[] | No | Directive prompt IDs (default: []) |
| `allowedGroups` | string[] | No | User groups (default: [], meaning global) |

#### Response

Returns the created stack object (same structure as Get Stack).

---

### Update Stack

Updates an existing stack. Admin only. Send the full stack payload (same shape as create); the stack is replaced with the provided values.

#### Request Example

```bash
curl -s -H "Authorization: Bearer <admin_token>" -H "Content-Type: application/json" \
  -X PUT https://<apigw_endpoint>/chat-assistant-stacks/{stackId} \
  -d '{
    "name": "Updated Developer Assistant",
    "description": "Updated description.",
    "modelIds": ["mistral-vllm", "another-model"],
    "repositoryIds": ["repo-1"],
    "collectionIds": [],
    "mcpServerIds": [],
    "mcpToolIds": [],
    "directivePromptIds": [],
    "allowedGroups": ["developers", "qa"]
  }'
```

#### Request Body

Same as [Create Stack](#create-stack) request body. All fields are required.

#### Response

Returns the updated stack object.

---

### Delete Stack

Deletes a Chat Assistant Stack. Admin only. This removes the stack from the system; users can no longer start new sessions from it.

#### Request Example

```bash
curl -s -H "Authorization: Bearer <admin_token>" -X DELETE https://<apigw_endpoint>/chat-assistant-stacks/{stackId}
```

#### Response Example

```json
{
  "status": "ok"
}
```

---

### Update Stack Status (Activate/Deactivate)

Activates or deactivates a stack. Admin only. Deactivated stacks are hidden from users but remain in the system and can be reactivated.

#### Request Example

```bash
curl -s -H "Authorization: Bearer <admin_token>" -H "Content-Type: application/json" \
  -X PUT https://<apigw_endpoint>/chat-assistant-stacks/{stackId}/status \
  -d '{"isActive": false}'
```

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `isActive` | boolean | Yes | `true` to activate, `false` to deactivate |

#### Response

Returns the updated stack object with the new `isActive` value.

---

## Summary

| Role | Where | What you do |
|------|--------|-------------|
| **Admin** | Configuration → Advanced | Enable **Chat Assistant Stacks**. |
| **Admin** | Administration → Chat Assistant Stack Management | Create, edit, delete stacks; activate/deactivate; search by name/description. |
| **User** | Chat UI left pane → Chat Assistants | See available assistants; click to open a preconfigured session. |
| **User** | Session | Use preconfigured models, RAG, MCP, prompts; choose among options when allowed; |

For configuration schema, see the LISA configuration documentation. For using the Chat UI in general, see [LISA Chat UI](/user/chat).

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

## Summary

| Role | Where | What you do |
|------|--------|-------------|
| **Admin** | Configuration → Advanced | Enable **Chat Assistant Stacks**. |
| **Admin** | Administration → Chat Assistant Stack Management | Create, edit, delete stacks; activate/deactivate; search by name/description. |
| **User** | Chat UI left pane → Chat Assistants | See available assistants; click to open a preconfigured session. |
| **User** | Session | Use preconfigured models, RAG, MCP, prompts; choose among options when allowed; |

For configuration schema and API details, see the LISA configuration and API documentation. For using the Chat UI in general, see [LISA Chat UI](/user/chat).

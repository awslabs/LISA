# Configuration UI

The Configuration UI is an Administrator-only page accessible via `Administration` &#8594; `Configuration`. It provides runtime control over platform features, system banners, and announcements — all without redeployment. Changes take effect immediately after saving.

## Chat Features

The Chat Features section contains toggles that control which capabilities are available to users in the Chat UI. Features are organized into the following groups:

### RAG
| Toggle | Description |
|--------|-------------|
| Document upload from Chat | Allows users to upload documents directly from the chat interface for RAG queries. See [RAG Repository](/config/repositories) for collection setup. |
| Edit number of referenced documents | Lets users adjust how many RAG documents are referenced during inference. |

### Library
| Toggle | Description |
|--------|-------------|
| Model Library | Exposes the [Model Library](/user/model-library) page where users can browse available models. |
| Document Library | Exposes the [Document Library](/user/document-library) page for managing RAG document collections. |
| Prompt Template Library | Exposes the Prompt Template Library for creating and managing reusable prompt templates. |

### In-Context
| Toggle | Description |
|--------|-------------|
| Document upload to context | Allows users to upload documents directly into the conversation context. |
| Document Summarization | Enables document summarization capabilities within chat sessions. |

### Advanced
| Toggle | Description |
|--------|-------------|
| Edit model arguments | Allows users to modify model inference parameters (temperature, top_p, etc.). |
| Update Prompt Template | Lets users change the prompt template used for a chat session. |
| View chat meta-data | Displays metadata (token counts, latency, etc.) alongside chat responses. |
| Delete Session History | Allows users to delete their own chat session history. |
| Edit chat history buffer | Lets users adjust the number of previous messages sent as context. |
| Model Comparison Utility | Enables side-by-side model comparison in the chat interface. |
| Session Encryption | Encrypts chat session data using KMS. |
| Chat Assistant Stacks | Enables the [Chat Assistant Stacks](/config/chat-assistant-stacks) feature for pre-configured assistant workflows. |

### MCP
| Toggle | Description |
|--------|-------------|
| MCP Server Connections | Enables users to configure [MCP server connections](/config/mcp). See also [LISA MCP: Self-host servers](/config/hosted-mcp). |
| MCP Workbench | Provides an experimentation workbench for MCP tools. See [MCP Workbench](/config/mcp-workbench). Requires MCP Server Connections to be enabled first. |

### API Tokens
| Toggle | Description |
|--------|-------------|
| User managed API tokens | Allows users to create and manage their own API tokens for programmatic access to LISA Serve. See [API Token Management](/config/api-tokens). |

> [!NOTE]
> Some toggles have dependencies. For example, MCP Workbench requires MCP Server Connections to be enabled. Disabling a prerequisite toggle will automatically disable its dependents.

## System Banner

The System Banner displays a persistent, colored banner across the top of the LISA UI for all users. This is useful for environment indicators (e.g., "STAGING"), maintenance notices, or security classification markings.

### Configuration

| Field | Description |
|-------|-------------|
| Banner Text | The message displayed in the banner. |
| Activate System Banner | Toggle to show or hide the banner. |
| Text Color | Color picker for the banner text. |
| Background Color | Color picker for the banner background. |

The banner is always visible when enabled and cannot be dismissed by users.

## Announcements

Announcements allow Administrators to broadcast a dismissable notification message to all LISA users. Unlike the system banner, announcements appear as an informational notification that users can dismiss.

### Configuration

| Field | Description |
|-------|-------------|
| Activate Announcement | Toggle to enable or disable the announcement. |
| Announcement Message | The message displayed to users. Required when the announcement is activated. |

### Behavior

- Announcements appear as an info-level notification banner prefixed with "📢 Announcement:"
- Users can dismiss the notification; dismissal is stored in the browser's localStorage
- If the Administrator updates the message (triggering a new configuration save), previously dismissed notifications reappear for all users
- Disabling the toggle removes the notification for all users on their next page load

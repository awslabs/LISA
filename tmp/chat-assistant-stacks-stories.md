# User Stories: LISA Configurable Chat Assistant Stacks

## Background

Customers (e.g. Thorben, GA) need to bundle models, repos, MCP servers, and prompt templates. LISA Admins can configure **Chat Assistant Stacks** and control access via enterprise user groups. Users see stacks they have access to and open preconfigured chat sessions from them.

---

## Administrator Stories

### Configuration & Visibility

- **AS-1** As an Admin, I can activate the **Chat Assistant Stacks** toggle on LISA’s **Configuration** page so that the feature is available in my org.
  - Toggle lives under the **Advanced** section.

- **AS-2** As an Admin, when Chat Assistant Stacks is activated, I see a **Chat Assistant Stack Management** selection in **Administration** drop down the so that I can manage stacks.
  - Page shows stacks as cards (à la Model Management).
  - Page includes: **Refresh** button, **Actions** button, **Create Stack** button.

- **AS-3** As an Admin, I can search stacks by name orS description so that I can find stacks quickly.

### CRUD & Lifecycle

- **AS-4** As an Admin, I can create a new Chat Assistant Stack so that users can use a preconfigured assistant.
  - Form includes all fields and steps defined in the form table below.

- **AS-5** As an Admin, I can update an existing stack (all updateable fields) so that configurations stay current.

- **AS-6** As an Admin, I can delete a stack so that it is removed from the system.

- **AS-7** As an Admin, I can **activate** or **deactivate** a stack so that I control availability without losing configuration.
  - Deactivated stacks are no longer available to users but remain visible and editable to Admins.

### Stack Form Fields (Create/Update)

| Field Name           | Type / Component | Multi-select? | Required? | Form Step | Updateable? | Notes |
|----------------------|------------------|---------------|-----------|-----------|-------------|-------|
| Stack Assistant Name | Text             | No            | Yes       | —         | Yes         | Shown to users. Enforce a size limit. |
| Description          | Text             | No            | Yes       | —         | Yes         | |
| Models               | Multiselect (e.g. Cloudscape) | Yes | Yes (≥1)  | Models    | Yes         | Any model, including embeddings (e.g. RAG). No default (users may not have access to all models). |
| Repos                | Multiselect      | Yes           | No (0 or ≥1) | RAG      | Yes         | |
| Collections          | Multiselect      | Yes           | No (0 or ≥1) | RAG      | Yes         | |
| MCP Servers          | Multiselect      | Yes           | No (0 or ≥1) | Agents   | Yes         | From LISA MCP, Workbench, or Connections. If ≥1 selected, at least one model must support MCP tools. |
| MCP Tools            | Multiselect      | Yes           | No (0 or ≥1) | Agents   | Yes         | |
| Persona Prompts      | Single select    | No (1 only)   | —         | Prompts    | Yes         | Applied in the background to the stack (e.g. developer persona). Consider “Assistant only” prompts (hidden from library). |
| Directive Prompts    | Multiselect      | Yes           | No (0 or ≥1) | Prompts  | Yes         | User can select from these. Consider “Assistant only” prompts (hidden from library). |
| Allowed Groups       | Multiselect      | Yes           | No (0 or ≥1) | Access   | Yes         | Use LISA standard group selection. If 0 groups, stack is global. Users only see resources they have access to. |

### Validation & Rules

- **AS-8** As an Admin, I am prevented from saving a stack without a **Stack Assistant Name** and **Description** (required), and with at least one **Model** selected.
- **AS-9** As an Admin, when I select at least one **MCP Server**, the system ensures at least one selected **Model** supports MCP tools (validation or guidance in UI).

---

## User Stories

### Discovery & Access

- **US-1** As a User, I see a **Chat Assistants** section in the left pane so that I can discover available assistants.
  - Section appears **above** the **History** search bar.
  - When expanded, I see only stacks I have access to (via Allowed Groups and resource permissions).

- **US-2** As a User, when I click a Chat Assistant, a new chat session opens so that I can start chatting with that assistant.
  - Session is preconfigured with the Admin’s stack selections (models, repos, collections, MCP, prompts, etc.).

### Choices Within a Stack

- **US-3** As a User, when a stack has multi-select options and I have access to all of them, I can choose what to use (e.g. change models, repos, collections) so that I can tailor the session when allowed.
  - Once I select a model, I cannot change it for that session (consistent with existing LISA behavior).

### Session & History

- **US-4** As a User, when I start using an Assistant, the session is saved under **History** so that I can return to it later.
  - Session name format: **[Name of assistant] + initial prompt** (same pattern as usual).
  - I can rename sessions. Session behavior matches existing behavior (e.g. access historic sessions, delete if supported).

---

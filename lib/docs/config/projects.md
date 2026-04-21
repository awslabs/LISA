# Project Organization

LISA's chat session Project Organization feature allows customers to group related chat sessions into named folders for better organization.

## Activating Chat Session Projects

Project Organization is deactivated by default. To activate:

1. Navigate to **Configuration** in the LISA UI
2. Go to the **Advanced** section
3. Toggle **Project Organization** to activate
4. Click **Save**

Once activated, users will see a **History / Projects** toggle in the chat sidebar.

## Configuration Options

| Setting | Default | Description |
|---------|---------|-------------|
| `projectOrganization` | `false` | Activate or deactivate the Projects feature |
| `maxProjectsPerUser` | `50` | Maximum number of Projects a user can create |

The `maxProjectsPerUser` limit can be adjusted based on your organization's needs. The limit is enforced server-side.

## User Guide

### Switching Between Views

When the Projects feature is activated, a toggle appears in the chat sidebar with two options:
- **History** — The default chronological view of all sessions
- **Projects** — A folder-based view showing Projects and their assigned sessions

The selected view persists across browser sessions.

### Creating Project folders

1. Switch to the **Projects** view
2. Click the **New** dropdown button
3. Select **New Project**
4. Enter a project name (1–100 characters)
5. Click **Create**

### Assigning Sessions to Projects folders

From the **History** view:

1. Find the session you want to assign
2. Click the actions menu (three-dot icon) on the session row
3. Hover over **Add to Project**
4. Select the target Project

Once assigned, sessions display a blue badge with the Project's name in the users's chat session history. The Project will also appear in the Projects view.

::: tip
A session can only belong to one Project at a time.
:::

### Removing Sessions from Project folder

- **From History**: Click the session's actions menu and select **Remove from Project**
- **From Projects**: Click the close button (X) on the session row

The session remains in History and can be reassigned to another Project.

### Managing Projects

Each Project has an actions menu with:

- **Rename** — Change the project name
- **Delete** — Two options:
  - **Delete Project only** — Sessions return to History (unassigned)
  - **Delete Project and sessions** — Project and all sessions are permanently deleted

## Data Retention

- Disabling the Projects feature preserves all Project assignments in the database
- Re-enabling the feature restores sessions to their previously assigned Projects
- Project metadata (`projectId`) is stored separately from encrypted session content

## API Reference

The Projects API allows programmatic management of Projects and session assignments. All endpoints are scoped to the authenticated user.

**Base URL**: `https://<your-lisa-domain>/project`

### List Projects

Retrieve all Projects for the current user.

```bash
GET /project
Authorization: Bearer <your-token>
```

**Response (200 OK):**

```json
[
  {
    "userId": "user-123",
    "projectId": "proj-abc123",
    "name": "Research Notes",
    "createTime": "2024-01-15T10:30:00Z",
    "lastUpdated": "2024-01-20T14:22:00Z"
  }
]
```

### Create Project

Create a new Project.

```bash
POST /project
Content-Type: application/json
Authorization: Bearer <your-token>

{
  "name": "My New Project"
}
```

**Request Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | Yes | Project name (1–100 characters) |

**Response (200 OK):**

```json
{
  "userId": "user-123",
  "projectId": "proj-def456",
  "name": "My New Project",
  "createTime": "2024-01-21T09:00:00Z",
  "lastUpdated": "2024-01-21T09:00:00Z"
}
```

**Error Responses:**

- `400 Bad Request`: Project limit reached (`maxProjectsPerUser`)
- `400 Bad Request`: Invalid Project name (empty or exceeds 100 characters)

### Rename Project

Update a Project's name.

```bash
PUT /project/{projectId}
Content-Type: application/json
Authorization: Bearer <your-token>

{
  "name": "Updated Project Name"
}
```

**Response (200 OK):**

```json
{
  "message": "Project renamed successfully"
}
```

**Error Responses:**

- `404 Not Found`: Project does not exist or belongs to another user

### Delete Project

Delete a Project with options for handling assigned sessions.

```bash
DELETE /project/{projectId}
Content-Type: application/json
Authorization: Bearer <your-token>

{
  "deleteSessions": false
}
```

**Request Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `deleteSessions` | boolean | `false` | If `true`, permanently delete all sessions assigned to the Project. If `false`, sessions are unassigned and remain in History. |

**Response (200 OK):**

```json
{
  "deleted": true
}
```

**Error Responses:**

- `404 Not Found`: Project does not exist or belongs to another user

### Assign Session to Project

Assign or remove a session to a Project.

```bash
PUT /project/{projectId}/session/{sessionId}
Content-Type: application/json
Authorization: Bearer <your-token>

{
  "unassign": false
}
```

**Request Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `unassign` | boolean | `false` | If `true`, removes the session from the Project. If `false`, assigns the session to the Project. |

**Response (200 OK):**

```json
{
  "message": "Session assignment updated successfully"
}
```

**Error Responses:**

- `404 Not Found`: Session or Project does not exist or belongs to another user
- `409 Conflict`: Project is being deleted

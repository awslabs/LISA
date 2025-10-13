# Collection Management API

The Collection Management API provides endpoints for creating, reading, updating, and deleting collections within RAG vector stores. Collections enable organizing documents with different chunking strategies and access controls without requiring infrastructure changes.

## Base URL Structure

All collection endpoints are accessed through LISA's main API Gateway with the following structure:
```
https://{API-GATEWAY-DOMAIN}/{STAGE}/repository/{repositoryId}/collection
```

## Authentication

All API endpoints require proper authentication through LISA's configured authorization mechanism. Ensure your requests include valid authorization headers as configured in your LISA deployment.

## Endpoints

### Create Collection

Create a new collection within a vector store.

**Endpoint:** `POST /repository/{repositoryId}/collection`

**Path Parameters:**
- `repositoryId` (string, required): The parent vector store repository ID

**Request Body:**

```json
{
  "name": "Legal Documents",
  "description": "Collection for legal contracts and agreements",
  "chunkingStrategy": {
    "type": "RECURSIVE",
    "parameters": {
      "chunkSize": 1000,
      "chunkOverlap": 200,
      "separators": ["\n\n", "\n", ". ", " "]
    }
  },
  "allowedGroups": ["legal-team", "compliance"],
  "metadata": {
    "tags": ["legal", "contracts", "confidential"]
  },
  "private": false,
  "allowChunkingOverride": true
}
```

**Request Body Schema:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Collection name (1-100 characters) |
| `description` | string | No | Collection description |
| `embeddingModel` | string | No | Embedding model ID (inherits from parent if omitted) |
| `chunkingStrategy` | object | No | Chunking strategy configuration (inherits from parent if omitted) |
| `chunkingStrategy.type` | enum | No | Strategy type: `FIXED_SIZE`, `SEMANTIC`, or `RECURSIVE` |
| `chunkingStrategy.parameters` | object | No | Strategy-specific parameters |
| `allowedGroups` | array[string] | No | User groups with access (inherits from parent if omitted) |
| `metadata` | object | No | Collection-specific metadata |
| `metadata.tags` | array[string] | No | Metadata tags (max 50 tags, 50 chars each) |
| `private` | boolean | No | Whether collection is private to creator (default: false) |
| `allowChunkingOverride` | boolean | No | Allow chunking strategy override during ingestion (default: true) |
| `pipelines` | array[object] | No | Automated ingestion pipelines |

**Chunking Strategy Types:**

1. **FIXED_SIZE**: Fixed-size chunks with overlap
   ```json
   {
     "type": "FIXED_SIZE",
     "parameters": {
       "chunkSize": 1000,
       "chunkOverlap": 200
     }
   }
   ```

2. **SEMANTIC**: Semantic-based chunking
   ```json
   {
     "type": "SEMANTIC",
     "parameters": {
       "threshold": 0.5
     }
   }
   ```

3. **RECURSIVE**: Recursive text splitting with custom separators
   ```json
   {
     "type": "RECURSIVE",
     "parameters": {
       "chunkSize": 1000,
       "chunkOverlap": 200,
       "separators": ["\n\n", "\n", ". ", " "]
     }
   }
   ```

**Response (200 OK):**

```json
{
  "collectionId": "550e8400-e29b-41d4-a716-446655440000",
  "repositoryId": "repo-123",
  "name": "Legal Documents",
  "description": "Collection for legal contracts and agreements",
  "chunkingStrategy": {
    "type": "RECURSIVE",
    "parameters": {
      "chunkSize": 1000,
      "chunkOverlap": 200,
      "separators": ["\n\n", "\n", ". ", " "]
    }
  },
  "allowChunkingOverride": true,
  "metadata": {
    "tags": ["legal", "contracts", "confidential"]
  },
  "allowedGroups": ["legal-team", "compliance"],
  "embeddingModel": "amazon.titan-embed-text-v1",
  "createdBy": "user-456",
  "createdAt": "2025-10-13T10:30:00Z",
  "updatedAt": "2025-10-13T10:30:00Z",
  "status": "ACTIVE",
  "private": false,
  "pipelines": []
}
```

**Error Responses:**

| Status Code | Description | Example |
|-------------|-------------|---------|
| 400 | Bad Request - Invalid input | `{"error": "Collection name must be unique within repository"}` |
| 403 | Forbidden - Insufficient permissions | `{"error": "User does not have write access to repository"}` |
| 404 | Not Found - Repository not found | `{"error": "Repository 'repo-123' not found"}` |
| 500 | Internal Server Error | `{"error": "Failed to create collection"}` |

**Example cURL Request:**

```bash
curl -X POST "https://{API-GATEWAY-DOMAIN}/{STAGE}/repository/repo-123/collection" \
  -H "Authorization: Bearer {YOUR_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Legal Documents",
    "description": "Collection for legal contracts and agreements",
    "chunkingStrategy": {
      "type": "RECURSIVE",
      "parameters": {
        "chunkSize": 1000,
        "chunkOverlap": 200,
        "separators": ["\n\n", "\n", ". ", " "]
      }
    },
    "allowedGroups": ["legal-team", "compliance"],
    "metadata": {
      "tags": ["legal", "contracts", "confidential"]
    },
    "private": false
  }'
```

**Example Python Request:**

```python
import requests
import json

url = "https://{API-GATEWAY-DOMAIN}/{STAGE}/repository/repo-123/collection"
headers = {
    "Authorization": "Bearer {YOUR_TOKEN}",
    "Content-Type": "application/json"
}
payload = {
    "name": "Legal Documents",
    "description": "Collection for legal contracts and agreements",
    "chunkingStrategy": {
        "type": "RECURSIVE",
        "parameters": {
            "chunkSize": 1000,
            "chunkOverlap": 200,
            "separators": ["\n\n", "\n", ". ", " "]
        }
    },
    "allowedGroups": ["legal-team", "compliance"],
    "metadata": {
        "tags": ["legal", "contracts", "confidential"]
    },
    "private": False
}

response = requests.post(url, headers=headers, json=payload)
if response.status_code == 200:
    collection = response.json()
    print(f"Created collection: {collection['collectionId']}")
else:
    print(f"Error: {response.status_code} - {response.text}")
```

**Example JavaScript Request:**

```javascript
const url = 'https://{API-GATEWAY-DOMAIN}/{STAGE}/repository/repo-123/collection';
const headers = {
  'Authorization': 'Bearer {YOUR_TOKEN}',
  'Content-Type': 'application/json'
};
const payload = {
  name: 'Legal Documents',
  description: 'Collection for legal contracts and agreements',
  chunkingStrategy: {
    type: 'RECURSIVE',
    parameters: {
      chunkSize: 1000,
      chunkOverlap: 200,
      separators: ['\n\n', '\n', '. ', ' ']
    }
  },
  allowedGroups: ['legal-team', 'compliance'],
  metadata: {
    tags: ['legal', 'contracts', 'confidential']
  },
  private: false
};

fetch(url, {
  method: 'POST',
  headers: headers,
  body: JSON.stringify(payload)
})
  .then(response => {
    if (response.status === 200) {
      return response.json();
    }
    throw new Error(`Error: ${response.status}`);
  })
  .then(collection => {
    console.log(`Created collection: ${collection.collectionId}`);
  })
  .catch(error => {
    console.error('Error:', error);
  });
```

## Inheritance Rules

Collections inherit configuration from their parent vector store:

1. **Embedding Model**: If not specified, inherits from parent vector store
2. **Allowed Groups**: If not specified or empty array, inherits from parent vector store
3. **Chunking Strategy**: If not specified, inherits from parent vector store's first pipeline
4. **Metadata**: Merged with parent vector store metadata (collection tags take precedence)

## Validation Rules

### Collection Name
- Required for creation
- Maximum 100 characters
- Must be unique within repository
- Allowed characters: alphanumeric, spaces, hyphens, underscores

### Allowed Groups
- Must be subset of parent repository's allowed groups
- Empty array inherits from parent

### Chunking Strategy Parameters
- `chunkSize`: 100-10000
- `chunkOverlap`: 0 to chunkSize/2
- `separators`: non-empty array for RECURSIVE strategy

### Metadata Tags
- Maximum 50 tags per collection
- Each tag maximum 50 characters
- Allowed characters: alphanumeric, hyphens, underscores

## Access Control

### Permission Levels
- **Read**: View collection configuration, query documents
- **Write**: Upload documents, update collection metadata
- **Admin**: Delete collection, modify access control

### Access Rules
1. Admin users have full access to all collections
2. Non-admin users must have group membership intersection with collection's allowed groups
3. Private collections are only accessible to creator and admins
4. Vector stores with `allowUserCollections: false` prevent non-admin collection creation

## Best Practices

1. **Use Descriptive Names**: Choose clear, descriptive names for collections to make them easy to identify
2. **Organize by Content Type**: Create separate collections for different document types (e.g., legal, technical, marketing)
3. **Optimize Chunking Strategy**: Select chunking strategies appropriate for your content:
   - Use `FIXED_SIZE` for uniform documents
   - Use `SEMANTIC` for documents with clear semantic boundaries
   - Use `RECURSIVE` for documents with hierarchical structure
4. **Manage Access Control**: Use allowed groups to restrict access to sensitive collections
5. **Use Private Collections**: Mark collections as private for personal or temporary collections
6. **Tag Collections**: Use metadata tags for easier filtering and organization

## Troubleshooting

### Common Errors

**"Collection name must be unique within repository"**
- Solution: Choose a different name or check existing collections

**"User does not have write access to repository"**
- Solution: Ensure user is in one of the repository's allowed groups or is an admin

**"Allowed groups must be subset of parent repository groups"**
- Solution: Only specify groups that exist in the parent repository's allowed groups

**"Chunk size must be between 100 and 10000"**
- Solution: Adjust chunk size to be within the valid range

**"Cannot create collection: allowUserCollections is false"**
- Solution: Contact an administrator to enable user collections or have an admin create the collection

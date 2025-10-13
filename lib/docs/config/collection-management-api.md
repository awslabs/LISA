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

### Get Collection

Retrieve a collection by ID within a vector store.

**Endpoint:** `GET /repository/{repositoryId}/collection/{collectionId}`

**Path Parameters:**
- `repositoryId` (string, required): The parent vector store repository ID
- `collectionId` (string, required): The collection ID (UUID)

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
| 403 | Forbidden - Insufficient permissions | `{"error": "Permission denied: User does not have read access to collection"}` |
| 404 | Not Found - Collection not found | `{"error": "Collection '550e8400-e29b-41d4-a716-446655440000' not found"}` |
| 404 | Not Found - Repository not found | `{"error": "Repository 'repo-123' not found"}` |
| 500 | Internal Server Error | `{"error": "Failed to retrieve collection"}` |

**Example cURL Request:**

```bash
curl -X GET "https://{API-GATEWAY-DOMAIN}/{STAGE}/repository/repo-123/collection/550e8400-e29b-41d4-a716-446655440000" \
  -H "Authorization: Bearer {YOUR_TOKEN}"
```

**Example Python Request:**

```python
import requests

url = "https://{API-GATEWAY-DOMAIN}/{STAGE}/repository/repo-123/collection/550e8400-e29b-41d4-a716-446655440000"
headers = {
    "Authorization": "Bearer {YOUR_TOKEN}"
}

response = requests.get(url, headers=headers)
if response.status_code == 200:
    collection = response.json()
    print(f"Collection: {collection['name']}")
    print(f"Status: {collection['status']}")
    print(f"Allowed Groups: {collection['allowedGroups']}")
else:
    print(f"Error: {response.status_code} - {response.text}")
```

**Example JavaScript Request:**

```javascript
const url = 'https://{API-GATEWAY-DOMAIN}/{STAGE}/repository/repo-123/collection/550e8400-e29b-41d4-a716-446655440000';
const headers = {
  'Authorization': 'Bearer {YOUR_TOKEN}'
};

fetch(url, {
  method: 'GET',
  headers: headers
})
  .then(response => {
    if (response.status === 200) {
      return response.json();
    }
    throw new Error(`Error: ${response.status}`);
  })
  .then(collection => {
    console.log(`Collection: ${collection.name}`);
    console.log(`Status: ${collection.status}`);
    console.log(`Allowed Groups: ${collection.allowedGroups}`);
  })
  .catch(error => {
    console.error('Error:', error);
  });
```

### Update Collection

Update a collection's configuration within a vector store. Supports partial updates - only specified fields will be modified.

**Endpoint:** `PUT /repository/{repositoryId}/collection/{collectionId}`

**Path Parameters:**
- `repositoryId` (string, required): The parent vector store repository ID
- `collectionId` (string, required): The collection ID (UUID)

**Request Body:**

All fields are optional. Only include fields you want to update.

```json
{
  "name": "Updated Legal Documents",
  "description": "Updated description for legal contracts",
  "chunkingStrategy": {
    "type": "FIXED_SIZE",
    "parameters": {
      "chunkSize": 1500,
      "chunkOverlap": 300
    }
  },
  "allowedGroups": ["legal-team", "compliance", "audit"],
  "metadata": {
    "tags": ["legal", "contracts", "confidential", "2025"]
  },
  "private": false,
  "allowChunkingOverride": true,
  "status": "ACTIVE"
}
```

**Request Body Schema:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | No | Collection name (1-100 characters) |
| `description` | string | No | Collection description |
| `chunkingStrategy` | object | No | Chunking strategy configuration |
| `chunkingStrategy.type` | enum | No | Strategy type: `FIXED_SIZE`, `SEMANTIC`, or `RECURSIVE` |
| `chunkingStrategy.parameters` | object | No | Strategy-specific parameters |
| `allowedGroups` | array[string] | No | User groups with access |
| `metadata` | object | No | Collection-specific metadata |
| `metadata.tags` | array[string] | No | Metadata tags (max 50 tags, 50 chars each) |
| `private` | boolean | No | Whether collection is private to creator |
| `allowChunkingOverride` | boolean | No | Allow chunking strategy override during ingestion |
| `pipelines` | array[object] | No | Automated ingestion pipelines |
| `status` | enum | No | Collection status: `ACTIVE`, `ARCHIVED`, or `DELETED` |

**Immutable Fields:**

The following fields cannot be modified after creation and will be ignored if included in the request:
- `collectionId`
- `repositoryId`
- `embeddingModel`
- `createdBy`
- `createdAt`

**Response (200 OK):**

```json
{
  "collection": {
    "collectionId": "550e8400-e29b-41d4-a716-446655440000",
    "repositoryId": "repo-123",
    "name": "Updated Legal Documents",
    "description": "Updated description for legal contracts",
    "chunkingStrategy": {
      "type": "FIXED_SIZE",
      "parameters": {
        "chunkSize": 1500,
        "chunkOverlap": 300
      }
    },
    "allowChunkingOverride": true,
    "metadata": {
      "tags": ["legal", "contracts", "confidential", "2025"]
    },
    "allowedGroups": ["legal-team", "compliance", "audit"],
    "embeddingModel": "amazon.titan-embed-text-v1",
    "createdBy": "user-456",
    "createdAt": "2025-10-13T10:30:00Z",
    "updatedAt": "2025-10-13T14:45:00Z",
    "status": "ACTIVE",
    "private": false,
    "pipelines": []
  },
  "warnings": [
    "Changing chunking strategy will only affect new documents. Existing documents will retain their original chunking. Consider re-ingesting existing documents if needed."
  ]
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `collection` | object | The updated collection configuration |
| `warnings` | array[string] | Optional warnings about the update (e.g., chunking strategy changes) |

**Error Responses:**

| Status Code | Description | Example |
|-------------|-------------|---------|
| 400 | Bad Request - Invalid input | `{"error": "Collection name must be unique within repository"}` |
| 403 | Forbidden - Insufficient permissions | `{"error": "Permission denied: User does not have write access to collection"}` |
| 404 | Not Found - Collection not found | `{"error": "Collection '550e8400-e29b-41d4-a716-446655440000' not found"}` |
| 404 | Not Found - Repository not found | `{"error": "Repository 'repo-123' not found"}` |
| 500 | Internal Server Error | `{"error": "Failed to update collection"}` |

**Example cURL Request:**

```bash
curl -X PUT "https://{API-GATEWAY-DOMAIN}/{STAGE}/repository/repo-123/collection/550e8400-e29b-41d4-a716-446655440000" \
  -H "Authorization: Bearer {YOUR_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Updated Legal Documents",
    "description": "Updated description for legal contracts",
    "metadata": {
      "tags": ["legal", "contracts", "confidential", "2025"]
    }
  }'
```

**Example Python Request:**

```python
import requests
import json

url = "https://{API-GATEWAY-DOMAIN}/{STAGE}/repository/repo-123/collection/550e8400-e29b-41d4-a716-446655440000"
headers = {
    "Authorization": "Bearer {YOUR_TOKEN}",
    "Content-Type": "application/json"
}
payload = {
    "name": "Updated Legal Documents",
    "description": "Updated description for legal contracts",
    "metadata": {
        "tags": ["legal", "contracts", "confidential", "2025"]
    }
}

response = requests.put(url, headers=headers, json=payload)
if response.status_code == 200:
    result = response.json()
    collection = result['collection']
    print(f"Updated collection: {collection['collectionId']}")
    print(f"New name: {collection['name']}")
    
    # Check for warnings
    if 'warnings' in result:
        print("Warnings:")
        for warning in result['warnings']:
            print(f"  - {warning}")
else:
    print(f"Error: {response.status_code} - {response.text}")
```

**Example JavaScript Request:**

```javascript
const url = 'https://{API-GATEWAY-DOMAIN}/{STAGE}/repository/repo-123/collection/550e8400-e29b-41d4-a716-446655440000';
const headers = {
  'Authorization': 'Bearer {YOUR_TOKEN}',
  'Content-Type': 'application/json'
};
const payload = {
  name: 'Updated Legal Documents',
  description: 'Updated description for legal contracts',
  metadata: {
    tags: ['legal', 'contracts', 'confidential', '2025']
  }
};

fetch(url, {
  method: 'PUT',
  headers: headers,
  body: JSON.stringify(payload)
})
  .then(response => {
    if (response.status === 200) {
      return response.json();
    }
    throw new Error(`Error: ${response.status}`);
  })
  .then(result => {
    const collection = result.collection;
    console.log(`Updated collection: ${collection.collectionId}`);
    console.log(`New name: ${collection.name}`);
    
    // Check for warnings
    if (result.warnings) {
      console.log('Warnings:');
      result.warnings.forEach(warning => {
        console.log(`  - ${warning}`);
      });
    }
  })
  .catch(error => {
    console.error('Error:', error);
  });
```

**Partial Update Example:**

You can update just one field without affecting others:

```bash
# Update only the description
curl -X PUT "https://{API-GATEWAY-DOMAIN}/{STAGE}/repository/repo-123/collection/550e8400-e29b-41d4-a716-446655440000" \
  -H "Authorization: Bearer {YOUR_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "New description only"
  }'
```

**Chunking Strategy Change Warning:**

When updating the chunking strategy on a collection that already has documents, the API will return a warning:

```json
{
  "collection": { ... },
  "warnings": [
    "Changing chunking strategy will only affect new documents. Existing documents will retain their original chunking. Consider re-ingesting existing documents if needed."
  ]
}
```

This warning indicates that:
1. New documents uploaded after the change will use the new chunking strategy
2. Existing documents will keep their original chunking
3. You may want to re-ingest existing documents to apply the new strategy

### Delete Collection

Delete a collection within a vector store. This operation requires admin access and will remove all associated documents from S3 and the vector store.

**Endpoint:** `DELETE /repository/{repositoryId}/collection/{collectionId}`

**Path Parameters:**
- `repositoryId` (string, required): The parent vector store repository ID
- `collectionId` (string, required): The collection ID (UUID)

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `hardDelete` | boolean | No | false | Whether to permanently delete (true) or soft delete (false) |

**Deletion Behavior:**

- **Soft Delete (default)**: Marks the collection status as `DELETED` but retains the record in the database
- **Hard Delete**: Permanently removes the collection record from the database
- **Document Cleanup**: Both deletion types remove all associated documents from:
  - S3 storage
  - DynamoDB document table
  - Vector store embeddings

**Response (204 No Content):**

No response body is returned on successful deletion.

**Error Responses:**

| Status Code | Description | Example |
|-------------|-------------|---------|
| 400 | Bad Request - Cannot delete default collection | `{"error": "Cannot delete the default collection"}` |
| 403 | Forbidden - Insufficient permissions | `{"error": "Permission denied: User does not have admin access to collection"}` |
| 404 | Not Found - Collection not found | `{"error": "Collection '550e8400-e29b-41d4-a716-446655440000' not found"}` |
| 404 | Not Found - Repository not found | `{"error": "Repository 'repo-123' not found"}` |
| 500 | Internal Server Error | `{"error": "Failed to delete collection"}` |

**Example cURL Request (Soft Delete):**

```bash
curl -X DELETE "https://{API-GATEWAY-DOMAIN}/{STAGE}/repository/repo-123/collection/550e8400-e29b-41d4-a716-446655440000" \
  -H "Authorization: Bearer {YOUR_TOKEN}"
```

**Example cURL Request (Hard Delete):**

```bash
curl -X DELETE "https://{API-GATEWAY-DOMAIN}/{STAGE}/repository/repo-123/collection/550e8400-e29b-41d4-a716-446655440000?hardDelete=true" \
  -H "Authorization: Bearer {YOUR_TOKEN}"
```

**Example Python Request:**

```python
import requests

url = "https://{API-GATEWAY-DOMAIN}/{STAGE}/repository/repo-123/collection/550e8400-e29b-41d4-a716-446655440000"
headers = {
    "Authorization": "Bearer {YOUR_TOKEN}"
}

# Soft delete (default)
response = requests.delete(url, headers=headers)
if response.status_code == 204:
    print("Collection soft deleted successfully")
else:
    print(f"Error: {response.status_code} - {response.text}")

# Hard delete
params = {"hardDelete": "true"}
response = requests.delete(url, headers=headers, params=params)
if response.status_code == 204:
    print("Collection permanently deleted")
else:
    print(f"Error: {response.status_code} - {response.text}")
```

**Example JavaScript Request:**

```javascript
const url = 'https://{API-GATEWAY-DOMAIN}/{STAGE}/repository/repo-123/collection/550e8400-e29b-41d4-a716-446655440000';
const headers = {
  'Authorization': 'Bearer {YOUR_TOKEN}'
};

// Soft delete (default)
fetch(url, {
  method: 'DELETE',
  headers: headers
})
  .then(response => {
    if (response.status === 204) {
      console.log('Collection soft deleted successfully');
    } else {
      throw new Error(`Error: ${response.status}`);
    }
  })
  .catch(error => {
    console.error('Error:', error);
  });

// Hard delete
const hardDeleteUrl = `${url}?hardDelete=true`;
fetch(hardDeleteUrl, {
  method: 'DELETE',
  headers: headers
})
  .then(response => {
    if (response.status === 204) {
      console.log('Collection permanently deleted');
    } else {
      throw new Error(`Error: ${response.status}`);
    }
  })
  .catch(error => {
    console.error('Error:', error);
  });
```

**Important Notes:**

1. **Admin Access Required**: Only users with admin access to the collection can delete it
2. **Default Collection Protection**: The default collection (based on embedding model ID) cannot be deleted
3. **Document Cleanup**: All documents in the collection will be removed from S3, DynamoDB, and the vector store
4. **Irreversible Operation**: Hard delete is permanent and cannot be undone
5. **Soft Delete Recovery**: Soft-deleted collections can be restored by updating the status back to `ACTIVE`

**Deletion Confirmation Workflow:**

Before deleting a collection, it's recommended to:

1. **Check document count**: Use the GET endpoint to see how many documents will be affected
2. **Warn users**: Display a confirmation dialog showing the collection name and document count
3. **Require confirmation**: Ask users to type the collection name to confirm deletion
4. **Log the action**: Ensure audit logs capture who deleted the collection and when

**Example Confirmation Flow:**

```python
import requests

def delete_collection_with_confirmation(repository_id, collection_id, token):
    """Delete a collection with user confirmation."""
    url = f"https://{{API-GATEWAY-DOMAIN}}/{{STAGE}}/repository/{repository_id}/collection/{collection_id}"
    headers = {"Authorization": f"Bearer {token}"}
    
    # Step 1: Get collection details
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Error fetching collection: {response.status_code}")
        return False
    
    collection = response.json()
    collection_name = collection['name']
    
    # Step 2: Get document count (from list_docs endpoint)
    docs_url = f"https://{{API-GATEWAY-DOMAIN}}/{{STAGE}}/repository/{repository_id}/documents"
    docs_response = requests.get(
        docs_url,
        headers=headers,
        params={"collectionId": collection_id, "pageSize": 1}
    )
    
    doc_count = 0
    if docs_response.status_code == 200:
        doc_count = docs_response.json().get('totalDocuments', 0)
    
    # Step 3: Display warning and get confirmation
    print(f"\nWARNING: You are about to delete collection '{collection_name}'")
    print(f"This will remove {doc_count} documents from S3 and the vector store.")
    print("This action cannot be undone.")
    
    confirmation = input(f"\nType the collection name '{collection_name}' to confirm: ")
    
    if confirmation != collection_name:
        print("Deletion cancelled - name did not match")
        return False
    
    # Step 4: Delete the collection
    response = requests.delete(url, headers=headers)
    if response.status_code == 204:
        print(f"Collection '{collection_name}' deleted successfully")
        return True
    else:
        print(f"Error deleting collection: {response.status_code} - {response.text}")
        return False

# Usage
delete_collection_with_confirmation(
    "repo-123",
    "550e8400-e29b-41d4-a716-446655440000",
    "{YOUR_TOKEN}"
)
```

### List Collections

List collections in a repository with pagination, filtering, and sorting.

**Endpoint:** `GET /repository/{repositoryId}/collections`

**Path Parameters:**
- `repositoryId` (string, required): The parent vector store repository ID

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `pageSize` | integer | No | 20 | Number of items per page (max: 100) |
| `filter` | string | No | - | Text filter for name/description (substring match) |
| `status` | enum | No | - | Status filter: `ACTIVE`, `ARCHIVED`, or `DELETED` |
| `sortBy` | enum | No | `createdAt` | Sort field: `name`, `createdAt`, or `updatedAt` |
| `sortOrder` | enum | No | `desc` | Sort order: `asc` or `desc` |
| `lastEvaluatedKeyCollectionId` | string | No | - | Pagination token: collection ID from previous response |
| `lastEvaluatedKeyRepositoryId` | string | No | - | Pagination token: repository ID from previous response |
| `lastEvaluatedKeyStatus` | string | No | - | Pagination token: status from previous response (if status filter used) |
| `lastEvaluatedKeyCreatedAt` | string | No | - | Pagination token: createdAt from previous response |

**Response (200 OK):**

```json
{
  "collections": [
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
    },
    {
      "collectionId": "660e8400-e29b-41d4-a716-446655440001",
      "repositoryId": "repo-123",
      "name": "Technical Documentation",
      "description": "Collection for technical manuals and guides",
      "chunkingStrategy": {
        "type": "FIXED_SIZE",
        "parameters": {
          "chunkSize": 1500,
          "chunkOverlap": 300
        }
      },
      "allowChunkingOverride": true,
      "metadata": {
        "tags": ["technical", "documentation"]
      },
      "allowedGroups": ["engineering", "support"],
      "embeddingModel": "amazon.titan-embed-text-v1",
      "createdBy": "user-789",
      "createdAt": "2025-10-12T15:20:00Z",
      "updatedAt": "2025-10-12T15:20:00Z",
      "status": "ACTIVE",
      "private": false,
      "pipelines": []
    }
  ],
  "pagination": {
    "totalCount": 45,
    "currentPage": 1,
    "totalPages": 3
  },
  "lastEvaluatedKey": {
    "collectionId": "660e8400-e29b-41d4-a716-446655440001",
    "repositoryId": "repo-123",
    "createdAt": "2025-10-12T15:20:00Z"
  },
  "hasNextPage": true,
  "hasPreviousPage": false
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `collections` | array[object] | List of collection configurations |
| `pagination` | object | Pagination metadata |
| `pagination.totalCount` | integer | Total number of collections (null if filters applied) |
| `pagination.currentPage` | integer | Current page number (null if using lastEvaluatedKey) |
| `pagination.totalPages` | integer | Total number of pages (null if filters applied) |
| `lastEvaluatedKey` | object | Pagination token for next page (null if no more pages) |
| `hasNextPage` | boolean | Whether there are more pages |
| `hasPreviousPage` | boolean | Whether there is a previous page |

**Access Control Filtering:**

- **Admin users**: See all collections in the repository
- **Non-admin users**: See only collections where:
  - User's groups intersect with collection's allowed groups, AND
  - Collection is not private OR user is the creator

**Error Responses:**

| Status Code | Description | Example |
|-------------|-------------|---------|
| 400 | Bad Request - Invalid parameters | `{"error": "Invalid sortBy value: invalid"}` |
| 403 | Forbidden - Insufficient permissions | `{"error": "Permission denied: User does not have read access to repository"}` |
| 404 | Not Found - Repository not found | `{"error": "Repository 'repo-123' not found"}` |
| 500 | Internal Server Error | `{"error": "Failed to list collections"}` |

**Example cURL Request (Basic):**

```bash
curl -X GET "https://{API-GATEWAY-DOMAIN}/{STAGE}/repository/repo-123/collections" \
  -H "Authorization: Bearer {YOUR_TOKEN}"
```

**Example cURL Request (With Filters):**

```bash
curl -X GET "https://{API-GATEWAY-DOMAIN}/{STAGE}/repository/repo-123/collections?pageSize=50&filter=legal&status=ACTIVE&sortBy=name&sortOrder=asc" \
  -H "Authorization: Bearer {YOUR_TOKEN}"
```

**Example cURL Request (Pagination):**

```bash
# First page
curl -X GET "https://{API-GATEWAY-DOMAIN}/{STAGE}/repository/repo-123/collections?pageSize=20" \
  -H "Authorization: Bearer {YOUR_TOKEN}"

# Next page (using lastEvaluatedKey from previous response)
curl -X GET "https://{API-GATEWAY-DOMAIN}/{STAGE}/repository/repo-123/collections?pageSize=20&lastEvaluatedKeyCollectionId=660e8400-e29b-41d4-a716-446655440001&lastEvaluatedKeyRepositoryId=repo-123&lastEvaluatedKeyCreatedAt=2025-10-12T15:20:00Z" \
  -H "Authorization: Bearer {YOUR_TOKEN}"
```

**Example Python Request:**

```python
import requests
import urllib.parse

url = "https://{API-GATEWAY-DOMAIN}/{STAGE}/repository/repo-123/collections"
headers = {
    "Authorization": "Bearer {YOUR_TOKEN}"
}

# Basic request
response = requests.get(url, headers=headers)
if response.status_code == 200:
    result = response.json()
    collections = result['collections']
    print(f"Found {len(collections)} collections")
    
    for collection in collections:
        print(f"  - {collection['name']} ({collection['collectionId']})")
    
    # Check for more pages
    if result['hasNextPage']:
        print("More pages available")
        last_key = result['lastEvaluatedKey']
        print(f"Next page token: {last_key}")
else:
    print(f"Error: {response.status_code} - {response.text}")

# Request with filters
params = {
    "pageSize": 50,
    "filter": "legal",
    "status": "ACTIVE",
    "sortBy": "name",
    "sortOrder": "asc"
}
response = requests.get(url, headers=headers, params=params)
if response.status_code == 200:
    result = response.json()
    print(f"Filtered results: {len(result['collections'])} collections")

# Pagination example
def get_all_collections(repository_id, page_size=20):
    """Fetch all collections with pagination."""
    all_collections = []
    last_evaluated_key = None
    
    while True:
        params = {"pageSize": page_size}
        
        # Add pagination token if available
        if last_evaluated_key:
            params["lastEvaluatedKeyCollectionId"] = last_evaluated_key["collectionId"]
            params["lastEvaluatedKeyRepositoryId"] = last_evaluated_key["repositoryId"]
            if "createdAt" in last_evaluated_key:
                params["lastEvaluatedKeyCreatedAt"] = last_evaluated_key["createdAt"]
        
        response = requests.get(
            f"https://{{API-GATEWAY-DOMAIN}}/{{STAGE}}/repository/{repository_id}/collections",
            headers=headers,
            params=params
        )
        
        if response.status_code != 200:
            print(f"Error: {response.status_code} - {response.text}")
            break
        
        result = response.json()
        all_collections.extend(result['collections'])
        
        # Check if there are more pages
        if not result['hasNextPage']:
            break
        
        last_evaluated_key = result['lastEvaluatedKey']
    
    return all_collections

# Get all collections
all_collections = get_all_collections("repo-123")
print(f"Total collections: {len(all_collections)}")
```

**Example JavaScript Request:**

```javascript
const url = 'https://{API-GATEWAY-DOMAIN}/{STAGE}/repository/repo-123/collections';
const headers = {
  'Authorization': 'Bearer {YOUR_TOKEN}'
};

// Basic request
fetch(url, {
  method: 'GET',
  headers: headers
})
  .then(response => {
    if (response.status === 200) {
      return response.json();
    }
    throw new Error(`Error: ${response.status}`);
  })
  .then(result => {
    const collections = result.collections;
    console.log(`Found ${collections.length} collections`);
    
    collections.forEach(collection => {
      console.log(`  - ${collection.name} (${collection.collectionId})`);
    });
    
    // Check for more pages
    if (result.hasNextPage) {
      console.log('More pages available');
      console.log('Next page token:', result.lastEvaluatedKey);
    }
  })
  .catch(error => {
    console.error('Error:', error);
  });

// Request with filters
const params = new URLSearchParams({
  pageSize: '50',
  filter: 'legal',
  status: 'ACTIVE',
  sortBy: 'name',
  sortOrder: 'asc'
});

fetch(`${url}?${params}`, {
  method: 'GET',
  headers: headers
})
  .then(response => response.json())
  .then(result => {
    console.log(`Filtered results: ${result.collections.length} collections`);
  })
  .catch(error => {
    console.error('Error:', error);
  });

// Pagination example
async function getAllCollections(repositoryId, pageSize = 20) {
  const allCollections = [];
  let lastEvaluatedKey = null;
  
  while (true) {
    const params = new URLSearchParams({ pageSize: pageSize.toString() });
    
    // Add pagination token if available
    if (lastEvaluatedKey) {
      params.append('lastEvaluatedKeyCollectionId', lastEvaluatedKey.collectionId);
      params.append('lastEvaluatedKeyRepositoryId', lastEvaluatedKey.repositoryId);
      if (lastEvaluatedKey.createdAt) {
        params.append('lastEvaluatedKeyCreatedAt', lastEvaluatedKey.createdAt);
      }
    }
    
    const response = await fetch(
      `https://{API-GATEWAY-DOMAIN}/{STAGE}/repository/${repositoryId}/collections?${params}`,
      { method: 'GET', headers: headers }
    );
    
    if (response.status !== 200) {
      console.error(`Error: ${response.status}`);
      break;
    }
    
    const result = await response.json();
    allCollections.push(...result.collections);
    
    // Check if there are more pages
    if (!result.hasNextPage) {
      break;
    }
    
    lastEvaluatedKey = result.lastEvaluatedKey;
  }
  
  return allCollections;
}

// Get all collections
getAllCollections('repo-123')
  .then(collections => {
    console.log(`Total collections: ${collections.length}`);
  })
  .catch(error => {
    console.error('Error:', error);
  });
```

**Filtering Examples:**

1. **Filter by name/description:**
   ```
   GET /repository/repo-123/collections?filter=legal
   ```
   Returns collections with "legal" in name or description

2. **Filter by status:**
   ```
   GET /repository/repo-123/collections?status=ACTIVE
   ```
   Returns only active collections

3. **Combined filters:**
   ```
   GET /repository/repo-123/collections?filter=legal&status=ACTIVE
   ```
   Returns active collections with "legal" in name or description

**Sorting Examples:**

1. **Sort by name (ascending):**
   ```
   GET /repository/repo-123/collections?sortBy=name&sortOrder=asc
   ```

2. **Sort by creation date (newest first):**
   ```
   GET /repository/repo-123/collections?sortBy=createdAt&sortOrder=desc
   ```

3. **Sort by last update (oldest first):**
   ```
   GET /repository/repo-123/collections?sortBy=updatedAt&sortOrder=asc
   ```

**Pagination Notes:**

1. **Page Size**: Maximum 100 items per page. Default is 20.
2. **Total Count**: Only available when no filters are applied (for performance reasons)
3. **Pagination Token**: Use `lastEvaluatedKey` from response to get next page
4. **URL Encoding**: Ensure pagination token values are URL-encoded when constructing URLs

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

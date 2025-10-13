# DynamoDB Schema for RAG 2.0 Collections

## Overview

This document defines the DynamoDB table schemas for RAG 2.0 Collections feature, including the new Collections table and updates to existing tables.

## Table 1: Collections Table (New)

### Table Name
`LisaRagCollectionsTable` (configurable via environment variable)

### Primary Key Structure

| Key Type | Attribute Name | Type | Description |
|----------|---------------|------|-------------|
| Partition Key (PK) | `collectionId` | String | UUID of the collection |
| Sort Key (SK) | `repositoryId` | String | Parent vector store ID |

**Rationale:** This key structure allows:
- Fast lookup by collection ID
- Efficient queries for all collections in a repository
- Natural relationship modeling (collection belongs to repository)

### Global Secondary Indexes

#### GSI 1: RepositoryIndex

**Purpose:** List all collections in a repository with sorting by creation date

| Key Type | Attribute Name | Type |
|----------|---------------|------|
| Partition Key | `repositoryId` | String |
| Sort Key | `createdAt` | String (ISO 8601) |

**Projection:** ALL

**Use Cases:**
- List collections for a repository: `GET /repository/{repositoryId}/collections`
- Sort collections by creation date
- Pagination through collections

**Query Pattern:**
```python
response = table.query(
    IndexName='RepositoryIndex',
    KeyConditionExpression='repositoryId = :repo_id',
    ExpressionAttributeValues={':repo_id': 'repo-123'},
    ScanIndexForward=False,  # Descending order (newest first)
    Limit=20
)
```

#### GSI 2: StatusIndex

**Purpose:** Filter collections by status within a repository

| Key Type | Attribute Name | Type |
|----------|---------------|------|
| Partition Key | `repositoryId` | String |
| Sort Key | `status` | String |

**Projection:** ALL

**Use Cases:**
- List only active collections
- Find archived collections
- Filter deleted collections (for cleanup)

**Query Pattern:**
```python
response = table.query(
    IndexName='StatusIndex',
    KeyConditionExpression='repositoryId = :repo_id AND #status = :status',
    ExpressionAttributeNames={'#status': 'status'},
    ExpressionAttributeValues={
        ':repo_id': 'repo-123',
        ':status': 'ACTIVE'
    }
)
```

#### GSI 3: CreatorIndex (Optional)

**Purpose:** Find all collections created by a specific user

| Key Type | Attribute Name | Type |
|----------|---------------|------|
| Partition Key | `createdBy` | String |
| Sort Key | `createdAt` | String (ISO 8601) |

**Projection:** ALL

**Use Cases:**
- User dashboard showing their collections
- Audit trail of user-created collections

### Attributes

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| collectionId | String (UUID) | Yes | Unique collection identifier |
| repositoryId | String | Yes | Parent vector store ID |
| name | String | No | User-friendly name (max 100 chars) |
| description | String | No | Collection description |
| chunkingStrategy | Map | No | Chunking strategy configuration |
| allowChunkingOverride | Boolean | Yes | Allow override during ingestion |
| metadata | Map | No | Collection metadata (tags, custom fields) |
| allowedGroups | List<String> | No | User groups with access (null = inherit) |
| embeddingModel | String | Yes | Embedding model ID (inherited) |
| createdBy | String | Yes | User ID of creator |
| createdAt | String | Yes | ISO 8601 timestamp |
| updatedAt | String | Yes | ISO 8601 timestamp |
| status | String | Yes | ACTIVE, ARCHIVED, DELETED |
| private | Boolean | Yes | Private to creator flag |
| pipelines | List<Map> | No | Automated ingestion pipelines |

### Example Item

```json
{
  "collectionId": "550e8400-e29b-41d4-a716-446655440000",
  "repositoryId": "repo-123",
  "name": "Legal Documents",
  "description": "Collection for legal contracts and agreements",
  "chunkingStrategy": {
    "type": "RECURSIVE",
    "chunkSize": 1000,
    "chunkOverlap": 200,
    "separators": ["\n\n", "\n", ". ", " "]
  },
  "allowChunkingOverride": true,
  "metadata": {
    "tags": ["legal", "contracts", "confidential"],
    "customFields": {
      "department": "legal",
      "classification": "internal"
    }
  },
  "allowedGroups": ["legal-team", "compliance"],
  "embeddingModel": "amazon.titan-embed-text-v1",
  "createdBy": "user-456",
  "createdAt": "2025-10-13T10:30:00.000Z",
  "updatedAt": "2025-10-13T10:30:00.000Z",
  "status": "ACTIVE",
  "private": false,
  "pipelines": [
    {
      "autoRemove": true,
      "chunkOverlap": 200,
      "chunkSize": 1000,
      "s3Bucket": "lisa-rag-documents",
      "s3Prefix": "legal/contracts/",
      "trigger": "event"
    }
  ]
}
```

### Capacity Planning

**Initial Provisioning:**
- Read Capacity Units (RCU): 5
- Write Capacity Units (WCU): 5

**Auto-scaling Configuration:**
- Target Utilization: 70%
- Min Capacity: 5
- Max Capacity: 100

**Estimated Item Size:**
- Average: 2 KB per collection
- Maximum: 10 KB per collection (with large metadata)

**Expected Load:**
- Collections per repository: 10-100
- Total collections: 1,000-10,000
- Read:Write ratio: 80:20

## Table 2: Documents Table (Updated)

### Table Name
`LisaRagDocumentTable` (existing)

### Updates Required

#### New Attribute

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| collectionId | String | Yes | Collection ID for the document |

#### Updated Partition Key

The partition key (`pk`) now includes the collection ID:

**Old Format:** `{repositoryId}`  
**New Format:** `{repositoryId}#{collectionId}`

**Example:**
```python
# Old
pk = "repo-123"

# New
pk = "repo-123#coll-456"
```

#### New Global Secondary Index: CollectionIndex

**Purpose:** List all documents in a collection

| Key Type | Attribute Name | Type |
|----------|---------------|------|
| Partition Key | `collectionId` | String |
| Sort Key | `upload_date` | Number |

**Projection:** ALL

**Use Cases:**
- List documents in a collection
- Count documents in a collection
- Delete all documents when collection is deleted

**Query Pattern:**
```python
response = table.query(
    IndexName='CollectionIndex',
    KeyConditionExpression='collectionId = :coll_id',
    ExpressionAttributeValues={':coll_id': 'coll-456'},
    ScanIndexForward=False  # Newest first
)
```

### Migration Strategy

**Backward Compatibility:**

For existing documents without `collectionId`:
1. Default collection ID is based on embedding model ID
2. Partition key remains backward compatible
3. No data migration required

**Example:**
```python
# Existing document (no collectionId)
existing_doc = {
    "pk": "repo-123",  # Old format
    "document_id": "doc-789",
    "repository_id": "repo-123",
    # collectionId missing
}

# Handled at runtime
def get_collection_id(doc):
    if 'collection_id' in doc:
        return doc['collection_id']
    else:
        # Use embedding model ID as default collection
        return get_embedding_model_id(doc['repository_id'])
```

## Table 3: Vector Store Table (Updated)

### Table Name
`LisaRagVectorStoreTable` (existing)

### New Attributes

| Attribute | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| allowUserCollections | Boolean | No | true | Allow non-admins to create collections |
| metadata | Map | No | {} | Vector store metadata |

#### metadata Structure

```json
{
  "metadata": {
    "tags": ["production", "v2"],
    "customFields": {
      "owner": "data-team",
      "environment": "prod"
    }
  }
}
```

### Example Updated Item

```json
{
  "repositoryId": "repo-123",
  "config": {
    "repositoryId": "repo-123",
    "embeddingModelId": "amazon.titan-embed-text-v1",
    "allowedGroups": ["engineering", "data-science"],
    "type": "opensearch",
    "allowUserCollections": true,
    "metadata": {
      "tags": ["production"],
      "customFields": {
        "owner": "ml-team"
      }
    }
  },
  "status": "CREATE_COMPLETE",
  "stackName": "lisa-rag-repo-123"
}
```

## Access Patterns

### Pattern 1: Create Collection

**Operation:** PutItem  
**Table:** Collections  
**Key:** `collectionId` (new UUID), `repositoryId`

```python
table.put_item(
    Item={
        'collectionId': str(uuid4()),
        'repositoryId': 'repo-123',
        'name': 'Legal Documents',
        # ... other attributes
    },
    ConditionExpression='attribute_not_exists(collectionId)'
)
```

### Pattern 2: Get Collection

**Operation:** GetItem  
**Table:** Collections  
**Key:** `collectionId`, `repositoryId`

```python
response = table.get_item(
    Key={
        'collectionId': 'coll-456',
        'repositoryId': 'repo-123'
    }
)
```

### Pattern 3: List Collections in Repository

**Operation:** Query  
**Table:** Collections  
**Index:** RepositoryIndex

```python
response = table.query(
    IndexName='RepositoryIndex',
    KeyConditionExpression='repositoryId = :repo_id',
    ExpressionAttributeValues={':repo_id': 'repo-123'},
    Limit=20,
    ExclusiveStartKey=last_evaluated_key  # For pagination
)
```

### Pattern 4: Update Collection

**Operation:** UpdateItem  
**Table:** Collections  
**Key:** `collectionId`, `repositoryId`

```python
table.update_item(
    Key={
        'collectionId': 'coll-456',
        'repositoryId': 'repo-123'
    },
    UpdateExpression='SET #desc = :desc, updatedAt = :now',
    ExpressionAttributeNames={'#desc': 'description'},
    ExpressionAttributeValues={
        ':desc': 'Updated description',
        ':now': datetime.now(timezone.utc).isoformat()
    }
)
```

### Pattern 5: Delete Collection

**Operation:** DeleteItem  
**Table:** Collections  
**Key:** `collectionId`, `repositoryId`

```python
# Soft delete (update status)
table.update_item(
    Key={
        'collectionId': 'coll-456',
        'repositoryId': 'repo-123'
    },
    UpdateExpression='SET #status = :deleted, updatedAt = :now',
    ExpressionAttributeNames={'#status': 'status'},
    ExpressionAttributeValues={
        ':deleted': 'DELETED',
        ':now': datetime.now(timezone.utc).isoformat()
    }
)

# Hard delete
table.delete_item(
    Key={
        'collectionId': 'coll-456',
        'repositoryId': 'repo-123'
    }
)
```

### Pattern 6: Count Documents in Collection

**Operation:** Query (with Select=COUNT)  
**Table:** Documents  
**Index:** CollectionIndex

```python
response = table.query(
    IndexName='CollectionIndex',
    KeyConditionExpression='collectionId = :coll_id',
    ExpressionAttributeValues={':coll_id': 'coll-456'},
    Select='COUNT'
)
document_count = response['Count']
```

### Pattern 7: Delete All Documents in Collection

**Operation:** BatchWriteItem  
**Table:** Documents  
**Index:** CollectionIndex (for query)

```python
# Query all documents
response = table.query(
    IndexName='CollectionIndex',
    KeyConditionExpression='collectionId = :coll_id',
    ExpressionAttributeValues={':coll_id': 'coll-456'},
    ProjectionExpression='pk, document_id'
)

# Batch delete
with table.batch_writer() as batch:
    for item in response['Items']:
        batch.delete_item(
            Key={
                'pk': item['pk'],
                'document_id': item['document_id']
            }
        )
```

## Performance Considerations

### Hot Partitions

**Risk:** Popular repositories with many collections could create hot partitions

**Mitigation:**
- Use UUID for collectionId (distributes writes)
- Use GSI for repository-based queries (distributes reads)
- Monitor partition metrics

### Large Items

**Risk:** Collections with many pipelines or large metadata could exceed item size limits

**Mitigation:**
- Limit pipelines to 10 per collection
- Limit metadata tags to 50
- Limit custom fields size to 10 KB

### Query Performance

**Optimization:**
- Use sparse indexes for optional attributes
- Project only needed attributes in GSIs
- Use pagination for large result sets
- Cache frequently accessed collections

## Cost Optimization

### On-Demand vs Provisioned

**Recommendation:** Start with On-Demand pricing

**Rationale:**
- Unpredictable access patterns initially
- Low initial volume
- Switch to provisioned after establishing baseline

### TTL for Deleted Collections

**Configuration:** Enable TTL on `deletedAt` attribute

```python
# Set TTL when soft-deleting
table.update_item(
    Key={'collectionId': 'coll-456', 'repositoryId': 'repo-123'},
    UpdateExpression='SET #status = :deleted, deletedAt = :ttl',
    ExpressionAttributeNames={'#status': 'status'},
    ExpressionAttributeValues={
        ':deleted': 'DELETED',
        ':ttl': int(time.time()) + (90 * 24 * 60 * 60)  # 90 days
    }
)
```

## Monitoring

### CloudWatch Metrics

Monitor these metrics:
- `ConsumedReadCapacityUnits`
- `ConsumedWriteCapacityUnits`
- `UserErrors` (throttling)
- `SystemErrors`
- `SuccessfulRequestLatency`

### Alarms

Set alarms for:
- Throttled requests > 1% of total requests
- Average latency > 100ms
- User errors > 5% of total requests

## Backup and Recovery

### Point-in-Time Recovery (PITR)

**Status:** Enabled  
**Retention:** 35 days

### On-Demand Backups

**Schedule:** Daily at 2 AM UTC  
**Retention:** 30 days

### Disaster Recovery

**RTO:** 4 hours  
**RPO:** 5 minutes (PITR)

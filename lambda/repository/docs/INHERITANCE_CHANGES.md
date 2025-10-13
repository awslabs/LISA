# Collection Inheritance Changes

## Summary of Changes

This document summarizes the corrections made to the collection inheritance model based on requirements clarification.

## Changes Made

### 1. embeddingModel Inheritance

**Previous Behavior:**
- Always inherited from parent vector store
- Completely immutable (read-only)

**Updated Behavior:**
- Can be **overridden at collection creation time**
- If not specified during creation, inherits from parent
- **Immutable after creation** (cannot be updated)

**Rationale:**
- Allows different collections to use different embedding models
- Enables optimization for different content types
- Maintains consistency within a collection (immutable after creation)

**Example Use Cases:**
```python
# Use case 1: Legal documents with specialized embedding model
legal_collection = {
    "name": "Legal Contracts",
    "embeddingModel": "cohere.embed-english-v3",  # Optimized for legal text
    "repositoryId": "repo-123"
}

# Use case 2: Code documentation with code-specific model
code_collection = {
    "name": "API Documentation",
    "embeddingModel": "amazon.titan-embed-code-v1",  # Optimized for code
    "repositoryId": "repo-123"
}

# Use case 3: General documents using default
general_collection = {
    "name": "General Documents",
    # embeddingModel not specified - inherits from parent
    "repositoryId": "repo-123"
}
```

### 2. metadata Inheritance

**Previous Behavior:**
- NOT inherited from parent
- Collection-specific only

**Updated Behavior:**
- **Composite/Merged** from parent and collection
- Tags are combined (deduplicated)
- Custom fields from collection override parent on conflict

**Rationale:**
- Allows organization-wide metadata standards
- Enables collection-specific metadata additions
- Supports hierarchical metadata management

**Merge Algorithm:**
```python
def merge_metadata(parent_metadata, collection_metadata):
    """
    Merges parent and collection metadata.
    
    Rules:
    1. Tags: Union of parent + collection (deduplicated, order preserved)
    2. Custom Fields: Collection overrides parent for same keys
    3. Null handling: If either is null, use the other
    """
    if parent is None:
        return collection
    if collection is None:
        return parent
    
    # Combine tags (deduplicate while preserving order)
    merged_tags = list(dict.fromkeys(parent.tags + collection.tags))
    
    # Merge custom fields (collection overrides parent)
    merged_custom_fields = {**parent.customFields, **collection.customFields}
    
    return CollectionMetadata(
        tags=merged_tags,
        customFields=merged_custom_fields
    )
```

**Example:**
```python
# Parent vector store metadata
parent_metadata = {
    "tags": ["production", "v2", "monitored"],
    "customFields": {
        "owner": "data-team",
        "environment": "prod",
        "cost-center": "engineering"
    }
}

# Collection-specific metadata
collection_metadata = {
    "tags": ["legal", "confidential"],
    "customFields": {
        "department": "legal",
        "environment": "prod-legal",  # Overrides parent
        "retention": "7-years"
    }
}

# Effective merged metadata
effective_metadata = {
    "tags": [
        "production",      # From parent
        "v2",             # From parent
        "monitored",      # From parent
        "legal",          # From collection
        "confidential"    # From collection
    ],
    "customFields": {
        "owner": "data-team",           # From parent
        "environment": "prod-legal",    # From collection (overrides parent)
        "cost-center": "engineering",   # From parent
        "department": "legal",          # From collection
        "retention": "7-years"          # From collection
    }
}
```

## Updated Model Changes

### CreateCollectionRequest

**Added Field:**
```python
embeddingModel: Optional[str] = Field(
    default=None, 
    description="Embedding model ID (inherits from parent if omitted, immutable after creation)"
)
```

### RagCollectionConfig

**Updated Field Descriptions:**
```python
embeddingModel: str = Field(
    min_length=1, 
    description="Embedding model ID (can be set at creation, immutable after)"
)

metadata: Optional[CollectionMetadata] = Field(
    default=None, 
    description="Collection-specific metadata (merged with parent)"
)
```

### CollectionMetadata

**Added Method:**
```python
@classmethod
def merge(cls, parent: Optional["CollectionMetadata"], 
          child: Optional["CollectionMetadata"]) -> "CollectionMetadata":
    """Merges parent and child metadata."""
    # Implementation handles tag deduplication and custom field merging
```

## Implementation Impact

### Service Layer Changes Required

1. **Collection Creation:**
   - Accept optional `embeddingModel` in request
   - If not provided, fetch from parent vector store
   - Store in collection configuration
   - Validate embedding model exists

2. **Collection Update:**
   - Reject attempts to update `embeddingModel`
   - Add to immutable fields list

3. **Metadata Resolution:**
   - Fetch parent vector store metadata
   - Fetch collection metadata
   - Use `CollectionMetadata.merge()` to combine
   - Return merged metadata in API responses

4. **Document Ingestion:**
   - Use collection's `embeddingModel` (not parent's)
   - Apply merged metadata to documents

### API Response Changes

**Collection GET Response:**
```json
{
  "collectionId": "coll-456",
  "repositoryId": "repo-123",
  "embeddingModel": "cohere.embed-english-v3",
  "metadata": {
    "tags": ["production", "v2", "legal", "confidential"],
    "customFields": {
      "owner": "data-team",
      "environment": "prod-legal",
      "department": "legal"
    }
  },
  "_metadataSource": {
    "parentTags": ["production", "v2"],
    "collectionTags": ["legal", "confidential"],
    "parentCustomFields": {"owner": "data-team", "environment": "prod"},
    "collectionCustomFields": {"department": "legal", "environment": "prod-legal"}
  }
}
```

Note: `_metadataSource` is optional debug information, not required in production.

## Validation Rules

### embeddingModel Validation

```python
def validate_embedding_model_at_creation(embedding_model: Optional[str], 
                                         parent_embedding_model: str) -> str:
    """Validates and resolves embedding model at creation."""
    if embedding_model is None:
        return parent_embedding_model
    
    # Validate embedding model exists
    if not is_valid_embedding_model(embedding_model):
        raise ValidationError(f"Invalid embedding model: {embedding_model}")
    
    return embedding_model

def validate_embedding_model_at_update(update_request: UpdateCollectionRequest):
    """Ensures embedding model is not updated."""
    if update_request.embeddingModel is not None:
        raise ValidationError(
            "embeddingModel is immutable and cannot be updated after creation"
        )
```

### metadata Validation

```python
def validate_merged_metadata(parent_metadata: Optional[CollectionMetadata],
                             collection_metadata: Optional[CollectionMetadata]) -> CollectionMetadata:
    """Validates merged metadata doesn't exceed limits."""
    merged = CollectionMetadata.merge(parent_metadata, collection_metadata)
    
    if len(merged.tags) > 50:
        raise ValidationError(
            f"Merged metadata has {len(merged.tags)} tags, maximum is 50. "
            f"Reduce collection-specific tags."
        )
    
    return merged
```

## Migration Considerations

### Existing Collections

**Scenario:** Collections created before this change

**Behavior:**
- `embeddingModel` already set (inherited from parent at creation)
- No change required
- Remains immutable

### Existing Vector Stores

**Scenario:** Vector stores without metadata

**Behavior:**
- Collections can still define metadata
- Merge with empty parent metadata = collection metadata only
- No migration required

## Testing Requirements

### Unit Tests

1. **embeddingModel Tests:**
   - Test creation with explicit embedding model
   - Test creation with inherited embedding model
   - Test update rejection of embedding model
   - Test validation of invalid embedding model

2. **metadata Tests:**
   - Test merge with both parent and collection metadata
   - Test merge with only parent metadata
   - Test merge with only collection metadata
   - Test merge with neither (empty metadata)
   - Test tag deduplication
   - Test custom field override
   - Test merged metadata validation (50 tag limit)

### Integration Tests

1. Create collection with custom embedding model
2. Verify documents use collection's embedding model
3. Create collection with metadata
4. Verify merged metadata in responses
5. Attempt to update embedding model (should fail)
6. Update collection metadata
7. Verify merged metadata updates correctly

## Documentation Updates

✅ Updated files:
- `lambda/models/domain_objects.py` - Model definitions
- `lambda/repository/docs/COLLECTION_INHERITANCE.md` - Inheritance rules
- `lambda/repository/schemas/collection_schema.json` - JSON schema
- `lambda/repository/docs/INHERITANCE_CHANGES.md` - This file

## Summary

These changes provide more flexibility in collection configuration while maintaining data consistency:

1. **embeddingModel:** Can be customized per collection at creation time, enabling optimization for different content types
2. **metadata:** Composite inheritance allows organization-wide standards with collection-specific additions

Both changes maintain backward compatibility and require no data migration.

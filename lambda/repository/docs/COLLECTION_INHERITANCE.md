# Collection Configuration Inheritance Rules

## Overview

RAG 2.0 Collections inherit default configurations from their parent Vector Store to ensure consistency while allowing flexibility. This document defines the inheritance rules and constraints.

## Inheritance Hierarchy

```
Vector Store (Parent)
  ├── embeddingModelId
  ├── allowedGroups
  ├── chunkingStrategy (from pipelines)
  └── metadata
      └── tags

Collection (Child)
  ├── embeddingModel ← INHERITED (immutable)
  ├── allowedGroups ← INHERITED (can be restricted)
  ├── chunkingStrategy ← INHERITED (can be overridden)
  └── metadata ← NOT INHERITED (collection-specific)
```

## Field-by-Field Inheritance Rules

### 1. embeddingModel

**Inheritance:** Inherited from parent if not specified at creation  
**Mutability:** Immutable after creation (can be set once at creation time)  
**Validation:** Must be a valid embedding model ID

**Behavior:**
- If not specified during creation, inherits parent's `embeddingModelId`
- Can be explicitly set to a different model during creation (allows different embedding models per collection)
- Cannot be changed after creation (immutable)
- Ensures all documents in a collection use the same embedding model

**Example:**
```python
# Vector Store
vector_store = {
    "repositoryId": "repo-123",
    "embeddingModelId": "amazon.titan-embed-text-v1"
}

# Collection with inherited embedding model
collection_inherited = {
    "collectionId": "coll-456",
    "repositoryId": "repo-123",
    "embeddingModel": "amazon.titan-embed-text-v1"  # Inherited from parent
}

# Collection with custom embedding model (set at creation)
collection_custom = {
    "collectionId": "coll-789",
    "repositoryId": "repo-123",
    "embeddingModel": "cohere.embed-english-v3"  # Different from parent, set at creation
}

# Attempting to update embedding model (FAILS)
update_request = {
    "embeddingModel": "amazon.titan-embed-text-v2"  # This will be ignored/rejected
}
# Result: embeddingModel remains unchanged (immutable after creation)
```

### 2. allowedGroups

**Inheritance:** Inherited from parent if not specified  
**Mutability:** Mutable (can be restricted)  
**Validation:** Must be a subset of parent's allowedGroups

**Behavior:**
- If `allowedGroups` is `null` or empty during creation, inherits parent's groups
- If specified, must be a subset of parent's `allowedGroups`
- Cannot grant access to groups not allowed by parent
- Can be updated later (still must remain a subset)

**Example:**
```python
# Vector Store
vector_store = {
    "repositoryId": "repo-123",
    "allowedGroups": ["engineering", "data-science", "ml-ops"]
}

# Valid Collection (subset of parent groups)
collection_valid = {
    "collectionId": "coll-456",
    "repositoryId": "repo-123",
    "allowedGroups": ["engineering", "ml-ops"]  # Valid: subset of parent
}

# Invalid Collection (contains group not in parent)
collection_invalid = {
    "collectionId": "coll-789",
    "repositoryId": "repo-123",
    "allowedGroups": ["engineering", "finance"]  # Invalid: "finance" not in parent
}
# Validation Error: "allowedGroups must be a subset of parent repository groups"

# Collection with inherited groups
collection_inherited = {
    "collectionId": "coll-999",
    "repositoryId": "repo-123",
    "allowedGroups": None  # Inherits all parent groups
}
# Result: allowedGroups = ["engineering", "data-science", "ml-ops"]
```

### 3. chunkingStrategy

**Inheritance:** Inherited from parent if not specified  
**Mutability:** Mutable (can be overridden)  
**Validation:** Must be a valid chunking strategy

**Behavior:**
- If `chunkingStrategy` is `null` during creation, inherits from parent's pipeline configuration
- Can be overridden with any valid chunking strategy
- Different collections can use different strategies for optimal document processing
- Can be updated later (with warning if documents already exist)

**Example:**
```python
# Vector Store with default chunking strategy
vector_store = {
    "repositoryId": "repo-123",
    "pipelines": [{
        "chunkSize": 1000,
        "chunkOverlap": 200
    }]
}

# Collection with inherited strategy
collection_inherited = {
    "collectionId": "coll-456",
    "repositoryId": "repo-123",
    "chunkingStrategy": None  # Inherits from parent
}
# Result: chunkingStrategy = {"type": "FIXED_SIZE", "chunkSize": 1000, "chunkOverlap": 200}

# Collection with custom strategy
collection_custom = {
    "collectionId": "coll-789",
    "repositoryId": "repo-123",
    "chunkingStrategy": {
        "type": "RECURSIVE",
        "chunkSize": 1500,
        "chunkOverlap": 300,
        "separators": ["\n\n", "\n", ". "]
    }
}
```

### 4. metadata

**Inheritance:** Composite (merged with parent)  
**Mutability:** Mutable  
**Validation:** Tags must follow format rules

**Behavior:**
- Metadata is **merged** from parent vector store and collection
- Collection metadata is **additive** to parent metadata
- Tags from both parent and collection are combined (deduplicated)
- Custom fields from both parent and collection are merged (collection values override parent on conflict)
- Allows both organization-wide and collection-specific metadata

**Example:**
```python
# Vector Store with metadata
vector_store = {
    "repositoryId": "repo-123",
    "metadata": {
        "tags": ["production", "v2"],
        "customFields": {
            "owner": "data-team",
            "environment": "prod"
        }
    }
}

# Collection with additional metadata
collection = {
    "collectionId": "coll-456",
    "repositoryId": "repo-123",
    "metadata": {
        "tags": ["legal", "contracts"],  # Added to parent tags
        "customFields": {
            "department": "legal",
            "environment": "prod-legal"  # Overrides parent's "environment"
        }
    }
}

# Effective merged metadata for the collection
effective_metadata = {
    "tags": ["production", "v2", "legal", "contracts"],  # Combined and deduplicated
    "customFields": {
        "owner": "data-team",  # From parent
        "environment": "prod-legal",  # From collection (overrides parent)
        "department": "legal"  # From collection
    }
}
```

**Merge Rules:**
1. **Tags:** Union of parent and collection tags (deduplicated while preserving order)
2. **Custom Fields:** Collection values override parent values for same keys
3. **Empty Collection Metadata:** If collection has no metadata, uses parent metadata only
4. **Empty Parent Metadata:** If parent has no metadata, uses collection metadata only

**Implementation:**
```python
# Using the CollectionMetadata.merge() helper method
from models.domain_objects import CollectionMetadata

parent_metadata = CollectionMetadata(
    tags=["production", "v2"],
    customFields={"owner": "data-team", "environment": "prod"}
)

collection_metadata = CollectionMetadata(
    tags=["legal", "contracts"],
    customFields={"department": "legal", "environment": "prod-legal"}
)

# Merge metadata
effective_metadata = CollectionMetadata.merge(parent_metadata, collection_metadata)
# Result:
# tags: ["production", "v2", "legal", "contracts"]
# customFields: {"owner": "data-team", "environment": "prod-legal", "department": "legal"}
```

## Immutable Fields

The following fields cannot be changed after collection creation:

1. **collectionId** - Unique identifier
2. **repositoryId** - Parent vector store reference
3. **embeddingModel** - Inherited embedding model
4. **createdBy** - Original creator
5. **createdAt** - Creation timestamp

**Behavior:**
- Update requests that include these fields will ignore the changes
- These fields are protected at the service layer
- Attempting to modify them will not result in an error, but changes will be silently ignored

## Validation Rules

### Name Uniqueness

**Rule:** Collection name must be unique within the parent repository

```python
# Validation check during creation/update
def validate_name_uniqueness(repository_id: str, name: str, collection_id: str = None):
    existing = collection_repo.find_by_repository_and_name(repository_id, name)
    if existing and existing.collectionId != collection_id:
        raise ValidationError("Collection name must be unique within repository")
```

### Allowed Groups Subset

**Rule:** Collection allowedGroups must be a subset of parent allowedGroups

```python
# Validation check during creation/update
def validate_allowed_groups(parent_groups: List[str], collection_groups: List[str]):
    if not set(collection_groups).issubset(set(parent_groups)):
        invalid_groups = set(collection_groups) - set(parent_groups)
        raise ValidationError(
            f"Collection allowedGroups must be a subset of parent repository groups. "
            f"Invalid groups: {invalid_groups}"
        )
```

### Chunk Overlap Constraint

**Rule:** chunkOverlap must be ≤ chunkSize/2

```python
# Validation check for chunking strategies
def validate_chunk_overlap(chunk_size: int, chunk_overlap: int):
    if chunk_overlap > chunk_size / 2:
        raise ValidationError(
            f"chunkOverlap ({chunk_overlap}) must be less than or equal to "
            f"half of chunkSize ({chunk_size/2})"
        )
```

## Default Collection Behavior

For backward compatibility, vector stores without explicit collections use a "default" collection:

**Default Collection Properties:**
- `collectionId`: Based on embedding model ID (e.g., `"amazon.titan-embed-text-v1"`)
- `name`: `"Default Collection"`
- `allowedGroups`: Inherited from vector store
- `chunkingStrategy`: Inherited from vector store pipelines
- `status`: `ACTIVE`
- `private`: `false`

**Example:**
```python
# Vector Store without collections
vector_store = {
    "repositoryId": "repo-123",
    "embeddingModelId": "amazon.titan-embed-text-v1",
    "allowedGroups": ["engineering"]
}

# Automatically created default collection
default_collection = {
    "collectionId": "amazon.titan-embed-text-v1",  # Based on embedding model
    "repositoryId": "repo-123",
    "name": "Default Collection",
    "embeddingModel": "amazon.titan-embed-text-v1",
    "allowedGroups": ["engineering"],  # Inherited
    "status": "ACTIVE",
    "private": False
}
```

## Update Behavior

### Changing Inherited Values

When updating a collection that previously inherited a value:

```python
# Collection initially created with inherited groups
collection_before = {
    "collectionId": "coll-456",
    "repositoryId": "repo-123",
    "allowedGroups": None  # Inherited: ["engineering", "data-science"]
}

# Update to restrict groups
update_request = {
    "allowedGroups": ["engineering"]  # Restrict to subset
}

collection_after = {
    "collectionId": "coll-456",
    "repositoryId": "repo-123",
    "allowedGroups": ["engineering"]  # Now explicitly set
}
```

### Changing Chunking Strategy with Existing Documents

When updating `chunkingStrategy` on a collection with existing documents:

```python
# Collection with documents
collection = {
    "collectionId": "coll-456",
    "repositoryId": "repo-123",
    "chunkingStrategy": {"type": "FIXED_SIZE", "chunkSize": 1000, "chunkOverlap": 200}
}

# Update request
update_request = {
    "chunkingStrategy": {"type": "RECURSIVE", "chunkSize": 1500, "chunkOverlap": 300}
}

# Warning returned in response
response = {
    "collection": { /* updated collection */ },
    "warnings": [
        "Changing chunking strategy will only affect new documents. "
        "Existing documents will retain their original chunking. "
        "Consider re-ingesting existing documents if needed."
    ]
}
```

## Summary Table

| Field | Inherited | Mutable After Creation | Constraint |
|-------|-----------|----------------------|------------|
| collectionId | No | No | Auto-generated UUID |
| repositoryId | No | No | Set at creation |
| name | No | Yes | Unique within repository, max 100 chars |
| description | No | Yes | None |
| embeddingModel | Yes (if not set) | No | Can override at creation, immutable after |
| allowedGroups | Yes (if not set) | Yes | Must be subset of parent |
| chunkingStrategy | Yes (if not set) | Yes | Valid strategy format |
| metadata | Yes (merged) | Yes | Composite of parent + collection |
| private | No | Yes | Boolean |
| allowChunkingOverride | No | Yes | Boolean |
| pipelines | No | Yes | Valid pipeline configs |
| status | No | Yes | ACTIVE, ARCHIVED, DELETED |
| createdBy | No | No | Set at creation |
| createdAt | No | No | Set at creation |
| updatedAt | No | Yes | Auto-updated |

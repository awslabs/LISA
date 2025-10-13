# Schema Migration: JSON to Zod

## Summary

The collection schema has been migrated from JSON Schema to Zod Schema to align with LISA's standard schema patterns.

## Changes Made

### Removed
- ❌ `lambda/repository/schemas/collection_schema.json` - Old JSON schema file

### Added
- ✅ `lib/schema/collectionSchema.ts` - New Zod schema file

## Zod Schema Benefits

1. **Type Safety**: Automatic TypeScript type generation
2. **Runtime Validation**: Validates data at runtime
3. **Consistency**: Matches existing LISA patterns (ragSchema.ts, configSchema.ts)
4. **Refinements**: Complex validation logic with `.refine()`
5. **Transformations**: Data transformation capabilities
6. **Better DX**: IDE autocomplete and type checking

## Schema Structure

### Enums
```typescript
export enum CollectionStatus {
    ACTIVE = 'ACTIVE',
    ARCHIVED = 'ARCHIVED',
    DELETED = 'DELETED',
}

export enum ChunkingStrategyType {
    FIXED_SIZE = 'FIXED_SIZE',
    SEMANTIC = 'SEMANTIC',
    RECURSIVE = 'RECURSIVE',
}
```

### Main Schemas
- `ChunkingStrategySchema` - Union of all chunking strategies
- `PipelineConfigSchema` - Pipeline configuration
- `CollectionMetadataSchema` - Metadata with validation
- `RagCollectionConfigSchema` - Complete collection config
- `CreateCollectionRequestSchema` - Creation request
- `UpdateCollectionRequestSchema` - Update request
- `ListCollectionsQuerySchema` - Query parameters
- `ListCollectionsResponseSchema` - Response format

### Type Exports
```typescript
export type RagCollectionConfig = z.infer<typeof RagCollectionConfigSchema>;
export type CreateCollectionRequest = z.infer<typeof CreateCollectionRequestSchema>;
// ... etc
```

### Constants
```typescript
export const COLLECTION_INHERITANCE_RULES = { /* ... */ };
export const IMMUTABLE_FIELDS = ['collectionId', 'repositoryId', ...];
export const VALIDATION_RULES = { /* ... */ };
```

## Usage Examples

### Validation
```typescript
import { CreateCollectionRequestSchema } from '@/schema/collectionSchema';

// Validate request data
const result = CreateCollectionRequestSchema.safeParse(requestData);
if (!result.success) {
    console.error(result.error);
}
```

### Type Checking
```typescript
import { RagCollectionConfig } from '@/schema/collectionSchema';

function processCollection(collection: RagCollectionConfig) {
    // TypeScript knows all fields and types
    console.log(collection.collectionId);
}
```

### Default Values
```typescript
import { getDefaults } from '@/schema/zodUtil';
import { CreateCollectionRequestSchema } from '@/schema/collectionSchema';

const defaults = getDefaults(CreateCollectionRequestSchema);
// { private: false, allowChunkingOverride: true, ... }
```

## Migration Impact

### Backend (Python)
- No changes required
- Python models in `domain_objects.py` remain authoritative for backend
- Zod schema is for frontend/CDK validation

### Frontend (TypeScript/React)
- Import types from `@/schema/collectionSchema`
- Use schemas for form validation
- Type-safe API calls

### CDK (TypeScript)
- Use schemas for config validation
- Type-safe infrastructure definitions

## Validation Rules

All validation rules from the JSON schema are preserved:

1. **Name Validation**
   - Max 100 characters
   - Alphanumeric, spaces, hyphens, underscores only
   - Unique within repository (enforced at service layer)

2. **Chunk Overlap**
   - Must be ≤ chunkSize/2
   - Enforced with `.refine()`

3. **Tags**
   - Max 50 tags per collection
   - Each tag max 50 characters
   - Alphanumeric, hyphens, underscores only

4. **Allowed Groups**
   - Must be subset of parent (enforced at service layer)

5. **Update Request**
   - At least one field required
   - Enforced with `.refine()`

## Documentation

All inheritance rules and validation constraints are documented in:
- `lib/schema/collectionSchema.ts` - Inline with schemas
- `lambda/repository/docs/COLLECTION_INHERITANCE.md` - Detailed inheritance rules
- `lambda/repository/docs/INHERITANCE_CHANGES.md` - Change rationale

## Testing

### Unit Tests (TypeScript)
```typescript
import { CreateCollectionRequestSchema } from '@/schema/collectionSchema';

describe('CreateCollectionRequestSchema', () => {
    it('validates valid request', () => {
        const result = CreateCollectionRequestSchema.safeParse({
            name: 'Test Collection',
            embeddingModel: 'amazon.titan-embed-text-v1',
        });
        expect(result.success).toBe(true);
    });

    it('rejects invalid name', () => {
        const result = CreateCollectionRequestSchema.safeParse({
            name: 'Invalid@Name!',
        });
        expect(result.success).toBe(false);
    });
});
```

### Integration Tests
- Validate API requests/responses match schema
- Ensure Python models and Zod schemas stay in sync

## Maintenance

### Keeping Schemas in Sync

When updating collection models:

1. Update Python models in `lambda/models/domain_objects.py`
2. Update Zod schema in `lib/schema/collectionSchema.ts`
3. Update documentation in `lambda/repository/docs/`
4. Run tests to ensure compatibility

### Schema Versioning

If breaking changes are needed:
1. Create new schema version (e.g., `RagCollectionConfigSchemaV2`)
2. Maintain old schema for backward compatibility
3. Add migration utilities
4. Update API versioning

## References

- Zod Documentation: https://zod.dev/
- Existing LISA schemas: `lib/schema/ragSchema.ts`, `lib/schema/configSchema.ts`
- Zod utilities: `lib/schema/zodUtil.ts`

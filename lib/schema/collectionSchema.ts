/**
 Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

 Licensed under the Apache License, Version 2.0 (the "License").
 You may not use this file except in compliance with the License.
 You may obtain a copy of the License at

 http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
 */

import { z } from 'zod';
import {
    RagRepositoryPipeline,
    ChunkingStrategySchema,
} from './ragSchema';

/**
 * Enum for collection status
 */
export enum CollectionStatus {
    ACTIVE = 'ACTIVE',
    ARCHIVED = 'ARCHIVED',
    DELETED = 'DELETED',
    DELETE_IN_PROGRESS = 'DELETE_IN_PROGRESS',
    DELETE_FAILED = 'DELETE_FAILED'
}


// Future chunking strategies (not yet implemented):
//
// export const SemanticChunkingStrategySchema = z.object({
//     type: z.literal(ChunkingStrategyType.SEMANTIC).describe('Semantic chunking strategy type'),
//     threshold: z.number().min(0.0).max(1.0).describe('Similarity threshold for semantic boundaries'),
//     chunkSize: z.number().min(100).max(10000).default(1000).optional().describe('Maximum chunk size'),
// });
//
// export const RecursiveChunkingStrategySchema = z.object({
//     type: z.literal(ChunkingStrategyType.RECURSIVE).describe('Recursive chunking strategy type'),
//     chunkSize: z.number().min(100).max(10000).describe('Target size of each chunk'),
//     chunkOverlap: z.number().min(0).describe('Overlap between chunks'),
//     separators: z.array(z.string()).min(1).default(['\n\n', '\n', '. ', ' ']).describe('Separators to use for recursive splitting'),
// }).refine(
//     (data) => data.chunkOverlap <= data.chunkSize / 2,
//     { message: 'chunkOverlap must be less than or equal to half of chunkSize' }
// );
//
// When implementing new strategies:
// 1. Add the strategy type to ChunkingStrategyType enum (uncomment above)
// 2. Create the schema (uncomment and modify above)
// 3. Update ChunkingStrategySchema to be a union: z.union([FixedSizeChunkingStrategySchema, SemanticChunkingStrategySchema, ...])
// 4. Implement the backend handler in chunking_strategy_factory.py

/**
 * Pipeline configuration schema - reusing from ragSchema
 */
export const PipelineConfigSchema = RagRepositoryPipeline;

/**
 * Collection metadata schema
 */
export const CollectionMetadataSchema = z.object({
    tags: z.array(
        z.string()
            .max(50)
            .regex(/^[a-zA-Z0-9_-]+$/, 'Tags must contain only alphanumeric characters, hyphens, and underscores')
    ).max(50).default([]).describe('Metadata tags for the collection (max 50 tags, each max 50 chars)'),
    customFields: z.record(z.string(), z.any()).default({}).describe('Custom metadata fields'),
});

/**
 * RAG Collection configuration schema
 */
export const RagCollectionConfigSchema = z.object({
    collectionId: z.uuid().describe('Unique collection identifier (UUID)'),
    repositoryId: z.string().min(1).describe('Parent vector store ID'),
    name: z.string()
        .max(100)
        .regex(/^[a-zA-Z0-9 _-]+$/, 'Collection name must contain only alphanumeric characters, spaces, hyphens, and underscores')
        .optional()
        .describe('User-friendly collection name'),
    description: z.string().optional().describe('Collection description'),
    chunkingStrategy: ChunkingStrategySchema.optional().describe('Chunking strategy for documents (inherits from parent if omitted)'),
    allowChunkingOverride: z.boolean().default(true).describe('Allow users to override chunking strategy during ingestion'),
    metadata: CollectionMetadataSchema.optional().describe('Collection-specific metadata (merged with parent metadata)'),
    allowedGroups: z.array(z.string()).optional().describe('User groups with access to collection (inherits from parent if omitted)'),
    embeddingModel: z.string().optional().describe('Embedding model ID (can be set at creation, inherits from parent if omitted, immutable after creation)'),
    createdBy: z.string().min(1).describe('User ID of creator'),
    createdAt: z.iso.datetime().describe('Creation timestamp (ISO 8601)'),
    updatedAt: z.iso.datetime().describe('Last update timestamp (ISO 8601)'),
    status: z.enum(CollectionStatus).default(CollectionStatus.ACTIVE).describe('Collection status'),
    default: z.boolean().default(false).optional().describe('Indicates if this is a default collection (virtual, no DB entry)'),
});

/**
 * Collection sort options
 */
export enum CollectionSortBy {
    NAME = 'name',
    CREATED_AT = 'createdAt',
    UPDATED_AT = 'updatedAt',
}

/**
 * Sort order options
 */
export enum SortOrder {
    ASC = 'asc',
    DESC = 'desc',
}

/**
 * List collections query parameters schema
 */
export const ListCollectionsQuerySchema = z.object({
    page: z.int().min(1).default(1).describe('Page number'),
    pageSize: z.int().min(1).max(100).default(20).describe('Number of items per page'),
    filter: z.string().optional().describe('Filter by name or description (substring match)'),
    sortBy: z.enum(CollectionSortBy).default(CollectionSortBy.CREATED_AT).describe('Sort field'),
    sortOrder: z.enum(SortOrder).default(SortOrder.DESC).describe('Sort order'),
    status: z.enum(CollectionStatus).optional().describe('Filter by status'),
});

/**
 * List collections response schema
 */
export const ListCollectionsResponseSchema = z.object({
    collections: z.array(RagCollectionConfigSchema).describe('List of collections'),
    totalCount: z.int().optional().describe('Total number of collections'),
    currentPage: z.int().optional().describe('Current page number'),
    totalPages: z.int().optional().describe('Total number of pages'),
    hasNextPage: z.boolean().default(false).describe('Whether there is a next page'),
    hasPreviousPage: z.boolean().default(false).describe('Whether there is a previous page'),
    lastEvaluatedKey: z.record(z.string(), z.string()).optional().describe('Last evaluated key for pagination'),
});

/**
 * Type exports
 */
// ChunkingStrategy types are re-exported from ragSchema above
// export type SemanticChunkingStrategy = z.infer<typeof SemanticChunkingStrategySchema>;  // Not yet implemented
// export type RecursiveChunkingStrategy = z.infer<typeof RecursiveChunkingStrategySchema>;  // Not yet implemented
// PipelineConfig type is exported from ragSchema via PipelineConfigSchema
export type CollectionMetadata = z.infer<typeof CollectionMetadataSchema>;
export type RagCollectionConfig = z.infer<typeof RagCollectionConfigSchema>;
export type ListCollectionsQuery = z.infer<typeof ListCollectionsQuerySchema>;
export type ListCollectionsResponse = z.infer<typeof ListCollectionsResponseSchema>;

/**
 * Inheritance rules documentation
 */
export const COLLECTION_INHERITANCE_RULES = {
    embeddingModel: {
        inherited: true,
        mutableAtCreation: true,
        mutableAfterCreation: false,
        description: 'Inherits from parent if not specified at creation. Can be overridden at creation time but becomes immutable after creation.',
    },
    allowedGroups: {
        inherited: true,
        mutable: true,
        constraint: 'Must be a subset of parent vector store\'s allowedGroups',
        description: 'Inherits from parent if not specified, can be restricted but not expanded',
    },
    chunkingStrategy: {
        inherited: true,
        mutable: true,
        description: 'Inherits from parent if not specified, can be overridden per collection',
    },
    metadata: {
        inherited: true,
        mergeStrategy: 'composite',
        mutable: true,
        description: 'Merged from parent and collection. Tags are combined (deduplicated), custom fields from collection override parent on conflict.',
    },
} as const;

/**
 * Immutable fields that cannot be changed after creation
 */
export const IMMUTABLE_FIELDS = [
    'collectionId',
    'repositoryId',
    'embeddingModel',
    'createdBy',
    'createdAt',
] as const;

/**
 * Validation rules
 */
export const VALIDATION_RULES = {
    nameUniqueness: 'Collection name must be unique within the parent repository',
    allowedGroupsSubset: 'Collection allowedGroups must be a subset of parent repository allowedGroups',
    chunkOverlapConstraint: 'chunkOverlap must be less than or equal to chunkSize/2',
    tagsLimit: 'Maximum 50 tags per collection, each tag maximum 50 characters',
    nameCharacters: 'Name must contain only alphanumeric characters, spaces, hyphens, and underscores',
} as const;

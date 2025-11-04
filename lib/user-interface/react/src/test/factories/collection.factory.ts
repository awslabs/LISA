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

import { ChunkingStrategyType, CollectionStatus } from '#root/lib/schema';
import { RagCollectionConfig } from '@/shared/reducers/rag.reducer';

export function createMockCollection (overrides?: Partial<RagCollectionConfig>): RagCollectionConfig {
    return {
        collectionId: 'test-collection-1',
        repositoryId: 'test-repo-1',
        name: 'Test Collection',
        description: 'A test collection',
        embeddingModel: 'amazon.titan-embed-text-v1',
        chunkingStrategy: {
            type: ChunkingStrategyType.FIXED,
            size: 512,
            overlap: 50,
        },
        allowedGroups: [],
        createdBy: 'test-user',
        createdAt: '2024-01-01T00:00:00Z',
        updatedAt: '2024-01-01T00:00:00Z',
        status: CollectionStatus.ACTIVE,
        private: false,
        ...overrides,
    };
}

export function createMockCollections (count: number): RagCollectionConfig[] {
    return Array.from({ length: count }, (_, i) =>
        createMockCollection({
            collectionId: `test-collection-${i + 1}`,
            name: `Test Collection ${i + 1}`,
            repositoryId: `test-repo-${(i % 3) + 1}`,
        })
    );
}

export function createMockPublicCollection (overrides?: Partial<RagCollectionConfig>): RagCollectionConfig {
    return createMockCollection({
        allowedGroups: [],
        private: false,
        ...overrides,
    });
}

export function createMockPrivateCollection (groups: string[], overrides?: Partial<RagCollectionConfig>): RagCollectionConfig {
    return createMockCollection({
        allowedGroups: groups,
        private: true,
        ...overrides,
    });
}

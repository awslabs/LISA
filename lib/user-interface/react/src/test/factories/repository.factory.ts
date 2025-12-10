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

import { RagRepositoryConfig } from '#root/lib/schema';

export function createMockRepository (overrides?: Partial<RagRepositoryConfig>): RagRepositoryConfig {
    return {
        repositoryId: 'test-repo-1',
        repositoryName: 'Test Repository',
        type: 'OPENSEARCH',
        embeddingModelId: 'amazon.titan-embed-text-v1',
        allowedGroups: [],
        ...overrides,
    };
}

export function createMockRepositories (count: number): RagRepositoryConfig[] {
    return Array.from({ length: count }, (_, i) =>
        createMockRepository({
            repositoryId: `test-repo-${i + 1}`,
            repositoryName: `Test Repository ${i + 1}`,
        })
    );
}

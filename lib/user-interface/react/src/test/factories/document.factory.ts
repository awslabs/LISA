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

import { RagDocument, IngestionType } from '../../components/types';

export function createMockDocument(overrides?: Partial<RagDocument>): RagDocument {
    return {
        document_id: 'doc-123',
        document_name: 'test-document.pdf',
        repository_id: 'repo-456',
        collection_id: 'col-789',
        source: 's3://bucket/key',
        username: 'test-user',
        chunk_strategy: { type: 'fixed', size: 512, overlap: 50 },
        ingestion_type: 'manual' as IngestionType,
        upload_date: Date.now(),
        chunks: 10,
        ...overrides,
    };
}

export function createMockDocuments(count: number): RagDocument[] {
    return Array.from({ length: count }, (_, i) => 
        createMockDocument({
            document_id: `doc-${i + 1}`,
            document_name: `document-${i + 1}.pdf`,
        })
    );
}

export function createMockDocumentWithOwner(username: string, overrides?: Partial<RagDocument>): RagDocument {
    return createMockDocument({
        username,
        ...overrides,
    });
}

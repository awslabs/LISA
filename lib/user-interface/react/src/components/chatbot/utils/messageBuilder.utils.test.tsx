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

import { describe, it, expect } from 'vitest';
import { structureRagDocuments, buildMessageMetadata } from './messageBuilder.utils';

const makeDoc = (overrides: Record<string, any> = {}) => ({
    Document: {
        page_content: 'test content',
        metadata: {
            source: 's3://bucket/doc.pdf',
            name: 'doc.pdf',
            document_id: 'doc-1',
            repositoryId: 'repo-1',
            collectionId: 'col-1',
            ...overrides,
        },
    },
});

describe('structureRagDocuments', () => {
    it('extracts similarityScore from doc metadata', () => {
        const docs = [makeDoc({ similarity_score: 0.92 })];
        const result = structureRagDocuments(docs);
        expect(result).toHaveLength(1);
        expect(result[0].similarityScore).toBe(0.92);
    });

    it('handles missing similarity_score gracefully', () => {
        const docs = [makeDoc()];
        const result = structureRagDocuments(docs);
        expect(result).toHaveLength(1);
        expect(result[0].similarityScore).toBeUndefined();
    });

    it('deduplicates by source and keeps first score', () => {
        const docs = [
            makeDoc({ similarity_score: 0.95 }),
            makeDoc({ similarity_score: 0.80 }),
        ];
        const result = structureRagDocuments(docs);
        expect(result).toHaveLength(1);
        expect(result[0].similarityScore).toBe(0.95);
    });

    it('extracts all document fields correctly', () => {
        const docs = [makeDoc({
            similarity_score: 0.85,
            source: 's3://bucket/guide.pdf',
            name: 'guide.pdf',
            document_id: 'doc-42',
            repositoryId: 'repo-7',
            collectionId: 'col-3',
        })];
        const result = structureRagDocuments(docs);
        expect(result[0]).toEqual({
            documentId: 'doc-42',
            name: 'guide.pdf',
            source: 's3://bucket/guide.pdf',
            repositoryId: 'repo-7',
            collectionId: 'col-3',
            similarityScore: 0.85,
        });
    });

    it('sets documentId to null when document_id is missing', () => {
        const docs = [makeDoc({ document_id: undefined })];
        const result = structureRagDocuments(docs);
        expect(result[0].documentId).toBeNull();
    });

    it('returns empty array for null input', () => {
        expect(structureRagDocuments(null)).toEqual([]);
    });

    it('returns empty array for undefined input', () => {
        expect(structureRagDocuments(undefined)).toEqual([]);
    });

    it('returns empty array for non-array input', () => {
        expect(structureRagDocuments('not an array')).toEqual([]);
    });
});

describe('buildMessageMetadata', () => {
    const baseChatConfig = {
        sessionConfiguration: {
            imageGenerationArgs: {},
        },
    };

    it('includes ragSearchMetadata when response has metadata', async () => {
        const ragDocs = {
            data: {
                docs: [makeDoc({ similarity_score: 0.9 })],
                metadata: {
                    search_mode: 'hybrid',
                    actual_mode_used: 'hybrid',
                    backend: 'bedrock_knowledge_base',
                    hybrid_supported: true,
                },
            },
        };

        const result = await buildMessageMetadata({
            isImageGenerationMode: false,
            useRag: true,
            chatConfiguration: baseChatConfig,
            ragDocs,
        });

        expect(result.ragSearchMetadata).toEqual({
            searchMode: 'hybrid',
            actualModeUsed: 'hybrid',
            backend: 'bedrock_knowledge_base',
            hybridSupported: true,
        });
    });

    it('omits ragSearchMetadata for vector-only responses', async () => {
        const ragDocs = {
            data: {
                docs: [makeDoc()],
            },
        };

        const result = await buildMessageMetadata({
            isImageGenerationMode: false,
            useRag: true,
            chatConfiguration: baseChatConfig,
            ragDocs,
        });

        expect(result.ragSearchMetadata).toBeUndefined();
    });

    it('converts snake_case backend keys to camelCase', async () => {
        const ragDocs = {
            data: {
                docs: [makeDoc()],
                metadata: {
                    search_mode: 'hybrid',
                    actual_mode_used: 'vector',
                    backend: 'opensearch',
                    hybrid_supported: false,
                },
            },
        };

        const result = await buildMessageMetadata({
            isImageGenerationMode: false,
            useRag: true,
            chatConfiguration: baseChatConfig,
            ragDocs,
        });

        expect(result.ragSearchMetadata).toHaveProperty('searchMode');
        expect(result.ragSearchMetadata).toHaveProperty('actualModeUsed');
        expect(result.ragSearchMetadata).toHaveProperty('hybridSupported');
        expect(result.ragSearchMetadata).not.toHaveProperty('search_mode');
        expect(result.ragSearchMetadata).not.toHaveProperty('actual_mode_used');
        expect(result.ragSearchMetadata).not.toHaveProperty('hybrid_supported');
    });

    it('includes ragDocuments with scores in metadata', async () => {
        const ragDocs = {
            data: {
                docs: [makeDoc({ similarity_score: 0.88 })],
            },
        };

        const result = await buildMessageMetadata({
            isImageGenerationMode: false,
            useRag: true,
            chatConfiguration: baseChatConfig,
            ragDocs,
        });

        expect(result.ragDocuments).toBeDefined();
        expect(result.ragDocuments[0].similarityScore).toBe(0.88);
    });
});

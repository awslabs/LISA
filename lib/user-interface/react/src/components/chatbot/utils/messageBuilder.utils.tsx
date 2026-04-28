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

import { formatDocumentsAsString } from '@/components/utils';
import { RagDocumentCitation } from '@/components/types';

export type MessageContentParams = {
    isImageGenerationMode: boolean;
    fileContext: string;
    useRag: boolean;
    userPrompt: string;
    ragDocs?: any;
};

export const buildMessageContent = async ({
    isImageGenerationMode,
    fileContext,
    useRag,
    userPrompt,
    ragDocs,
}: MessageContentParams) => {
    if (isImageGenerationMode) {
        return userPrompt;
    }

    if (fileContext?.startsWith('File context: data:image')) {
        const imageData = fileContext.replace('File context: ', '');
        const content: Array<{ type: string; text?: string; image_url?: { url: string } }> = [
            { type: 'image_url', image_url: { url: imageData } },
        ];
        if (useRag && ragDocs) {
            content.push({
                type: 'text',
                text: 'Context from document search:\n' + formatDocumentsAsString(ragDocs.data?.docs),
            });
        }
        content.push({ type: 'text', text: userPrompt });
        return content;
    }

    const contextParts: string[] = [];
    if (fileContext) {
        contextParts.push(fileContext);
    }
    if (useRag && ragDocs) {
        contextParts.push(
            'Context from document search:\n' + formatDocumentsAsString(ragDocs.data?.docs),
        );
    }
    if (contextParts.length > 0) {
        return [
            { type: 'text', text: contextParts.join('\n\n') },
            { type: 'text', text: userPrompt },
        ];
    }

    return userPrompt;
};

/**
 * Structures RAG documents from search results, grouping by unique document.
 * Multiple chunks may come from the same document.
 * Includes all documents, even if they don't have document_id (for backward compatibility).
 */
export const structureRagDocuments = (docs: any): RagDocumentCitation[] => {
    if (!docs || !Array.isArray(docs)) return [];

    const uniqueDocs = new Map<string, RagDocumentCitation>();

    docs.forEach((doc) => {
        const metadata = doc.Document.metadata;
        const source = metadata.source;

        if (source && !uniqueDocs.has(source)) {
            uniqueDocs.set(source, {
                documentId: metadata.document_id || null,
                name: metadata.name || source.split('/').pop() || 'Unknown',
                source: source,
                repositoryId: metadata.repositoryId,
                collectionId: metadata.collectionId,
                similarityScore: metadata.similarity_score,
            });
        }
    });

    return Array.from(uniqueDocs.values());
};

export const buildMessageMetadata = async ({
    isImageGenerationMode,
    useRag,
    chatConfiguration,
    ragDocs,
}: {
    isImageGenerationMode: boolean;
    useRag: boolean;
    chatConfiguration: any;
    ragDocs?: any;
}) => {
    const metadata: any = {};

    if (isImageGenerationMode) {
        metadata.imageGenerationPrompt = true;
        metadata.imageGenerationSettings = chatConfiguration.sessionConfiguration.imageGenerationArgs;
    }

    if (useRag && !isImageGenerationMode && ragDocs) {
        metadata.ragContext = formatDocumentsAsString(ragDocs.data?.docs, true);
        metadata.ragDocuments = structureRagDocuments(ragDocs.data?.docs);

        if (ragDocs.data?.metadata) {
            const m = ragDocs.data.metadata;
            metadata.ragSearchMetadata = {
                searchMode: m.search_mode,
                actualModeUsed: m.actual_mode_used,
                backend: m.backend,
                hybridSupported: m.hybrid_supported,
            };
        }
    }

    return metadata;
};

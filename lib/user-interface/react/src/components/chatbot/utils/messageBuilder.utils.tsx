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

import { formatDocumentsAsString, formatDocumentTitlesAsString } from '@/components/utils';

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
        return [
            { type: 'image_url', image_url: { url: imageData } },
            { type: 'text', text: userPrompt },
        ];
    }

    if (useRag && ragDocs) {
        return [
            { type: 'text', text: 'File context: ' + formatDocumentsAsString(ragDocs.data?.docs) },
            { type: 'text', text: userPrompt },
        ];
    }

    if (fileContext) {
        return [
            { type: 'text', text: fileContext },
            { type: 'text', text: userPrompt },
        ];
    }

    return userPrompt;
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
        metadata.ragDocuments = formatDocumentTitlesAsString(ragDocs.data?.docs);
    }

    return metadata;
};

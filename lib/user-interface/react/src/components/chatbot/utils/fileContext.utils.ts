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

const DATA_IMAGE_URL_REGEX = /data:image\/[^;]+;base64,[A-Za-z0-9+/=]+/;

export type FileContextFile = {
    name: string;
    content: string;
};

/**
 * Extract the first embedded image data URL from file context.
 * Supports legacy `File context: data:image/...` and multi-file
 * `File context:\n--- File: name ---\ndata:image/...` formats.
 */
export function extractImageDataUrlFromFileContext (
    fileContext: string,
    fileContextFiles?: FileContextFile[],
): string | null {
    if (fileContextFiles?.length) {
        for (const file of fileContextFiles) {
            const match = file.content.match(DATA_IMAGE_URL_REGEX);
            if (match) {
                return match[0];
            }
        }
    }

    if (!fileContext?.trim()) {
        return null;
    }

    const match = fileContext.match(DATA_IMAGE_URL_REGEX);
    return match ? match[0] : null;
}

export function imageDataUrlToBlob (dataUrl: string): Blob | null {
    const matches = dataUrl.match(/^data:(image\/[^;]+);base64,(.+)$/);
    if (!matches) {
        return null;
    }

    const mimeType = matches[1];
    const base64Data = matches[2];
    const binaryString = atob(base64Data);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
    }
    return new Blob([bytes], { type: mimeType });
}

export function extractImageBlobFromFileContext (
    fileContext: string,
    fileContextFiles?: FileContextFile[],
): Blob | null {
    const dataUrl = extractImageDataUrlFromFileContext(fileContext, fileContextFiles);
    if (!dataUrl) {
        return null;
    }
    return imageDataUrlToBlob(dataUrl);
}

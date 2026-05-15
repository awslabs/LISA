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

export type ParsedAwsCredentials = {
    accessKeyId: string;
    secretAccessKey: string;
    sessionToken?: string;
};

const ENV_VAR =
    (name: string) =>
    new RegExp(
        `(?:^|\\n)\\s*(?:export\\s+)?${name}\\s*=\\s*(?:"([^"]*)"|'([^']*)'|([^\\s\\n]+))`,
        'm',
    );

const ACCESS_KEY_ID_PATTERN = ENV_VAR('AWS_ACCESS_KEY_ID');
const SECRET_ACCESS_KEY_PATTERN = ENV_VAR('AWS_SECRET_ACCESS_KEY');
const SESSION_TOKEN_PATTERN = ENV_VAR('AWS_SESSION_TOKEN');

const captureValue = (match: RegExpMatchArray | null): string | undefined => {
    if (!match) return undefined;
    return match[1] ?? match[2] ?? match[3];
};

/**
 * Parses shell-style AWS credential exports (e.g. Isengard `export AWS_*=...` blocks).
 * Returns null unless both access key ID and secret access key are present.
 */
export const parseAwsCredentialExport = (text: string): ParsedAwsCredentials | null => {
    const accessKeyId = captureValue(text.match(ACCESS_KEY_ID_PATTERN));
    const secretAccessKey = captureValue(text.match(SECRET_ACCESS_KEY_PATTERN));
    if (!accessKeyId || !secretAccessKey) {
        return null;
    }

    const sessionToken = captureValue(text.match(SESSION_TOKEN_PATTERN));
    return {
        accessKeyId,
        secretAccessKey,
        ...(sessionToken ? { sessionToken } : {}),
    };
};

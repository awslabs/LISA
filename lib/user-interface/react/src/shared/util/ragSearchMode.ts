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

/**
 * Derives the effective RAG search mode. When hybrid is disabled globally or
 * the repository doesn't support it, always returns 'vector' regardless of
 * user choice. Otherwise defaults to 'hybrid' unless the user explicitly chose.
 */
export function deriveRagSearchMode (
    userChoice: 'vector' | 'hybrid' | undefined,
    hybridEnabled: boolean,
    repoSupportsHybrid: boolean,
): 'vector' | 'hybrid' {
    if (!hybridEnabled || !repoSupportsHybrid) return 'vector';
    return userChoice ?? 'hybrid';
}

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
 * Derives the effective RAG search mode. When the user hasn't made an explicit
 * choice (undefined), the system defaults to 'hybrid' if both the admin toggle
 * and repository capability are enabled, otherwise 'vector'.
 */
export function deriveRagSearchMode (
    userChoice: 'vector' | 'hybrid' | undefined,
    hybridEnabled: boolean,
    repoSupportsHybrid: boolean,
): 'vector' | 'hybrid' {
    return userChoice ?? ((hybridEnabled && repoSupportsHybrid) ? 'hybrid' : 'vector');
}

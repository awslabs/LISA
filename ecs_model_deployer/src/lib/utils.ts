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

import { EcsClusterConfig } from '#root/lib/schema';

/**
 * Creates a "normalized" identifier based on the provided model config. If a modelId has been
 * defined the id will be used otherwise the model name will be used. This normalized identifier
 * strips all non alpha numeric characters.
 *
 * @param {EcsClusterConfig} modelConfig model config
 * @returns {string} normalized model name for use in CDK identifiers/resource names
 */
export function getModelIdentifier (modelConfig: EcsClusterConfig): string {
    return (modelConfig.modelId || modelConfig.modelName).replace(/[^a-zA-Z0-9]/g, '');
}

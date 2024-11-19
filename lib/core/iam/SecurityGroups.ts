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
 * List of all security groups used for overrides
 */
export enum SecurityGroups {
    LITE_LLM_SG = 'LiteLLMScalingSg',
    ECS_MODEL_ALB_SG = 'EcsModelAlbSg',
    REST_API_ALB_SG = 'RestApiAlbSg',
    LAMBDA_SG = 'LambdaSg',
    OPEN_SEARCH_SG = 'OpenSearchSg',
    PG_VECTOR_SG = 'PGVectorSg',
}

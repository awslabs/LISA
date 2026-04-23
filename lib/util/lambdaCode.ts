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

import * as path from 'node:path';

import { Code } from 'aws-cdk-lib/aws-lambda';

import { LAMBDA_HANDLERS_PATH } from './paths';

/**
 * Known handler packages. Each entry is a directory under `lambda/handlers/`
 * that owns one or more Lambda functions. Shared library code lives in
 * `lambda/shared/` and is attached to every Python Lambda via the
 * `LisaSharedLayer` layer — it is NOT included in any handler asset.
 *
 * Adding a new handler means:
 *   1. Create `lambda/handlers/<name>/` with its Python source.
 *   2. Add `<name>` to this list.
 *   3. Call `lambdaCodeAsset('<name>', config)` from the construct defining
 *      the Lambda.
 */
export const LAMBDA_HANDLERS = [
    'api_tokens',
    'authorizer',
    'chat_assistant_stacks',
    'configuration',
    'db_setup_iam_auth',
    'dockerimagebuilder',
    'management_key',
    'mcp_server',
    'mcp_workbench',
    'metrics',
    'models',
    'projects',
    'prompt_templates',
    'repository',
    'session',
    'user_preferences',
] as const;

export type LambdaHandler = typeof LAMBDA_HANDLERS[number];

/**
 * Returns the deploy asset for a Lambda handler. The asset is exactly the
 * `lambda/handlers/<handler>/` directory — no excludes, no dependency map.
 * All shared Python code is supplied via the `LisaSharedLayer` Lambda layer
 * mounted at `/opt/python/lisa/`.
 *
 * If `config.lambdaPath` is set to a prebuilt zip (air-gapped/ADC deployments
 * that ship a single precompiled bundle), the zip is passed through as-is.
 */
export function lambdaCodeAsset (
    handler: LambdaHandler,
    config?: { lambdaPath?: string },
): Code {
    if (config?.lambdaPath && config.lambdaPath.endsWith('.zip')) {
        return Code.fromAsset(config.lambdaPath);
    }

    return Code.fromAsset(path.join(LAMBDA_HANDLERS_PATH, handler));
}

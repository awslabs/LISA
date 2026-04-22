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

import { IAspect } from 'aws-cdk-lib';
import { ContainerDefinition } from 'aws-cdk-lib/aws-ecs';
import { Function, SingletonFunction } from 'aws-cdk-lib/aws-lambda';
import { IConstruct } from 'constructs';

/**
 * CDK Aspect that injects the CORS_ALLOWED_ORIGIN environment variable into all
 * Lambda functions and ECS container definitions in the stack.
 *
 * Lambda response builders and FastAPI middleware read this env var to set the
 * Access-Control-Allow-Origin header, replacing the previous hardcoded wildcard (*).
 *
 * For single-origin deployments (the common case), this is the origin echoed back.
 * For multi-origin deployments, API Gateway preflight handles validation; the Lambda
 * returns the first configured origin as a safe default.
 */
export class CorsOriginAspect implements IAspect {
    private readonly corsOrigin: string;

    /**
     * @param corsAllowedOrigins - The configured CORS allowed origins string
     *   (comma-separated). The first origin is used for Lambda response headers.
     *   Pass '*' to preserve wildcard behavior.
     */
    constructor (corsAllowedOrigins: string) {
        // Use the first origin for the Lambda response header.
        // API Gateway preflight OPTIONS handles multi-origin validation.
        const origins = corsAllowedOrigins.split(',').map((o) => o.trim()).filter(Boolean);
        this.corsOrigin = origins[0] || '*';
    }

    public visit (node: IConstruct): void {
        if (node instanceof Function || node instanceof SingletonFunction) {
            node.addEnvironment('CORS_ALLOWED_ORIGIN', this.corsOrigin);
        } else if (node instanceof ContainerDefinition) {
            node.addEnvironment('CORS_ALLOWED_ORIGIN', this.corsOrigin);
        }
    }
}

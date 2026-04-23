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
 * IMPORTANT: The Access-Control-Allow-Origin response header only supports a single
 * origin value (or '*'). For multi-origin deployments, this aspect uses the first
 * configured origin. API Gateway preflight OPTIONS handles multi-origin validation;
 * runtime services (FastAPI) that need multi-origin support should use CORS_ORIGINS
 * (the full comma-separated list) instead.
 *
 * TODO: Unify CORS env var naming. Currently two env vars serve different purposes:
 *   - CORS_ALLOWED_ORIGIN (single value) — used by Lambda response_builder.py and
 *     MCP workbench auth.py for the Access-Control-Allow-Origin response header.
 *   - CORS_ORIGINS (comma-separated list) — used by FastAPI CORSMiddleware in
 *     fastapi_factory.py and rest-api main.py for multi-origin middleware config.
 * Both are intentional (single-value header vs. multi-origin middleware), but the
 * naming is confusing. A future cleanup could consolidate to a single env var with
 * runtime logic to pick the right value per use case.
 */
export class CorsOriginAspect implements IAspect {
    private readonly corsOrigin: string;

    /**
     * @param corsAllowedOrigins - The configured CORS allowed origins string
     *   (comma-separated). The first origin is used for Lambda response headers
     *   because Access-Control-Allow-Origin only accepts a single value.
     *   Pass '*' to preserve wildcard behavior.
     */
    constructor (corsAllowedOrigins: string) {
        const origins = corsAllowedOrigins.split(',').map((o) => o.trim()).filter(Boolean);
        if (origins.length > 1) {
            console.warn(
                `CorsOriginAspect: Multiple CORS origins configured (${origins.length}). ` +
                `Only the first origin ('${origins[0]}') will be used for CORS_ALLOWED_ORIGIN. ` +
                'Runtime services should use CORS_ORIGINS for full multi-origin support.'
            );
        }
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

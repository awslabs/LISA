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

export const CA_BUNDLE = '/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem';
export const CA_BUNDLE_ENV_VARS = ['AWS_CA_BUNDLE', 'REQUESTS_CA_BUNDLE', 'SSL_CERT_FILE'];

/**
 * This Aspect will add CA bundle env vars to all lambda functions in the stack.
 */
export class AdcLambdaCABundleAspect implements IAspect {
    public visit (node: IConstruct): void {
        if (node instanceof Function || node instanceof SingletonFunction || node instanceof ContainerDefinition) {
            CA_BUNDLE_ENV_VARS.forEach((envVar) => node.addEnvironment(envVar, CA_BUNDLE));
        }
    }
}

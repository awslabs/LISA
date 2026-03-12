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

import { IAspect, RemovalPolicy } from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import { IConstruct } from 'constructs';

/**
 * Applies Lambda versioning to all Lambda functions in the CDK application.
 * Creates a lambda.Version for each lambda.Function to ensure CloudFormation
 * can roll back to a previous version during failed stack updates.
 */
export class LambdaVersioningAspect implements IAspect {
    public visit (node: IConstruct): void {
        if (node instanceof lambda.Function) {
            if (!node.node.tryFindChild('Version')) {
                new lambda.Version(node, 'Version', {
                    lambda: node,
                    removalPolicy: RemovalPolicy.RETAIN,
                });
            }
        }
    }
}

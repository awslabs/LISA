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
import { Function as LambdaFunction, CfnFunction } from 'aws-cdk-lib/aws-lambda';
import { LogGroup, RetentionDays } from 'aws-cdk-lib/aws-logs';
import { IConstruct } from 'constructs';

/**
 * Default log retention period for Lambda functions (1 year).
 */
export const DEFAULT_LOG_RETENTION = RetentionDays.ONE_YEAR;

/**
 * Aspect that ensures all Lambda functions have CloudWatch Log Groups with retention configured.
 * This creates explicit LogGroup resources for Lambda functions that don't have logRetention set,
 * ensuring logs are properly retained and the log group is created during deployment.
 */
export class LambdaLogRetentionAspect implements IAspect {
    private readonly retention: RetentionDays;
    private readonly removalPolicy: RemovalPolicy;
    private readonly processedFunctions: Set<string> = new Set();

    /**
     * Creates a new LambdaLogRetentionAspect.
     * @param retention - The log retention period (default: 1 year)
     * @param removalPolicy - The removal policy for log groups (default: RETAIN)
     */
    constructor (retention: RetentionDays = DEFAULT_LOG_RETENTION, removalPolicy: RemovalPolicy = RemovalPolicy.RETAIN) {
        this.retention = retention;
        this.removalPolicy = removalPolicy;
    }

    public visit (node: IConstruct): void {
        // Handle L2 Lambda Function constructs
        if (node instanceof LambdaFunction) {
            this.ensureLogGroup(node);
        }
    }

    private ensureLogGroup (lambdaFunction: LambdaFunction): void {
        const functionName = lambdaFunction.functionName;

        // Skip if we've already processed this function (avoid duplicates)
        if (this.processedFunctions.has(functionName)) {
            return;
        }

        // Check if a LogGroup already exists for this function by looking at children
        const existingLogGroup = lambdaFunction.node.tryFindChild('LogGroup');
        if (existingLogGroup) {
            this.processedFunctions.add(functionName);
            return;
        }

        // Check if logRetention was set (CDK creates a LogRetention custom resource)
        const logRetentionResource = lambdaFunction.node.tryFindChild('LogRetention');
        if (logRetentionResource) {
            this.processedFunctions.add(functionName);
            return;
        }

        // Create an explicit LogGroup for this Lambda function
        // The log group name must match the Lambda's expected log group: /aws/lambda/<function-name>
        const cfnFunction = lambdaFunction.node.defaultChild as CfnFunction;
        const logGroupName = `/aws/lambda/${cfnFunction.ref}`;

        new LogGroup(lambdaFunction, 'LogGroup', {
            logGroupName,
            retention: this.retention,
            removalPolicy: this.removalPolicy,
        });

        this.processedFunctions.add(functionName);
    }
}

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

// BRASS Stack.
import { Stack, StackProps } from 'aws-cdk-lib';
import { IAuthorizer } from 'aws-cdk-lib/aws-apigateway';
import { ISecurityGroup } from 'aws-cdk-lib/aws-ec2';
import { Construct } from 'constructs';

import { BrassAuthApi } from './api/brass-auth';
import { BaseProps } from '../schema';
import { Vpc } from '../networking/vpc';

/**
 * Properties for LisaBrassApplicationConstruct
 * 
 * @interface LisaBrassProps
 * @extends BaseProps
 * @extends StackProps
 */
export type LisaBrassProps = {
    /** Optional API Gateway authorizer for securing endpoints */
    authorizer?: IAuthorizer;
    /** REST API ID from the API base construct */
    restApiId: string;
    /** Root resource ID for API Gateway resource tree */
    rootResourceId: string;
    /** Security groups for Lambda function network access */
    securityGroups: ISecurityGroup[];
    /** VPC configuration for Lambda deployment */
    vpc: Vpc;
} & BaseProps & StackProps;

/**
 * LISA BRASS Application Construct.
 * 
 * This construct creates the BRASS authorization API infrastructure, including:
 * - Lambda functions for BRASS authorization requests
 * - API Gateway endpoints for frontend integration
 * - IAM roles and permissions for BRASS service access
 * - VPC and security group configuration
 * 
 * The construct integrates with the existing LISA API Gateway and provides
 * a `/brass/authorize` endpoint for checking bindle lock permissions.
 * 
 * @example
 * ```typescript
 * new LisaBrassApplicationConstruct(scope, 'LisaBrass', {
 *   config,
 *   restApiId: apiBase.restApiId,
 *   rootResourceId: apiBase.rootResourceId,
 *   securityGroups: [vpc.lambdaSg],
 *   vpc: vpc,
 *   authorizer: apiBase.authorizer
 * });
 * ```
 */
export class LisaBrassApplicationConstruct extends Construct {
    /**
     * Initialize the LISA BRASS Application Construct
     * 
     * @param scope - The parent construct (typically a Stack)
     * @param id - Unique identifier for this construct within the scope
     * @param props - Configuration properties for the BRASS construct
     */
    constructor (scope: Stack, id: string, props: LisaBrassProps) {
        super(scope, id);

        const { authorizer, config, restApiId, rootResourceId, securityGroups, vpc } = props;

        // Create BRASS authorization API with Lambda backend
        // This provides the `/brass/authorize` endpoint for frontend BRASS requests
        new BrassAuthApi(scope, 'BrassAuthApi', {
            authorizer,
            config,
            restApiId,
            rootResourceId,
            securityGroups,
            vpc,
        });
    }
}

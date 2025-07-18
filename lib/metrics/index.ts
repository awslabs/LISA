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

import { Stack, StackProps } from 'aws-cdk-lib';
import { IAuthorizer } from 'aws-cdk-lib/aws-apigateway';
import { ISecurityGroup } from 'aws-cdk-lib/aws-ec2';
import { Construct } from 'constructs';

import { BaseProps } from '../schema';
import { Vpc } from '../networking/vpc';
import { MetricsConstruct } from './metricsConstruct';

/**
 * Properties for LisaMetricsStack.
 */
export type LisaMetricsStackProps = {
    authorizer: IAuthorizer;
    restApiId: string;
    rootResourceId: string;
    securityGroups: ISecurityGroup[];
    vpc: Vpc;
} & BaseProps & StackProps;

/**
 * LISA Metrics stack.
 */
export class LisaMetricsStack extends Stack {
    /**
     * @param {Construct} scope - The parent or owner of the construct.
     * @param {string} id - The unique identifier for the construct within its scope.
     * @param {LisaMetricsStackProps} props - Properties for the Stack.
     */
    constructor (scope: Construct, id: string, props: LisaMetricsStackProps) {
        super(scope, id, props);

        new MetricsConstruct(this, id, props).node.addMetadata('aws:cdk:path', this.node.path);

    }
}

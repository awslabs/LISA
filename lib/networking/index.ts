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

import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';

import { Vpc } from './vpc';
import { BaseProps } from '../schema/app-private';

/**
 * Lisa Networking stack.
 */
type LisaNetworkingStackProps = {} & BaseProps & cdk.StackProps;

/**
 * Lisa Networking stack. Defines a VPC for LISA
 */
export class LisaNetworkingStack extends cdk.Stack {
    /** Virtual private cloud. */
    public readonly vpc: Vpc;

    /**
   * @param {Construct} scope - The parent or owner of the construct.
   * @param {string} id - The unique identifier for the construct within its scope.
   * @param {LisaNetworkingStackProps} props - Properties for the Stack.
   */
    constructor (scope: Construct, id: string, props: LisaNetworkingStackProps) {
        super(scope, id, props);

        const { config } = props;

        // Create VPC
        this.vpc = new Vpc(this, 'Vpc', {
            config: config,
        });
    }
}

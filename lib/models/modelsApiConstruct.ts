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

// LisaModelsApi Stack.
import { Stack, StackProps } from 'aws-cdk-lib';
import { IAuthorizer } from 'aws-cdk-lib/aws-apigateway';
import { ISecurityGroup } from 'aws-cdk-lib/aws-ec2';
import { Construct } from 'constructs';

import { Vpc } from '../networking/vpc';
import { ModelsApi } from './model-api';
import { BaseProps } from '../schema';
export type LisaModelsApiProps = BaseProps &
  StackProps & {
      authorizer?: IAuthorizer;
      restApiId: string;
      rootResourceId: string;
      securityGroups: ISecurityGroup[];
      vpc: Vpc;
  };

/**
 * Lisa Models API Construct.
 */
export class LisaModelsApiConstruct extends Construct {
    /**
   * @param {Stack} scope - The parent or owner of the construct.
   * @param {string} id - The unique identifier for the construct within its scope.
   * @param {LisaModelsApiProps} props - Properties for the Stack.
   */
    constructor (scope: Stack, id: string, props: LisaModelsApiProps) {
        super(scope, id);

        const { authorizer, config, restApiId, rootResourceId, securityGroups, vpc } = props;

        // Add REST API Lambdas to APIGW
        new ModelsApi(scope, 'ModelsApi', {
            authorizer,
            config,
            restApiId,
            rootResourceId,
            securityGroups,
            vpc,
        });
    }
}

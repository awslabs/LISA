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
import { Construct } from 'constructs';
import { BaseProps } from '../schema';
import { McpWorkbenchConstruct } from './mcpWorkbenchConstruct';
import { Vpc } from '../networking/vpc';
import { ECSCluster } from '../api-base/ecsCluster';
import { IAuthorizer } from 'aws-cdk-lib/aws-apigateway';

export type McpWorkbenchStackProps = {
    vpc: Vpc;
    restApiId: string;
    rootResourceId: string;
    apiCluster: ECSCluster;
    authorizer?: IAuthorizer;
} & BaseProps & StackProps;

export class McpWorkbenchStack extends Stack {
    constructor (scope: Construct, id: string, props: McpWorkbenchStackProps) {
        super(scope, id, props);

        const { vpc, restApiId, rootResourceId, authorizer, apiCluster } = props;

        new McpWorkbenchConstruct(this, 'McpWorkbench', {
            ...props,
            restApiId,
            rootResourceId,
            securityGroups: [vpc.securityGroups.ecsModelAlbSg],
            vpc: vpc,
            apiCluster,
            authorizer
        });
    }
}
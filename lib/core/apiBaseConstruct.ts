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
import { Authorizer, Cors, EndpointType, RestApi, StageOptions } from 'aws-cdk-lib/aws-apigateway';
import { Construct } from 'constructs';

import { CustomAuthorizer } from '../api-base/authorizer';
import { BaseProps } from '../schema';
import { Vpc } from '../networking/vpc';
import { Role } from 'aws-cdk-lib/aws-iam';
import { ITable } from 'aws-cdk-lib/aws-dynamodb';
import McpWorkbenchConstruct from '../serve/mcpWorkbenchConstruct';

export type LisaApiBaseProps = {
    vpc: Vpc;
    tokenTable: ITable | undefined;
} & BaseProps &
    StackProps;

/**
 * Base stack resources for LISA REST API
 */
export class LisaApiBaseConstruct extends Construct {
    public readonly restApi: RestApi;
    public readonly authorizer?: Authorizer;
    public readonly restApiId: string;
    public readonly rootResourceId: string;
    public readonly restApiUrl: string;

    constructor (scope: Stack, id: string, props: LisaApiBaseProps) {
        super(scope, id);

        const { config, vpc, tokenTable } = props;

        const deployOptions: StageOptions = {
            stageName: config.deploymentStage,
            throttlingRateLimit: 100,
            throttlingBurstLimit: 100,
        };

        if (config.authConfig) {
            // Create the authorizer Lambda for APIGW
            const authorizer = new CustomAuthorizer(scope, 'LisaApiAuthorizer', {
                config: config,
                securityGroups: [vpc.securityGroups.lambdaSg],
                tokenTable,
                vpc,
                ...(config.roles &&
                {
                    role: Role.fromRoleName(scope, 'AuthorizerRole', config.roles.RestApiAuthorizerRole),
                })
            });
            this.authorizer = authorizer.authorizer;
        }

        const restApi = new RestApi(scope, `${scope.node.id}-RestApi`, {
            description: 'Base API Gateway for LISA.',
            endpointConfiguration: { types: [config.privateEndpoints ? EndpointType.PRIVATE : EndpointType.REGIONAL] },
            deploy: true,
            deployOptions,
            defaultCorsPreflightOptions: {
                allowOrigins: Cors.ALL_ORIGINS,
                allowHeaders: [...Cors.DEFAULT_HEADERS],
            },
            // Support binary media types used for documentation images and fonts
            binaryMediaTypes: ['font/*', 'image/*'],
        });

        const workbench = new McpWorkbenchConstruct(this, id + 'McpWorkbench', {
            ...props,
            authorizer: this.authorizer!,
            restApiId: restApi.restApiId,
            rootResourceId: restApi.restApiRootResourceId,
            securityGroups: [props.vpc.securityGroups.ecsModelAlbSg],
        });

        this.restApi = restApi;
        this.restApiId = restApi.restApiId;
        this.rootResourceId = restApi.restApiRootResourceId;
        this.restApiUrl = restApi.url;
    }
}

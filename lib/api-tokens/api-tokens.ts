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

import crypto from 'node:crypto';
import { IAuthorizer, RestApi } from 'aws-cdk-lib/aws-apigateway';
import { ISecurityGroup } from 'aws-cdk-lib/aws-ec2';
import { IRole } from 'aws-cdk-lib/aws-iam';
import { LayerVersion } from 'aws-cdk-lib/aws-lambda';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';

import { getPythonRuntime, PythonLambdaFunction, registerAPIEndpoint } from '../api-base/utils';
import { BaseProps } from '../schema';
import { Vpc } from '../networking/vpc';
import { createLambdaRole } from '../core/utils';
import { LAMBDA_PATH } from '../util';
import { Table } from 'aws-cdk-lib/aws-dynamodb';

/**
 * Properties for ApiTokensApi Construct.
 *
 * @property {Vpc} vpc - Stack VPC
 * @property {string} restApiId - REST APIGW ID
 * @property {string} rootResourceId - Root resource ID for API
 * @property {IAuthorizer} authorizer - APIGW authorizer
 * @property {ISecurityGroup[]} securityGroups - Security groups for Lambdas
 */
export type ApiTokensApiProps = BaseProps & {
    authorizer?: IAuthorizer;
    restApiId: string;
    rootResourceId: string;
    securityGroups: ISecurityGroup[];
    vpc: Vpc;
};

/**
 * API for managing API Tokens
 */
export class ApiTokensApi extends Construct {
    constructor (scope: Construct, id: string, props: ApiTokensApiProps) {
        super(scope, id);

        const { authorizer, config, restApiId, rootResourceId, securityGroups, vpc } = props;

        // Get lambda layers from SSM
        const commonLambdaLayer = LayerVersion.fromLayerVersionArn(
            this,
            'api-tokens-common-lambda-layer',
            StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/layerVersion/common`),
        );

        const fastapiLambdaLayer = LayerVersion.fromLayerVersionArn(
            this,
            'api-tokens-fastapi-lambda-layer',
            StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/layerVersion/fastapi`),
        );

        const lambdaLayers = [commonLambdaLayer, fastapiLambdaLayer];

        // Reference existing REST API
        const restApi = RestApi.fromRestApiAttributes(this, 'RestApi', {
            restApiId: restApiId,
            rootResourceId: rootResourceId,
        });

        // Reference existing token table via SSM parameter
        const tokenTableName = StringParameter.valueForStringParameter(
            this,
            `${config.deploymentPrefix}/tokenTableName`
        );
        const tokenTable = Table.fromTableName(this, 'TokenTable', tokenTableName);

        // Generate random disambiguator for endpoint variations
        const generateDisambiguator = (size: number): string =>
            Buffer.from(
                crypto.getRandomValues(new Uint8Array(Math.ceil(size / 2))),
            )
                .toString('hex')
                .slice(0, size);

        const environment = {
            TOKEN_TABLE_NAME: tokenTable.tableName,
            ADMIN_GROUP: config.authConfig?.adminGroup || '',
        };

        // Create Lambda role with DynamoDB permissions
        const lambdaRole: IRole = createLambdaRole(
            this,
            config.deploymentName,
            'ApiTokensApi',
            tokenTable.tableArn,
            config.roles?.ApiTokensApiRole
        );

        const lambdaPath = config.lambdaPath || LAMBDA_PATH;

        // Create main proxy handler for /api-tokens/{proxy+}
        const lambdaFunction = registerAPIEndpoint(
            this,
            restApi,
            lambdaPath,
            lambdaLayers,
            {
                name: 'handler',
                resource: 'api_tokens',
                description: 'Manage API tokens',
                path: 'api-tokens/{proxy+}',
                method: 'ANY',
                environment
            },
            getPythonRuntime(),
            vpc,
            securityGroups,
            authorizer,
            lambdaRole,
        );

        // Grant DynamoDB permissions
        tokenTable.grantReadWriteData(lambdaFunction);

        // Register additional endpoints without trailing slash
        const apis: PythonLambdaFunction[] = [
            {
                name: 'handler',
                resource: 'api_tokens',
                description: 'List tokens or create own token',
                path: 'api-tokens',
                method: 'GET',
                disambiguator: generateDisambiguator(4),
                existingFunction: lambdaFunction.functionArn,
            },
            {
                name: 'handler',
                resource: 'api_tokens',
                description: 'Create own API token',
                path: 'api-tokens',
                method: 'POST',
                disambiguator: generateDisambiguator(4),
                existingFunction: lambdaFunction.functionArn,
            },
            {
                name: 'docs',
                resource: 'api_tokens',
                description: 'API tokens documentation',
                path: 'api-tokens/docs',
                method: 'GET',
                disableAuthorizer: true,
                environment
            },
            {
                name: 'handler',
                resource: 'api_tokens',
                description: 'Get API definition',
                path: 'api-tokens/openapi.json',
                method: 'GET',
                disambiguator: generateDisambiguator(4),
                existingFunction: lambdaFunction.functionArn,
                disableAuthorizer: true,
            },
        ];

        apis.forEach((f) => {
            registerAPIEndpoint(
                this,
                restApi,
                lambdaPath,
                lambdaLayers,
                f,
                getPythonRuntime(),
                vpc,
                securityGroups,
                authorizer,
                lambdaRole,
            );
        });
    }
}

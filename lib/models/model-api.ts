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

import { IAuthorizer, Method, RestApi } from 'aws-cdk-lib/aws-apigateway';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import { ISecurityGroup, IVpc } from 'aws-cdk-lib/aws-ec2';
import { IRole, ServicePrincipal } from 'aws-cdk-lib/aws-iam';
import { LayerVersion } from 'aws-cdk-lib/aws-lambda';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';

import { PythonLambdaFunction, registerAPIEndpoint } from '../api-base/utils';
import { BaseProps } from '../schema';
import crypto from 'node:crypto'

/**
 * Properties for SessionApi Construct.
 *
 * @property {IVpc} vpc - Stack VPC
 * @property {Layer} commonLayer - Lambda layer for all Lambdas.
 * @property {IRestApi} restAPI - REST APIGW for UI and Lambdas
 * @property {IRole} lambdaExecutionRole - Execution role for lambdas
 * @property {IAuthorizer} authorizer - APIGW authorizer
 * @property {ISecurityGroup[]} securityGroups - Security groups for Lambdas
 */
type ModelsApiProps = BaseProps & {
  authorizer: IAuthorizer;
  lambdaExecutionRole?: IRole;
  restApiId: string;
  rootResourceId: string;
  securityGroups?: ISecurityGroup[];
  vpc?: IVpc;
}

/**
 * API for managing Models
 */
export class ModelsApi extends Construct {
  constructor(scope: Construct, id: string, props: ModelsApiProps) {
    super(scope, id);

    const { authorizer, config, lambdaExecutionRole, restApiId, rootResourceId, securityGroups, vpc } = props;

    // Get common layer based on arn from SSM due to issues with cross stack references
    const commonLambdaLayer = LayerVersion.fromLayerVersionArn(
      this,
      'session-common-lambda-layer',
      StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/layerVersion/common`),
    );

    const restApi = RestApi.fromRestApiAttributes(this, 'RestApi', {
      restApiId: restApiId,
      rootResourceId: rootResourceId,
    });

    // generates a random hexidecimal string of a specific length
    const generateDisambiguator = (size: number): string => Buffer.from(
      // one byte is 2 hex characters so only generate ceil(size/2) bytse of randomness
      crypto.getRandomValues(new Uint8Array(Math.ceil(size/2)))
    ).toString('hex').slice(0,size);

    // create proxy hanlder
    const lambdaFunction = registerAPIEndpoint(
      this,
      restApi,
      authorizer,
      config.lambdaSourcePath,
      [commonLambdaLayer],
      {
        name: 'handler',
        resource: 'models',
        description: 'Manage model',
        path: 'models/{proxy+}',
        method: "ANY",
      },
      config.lambdaConfig.pythonRuntime,
      lambdaExecutionRole,
      vpc,
      securityGroups,
    );

    const apis: PythonLambdaFunction[] = [
      // create endpoint for /models without a trailing slash but reuse
      // the proxy lambda so there aren't cold start issues
      {
        name: 'handler',
        resource: 'models',
        description: 'Get models',
        path: 'models',
        method: "GET",
        disambiguator: generateDisambiguator(4),
        existingFunction: lambdaFunction.functionArn
      },

      // create an endpoints for the docs
      {
        name: 'docs',
        resource: 'models',
        description: 'Manage model',
        path: 'docs',
        method: "GET",
        disableAuthorizer: true
      },
      {
        name: 'handler',
        resource: 'models',
        description: 'Get API definition',
        path: 'openapi.json',
        method: "GET",
        disambiguator: generateDisambiguator(4),
        existingFunction: lambdaFunction.functionArn,
        disableAuthorizer: true
      },
    ];

    apis.forEach((f) => {
      const handler = registerAPIEndpoint(
        this,
        restApi,
        authorizer,
        config.lambdaSourcePath,
        [commonLambdaLayer],
        f,
        config.lambdaConfig.pythonRuntime,
        lambdaExecutionRole,
        vpc,
        securityGroups
      );
    });
  }
}

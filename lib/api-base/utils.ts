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

/*
 * Your use of this service is governed by the terms of the AWS Customer Agreement
 * (https://aws.amazon.com/agreement/) or other agreement with AWS governing your use of
 * AWS services. Each license to use the service, including any related source code component,
 * is valid for use associated with the related specific task-order contract as defined by
 * 10 U.S.C. 3401 and 41 U.S.C. 4101.
 *
 * Copyright 2023 Amazon.com, Inc. or its affiliates. All Rights Reserved. This is AWS Content
 * subject to the terms of the AWS Customer Agreement.
 */
import * as cdk from 'aws-cdk-lib';
import { Duration } from 'aws-cdk-lib';
import {
  AuthorizationType,
  IAuthorizer,
  IResource,
  LambdaIntegration,
  IRestApi,
  Cors,
} from 'aws-cdk-lib/aws-apigateway';
import { ISecurityGroup, IVpc } from 'aws-cdk-lib/aws-ec2';
import { IRole } from 'aws-cdk-lib/aws-iam';
import { Code, Function, Runtime, ILayerVersion, IFunction, CfnPermission } from 'aws-cdk-lib/aws-lambda';
import { Construct } from 'constructs';

/**
 * Type representing python lambda function
 */
export type PythonLambdaFunction = {
  id?: string;
  name: string;
  resource?: string;
  description: string;
  path: string;
  method: string;
  environment?: {
    [key: string]: string;
  };
  timeout?: Duration;
  disambiguator?: string;
};

/**
 * Registers API endpoints for Python lambda functions
 * @param scope a CDK construct
 * @param api the REST APIGateway this Lambda endpoint will be added to
 * @param authorizer the authorizer Lambda function for authenticating calls to this endpoint
 * @param lambdaSourcePath the file path to the source code for this Lambda function
 * @param layers the Lambda LayerVersion to use across Lambda functions
 * @param funcDef the properties of this Lambda function such as the name, path, and method
 * @param pythonRuntime the configured Python runtime
 * @param role the IAM execution role of this Lambda function
 * @param vpc the VPC this Lambda function will exist inside
 * @param securityGroups security groups for Lambdas
 * @param fromArn an existing lambda function that should be used instead of creating a new one
 * @returns
 */
export function registerAPIEndpoint(
  scope: Construct,
  api: IRestApi,
  authorizer: IAuthorizer,
  lambdaSourcePath: string,
  layers: ILayerVersion[],
  funcDef: PythonLambdaFunction,
  pythonRuntime: Runtime,
  role?: IRole,
  vpc?: IVpc,
  securityGroups?: ISecurityGroup[],
  fromArn?: string
): IFunction {
  const functionId = `${funcDef.id || [cdk.Stack.of(scope).stackName, funcDef.resource, funcDef.name, funcDef.disambiguator].filter(Boolean).join('-')}`;
  console.log('functionId', functionId);

  const functionResource = getOrCreateResource(scope, api.root, funcDef.path.split('/'));
  let handler;

  if (fromArn) {
    handler = Function.fromFunctionArn(scope, functionId, fromArn);

    // create a CFN L1 primitive because `handler.addPermission` doesn't behave as expected
    // https://stackoverflow.com/questions/71075361/aws-cdk-lambda-resource-based-policy-for-a-function-with-an-alias
    const cfnPermission = new CfnPermission(scope, `LambdaInvokeAccessRemote-${functionId}`, {
      action: 'lambda:InvokeFunction',
      sourceArn: api.arnForExecuteApi(funcDef.method, `/${funcDef.path}`),
      functionName: handler.functionName,
      principal: 'apigateway.amazonaws.com',
    });
  } else {
    handler = new Function(scope, functionId, {
      functionName: functionId,
      runtime: pythonRuntime,
      handler: `${funcDef.resource}.lambda_functions.${funcDef.name}`,
      code: Code.fromAsset(lambdaSourcePath),
      description: funcDef.description,
      environment: {
        ...funcDef.environment,
      },
      timeout: funcDef.timeout || Duration.seconds(180),
      memorySize: 512,
      layers,
      role,
      vpc,
      securityGroups,
    });
  }

  functionResource.addMethod(funcDef.method, new LambdaIntegration(handler), {
    authorizer,
    authorizationType: AuthorizationType.CUSTOM,
  });

  return handler;
}

function getOrCreateResource(scope: Construct, parentResource: IResource, path: string[]): IResource {
  let resource = parentResource.getResource(path[0]);
  if (!resource) {
    resource = parentResource.addResource(path[0]);
    resource.addCorsPreflight({
      allowOrigins: Cors.ALL_ORIGINS,
      allowHeaders: Cors.DEFAULT_HEADERS,
    });
  }
  if (path.length > 1) {
    return getOrCreateResource(scope, resource, path.slice(1));
  }
  return resource;
}

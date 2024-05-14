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
import { Code, Function, Runtime, ILayerVersion, IFunction } from 'aws-cdk-lib/aws-lambda';
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
): IFunction {
  const functionId = `${funcDef.id || [cdk.Stack.of(scope).stackName, funcDef.resource, funcDef.name].join('-')}`;
  const handler = new Function(scope, functionId, {
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
  const functionResource = getOrCreateResource(scope, api.root, funcDef.path.split('/'));
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

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

import { Duration } from 'aws-cdk-lib';
import { IAuthorizer, RestApi } from 'aws-cdk-lib/aws-apigateway';
import { ISecurityGroup, IVpc } from 'aws-cdk-lib/aws-ec2';
import { IRole } from 'aws-cdk-lib/aws-iam';
import { ILayerVersion } from 'aws-cdk-lib/aws-lambda';
import { Construct } from 'constructs';

import { PythonLambdaFunction, registerAPIEndpoint } from '../../api-base/utils';
import { BaseProps } from '../../schema';

/**
 * Properties for RepositoryAPI Construct.
 *
 * @property {IAuthorizer} authorizer - APIGW authorizer
 * @property {Record<string,string>} baseEnvironment - Default environment properties applied to all
 *                                                      lambdas
 * @property {LayerVersion[]} commonLayers - Lambda layers for all Lambdas.
 * @property {IRole} lambdaExecutionRole - Execution role for lambdas
 * @property {IRestApi} restAPI - REST APIGW for UI and Lambdas
 * @property {ISecurityGroup[]} securityGroups - Security groups for Lambdas
 * @property {IVpc} vpc - Stack VPC
 */
interface RepositoryApiProps extends BaseProps {
  authorizer: IAuthorizer;
  baseEnvironment: Record<string, string>;
  commonLayers: ILayerVersion[];
  lambdaExecutionRole: IRole;
  restApiId: string;
  rootResourceId: string;
  securityGroups?: ISecurityGroup[];
  vpc?: IVpc;
}

/**
 * API for RAG repository operations
 */
export class RepositoryApi extends Construct {
  constructor(scope: Construct, id: string, props: RepositoryApiProps) {
    super(scope, id);

    const {
      authorizer,
      baseEnvironment,
      config,
      commonLayers,
      lambdaExecutionRole,
      restApiId,
      rootResourceId,
      securityGroups,
      vpc,
    } = props;

    const restApi = RestApi.fromRestApiAttributes(this, 'RestApi', {
      restApiId: restApiId,
      rootResourceId: rootResourceId,
    });

    // Create API Lambda functions
    const apis: PythonLambdaFunction[] = [
      {
        name: 'list_all',
        resource: 'repository',
        description: 'List all registered repositories',
        path: 'repository',
        method: 'GET',
        environment: {
          ...baseEnvironment,
        },
      },
      {
        name: 'purge_document',
        resource: 'repository',
        description: 'Purges all records associated with a document from the repository',
        path: 'repository/{repositoryId}/{documentId}',
        method: 'DELETE',
        environment: {
          ...baseEnvironment,
        },
      },
      {
        name: 'ingest_documents',
        resource: 'repository',
        description: 'Ingest a set of documents based on specified S3 path',
        path: 'repository/{repositoryId}/bulk',
        method: 'POST',
        timeout: Duration.minutes(15),
        environment: {
          ...baseEnvironment,
        },
      },
      {
        name: 'presigned_url',
        resource: 'repository',
        description: 'Generates a presigned url for uploading files to RAG',
        path: 'repository/presigned-url',
        method: 'POST',
        environment: {
          ...baseEnvironment,
        },
      },
      {
        name: 'similarity_search',
        resource: 'repository',
        description: 'Run a similarity search against the specified repository using the specified query',
        path: 'repository/{repositoryId}/similaritySearch',
        method: 'GET',
        environment: {
          ...baseEnvironment,
        },
      },
    ];
    apis.forEach((f) => {
      registerAPIEndpoint(
        this,
        restApi,
        authorizer,
        config.lambdaSourcePath,
        commonLayers,
        f,
        config.lambdaConfig.pythonRuntime,
        lambdaExecutionRole,
        vpc,
        securityGroups,
      );
    });
  }
}

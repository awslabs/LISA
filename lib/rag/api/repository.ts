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
import { ISecurityGroup } from 'aws-cdk-lib/aws-ec2';
import { IRole } from 'aws-cdk-lib/aws-iam';
import { IFunction, ILayerVersion } from 'aws-cdk-lib/aws-lambda';
import { Construct } from 'constructs';

import { getDefaultRuntime, PythonLambdaFunction, registerAPIEndpoint } from '../../api-base/utils';
import { BaseProps } from '../../schema';
import { Vpc } from '../../networking/vpc';
import { LAMBDA_PATH } from '../../util';

/**
 * Properties for RepositoryAPI Construct.
 *
 * @property {IAuthorizer} authorizer - APIGW authorizer
 * @property {Record<string,string>} baseEnvironment - Default environment properties applied to all
 *                                                      lambdas
 * @property {ILayerVersion[]} commonLayers - Lambda layers for all Lambdas.
 * @property {IRole} lambdaExecutionRole - Execution role for lambdas
 * @property {string} restApiId - REST APIGW for UI and Lambdas
 * @property {ISecurityGroup[]} securityGroups - Security groups for Lambdas
 * @property {Vpc} vpc - Stack VPC
 */
type RepositoryApiProps = {
    authorizer?: IAuthorizer;
    baseEnvironment: Record<string, string>;
    commonLayers: ILayerVersion[];
    lambdaExecutionRole: IRole;
    restApiId: string;
    rootResourceId: string;
    securityGroups: ISecurityGroup[];
    vpc: Vpc;
} & BaseProps;

/**
 * API for RAG repository operations
 */
export class RepositoryApi extends Construct {
    public createCollectionFunction: IFunction;

    constructor (scope: Construct, id: string, props: RepositoryApiProps) {
        super(scope, id);

        const {
            authorizer,
            baseEnvironment,
            commonLayers,
            lambdaExecutionRole,
            restApiId,
            rootResourceId,
            securityGroups,
            vpc,
            config
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
                description: 'List all repositories',
                path: 'repository',
                method: 'GET',
                environment: {
                    ...baseEnvironment,
                },
            },
            {
                name: 'list_status',
                resource: 'repository',
                description: 'List status for all repositories',
                path: 'repository/status',
                method: 'GET',
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
                name: 'create',
                resource: 'repository',
                description: 'Create a new repository',
                path: 'repository',
                method: 'POST',
                environment: {
                    ...baseEnvironment,
                },
            },
            {
                name: 'get_repository_by_id',
                resource: 'repository',
                description: 'Get a repository by ID',
                path: 'repository/{repositoryId}',
                method: 'GET',
                environment: {
                    ...baseEnvironment,
                },
            },
            {
                name: 'update_repository',
                resource: 'repository',
                description: 'Update a repository',
                path: 'repository/{repositoryId}',
                method: 'PUT',
                environment: {
                    ...baseEnvironment,
                },
            },
            {
                name: 'delete',
                resource: 'repository',
                description: 'Delete a repository',
                path: 'repository/{repositoryId}',
                method: 'DELETE',
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
                name: 'list_docs',
                resource: 'repository',
                description: 'List all docs for a repository',
                path: 'repository/{repositoryId}/document',
                method: 'GET',
                environment: {
                    ...baseEnvironment,
                },
            },
            {
                name: 'get_document',
                resource: 'repository',
                description: 'Get a document by ID',
                path: 'repository/{repositoryId}/{documentId}',
                method: 'GET',
                environment: {
                    ...baseEnvironment,
                },
            },
            {
                name: 'download_document',
                resource: 'repository',
                description: 'Creates presigned url to download document within repository',
                path: 'repository/{repositoryId}/{documentId}/download',
                method: 'GET',
                environment: {
                    ...baseEnvironment,
                },
            },
            {
                name: 'delete_documents',
                resource: 'repository',
                description: 'Deletes all records associated with documents from the repository',
                path: 'repository/{repositoryId}/document',
                method: 'DELETE',
                environment: {
                    ...baseEnvironment,
                },
            },
            {
                name: 'list_jobs',
                resource: 'repository',
                description: 'List all ingestion jobs for a repository',
                path: 'repository/{repositoryId}/jobs',
                method: 'GET',
                environment: {
                    ...baseEnvironment,
                },
            },
            {
                name: 'list_collections',
                resource: 'repository',
                description: 'List all collections within a repository',
                path: 'repository/{repositoryId}/collection',
                method: 'GET',
                environment: {
                    ...baseEnvironment,
                },
            },
            {
                name: 'list_user_collections',
                resource: 'repository',
                description: 'List all collections user has access to across all repositories',
                path: 'repository/collections',
                method: 'GET',
                environment: {
                    ...baseEnvironment,
                },
            },
            {
                name: 'create_collection',
                resource: 'repository',
                description: 'Create a new collection within a repository',
                path: 'repository/{repositoryId}/collection',
                method: 'POST',
                environment: {
                    ...baseEnvironment,
                },
            },
            {
                name: 'get_collection',
                resource: 'repository',
                description: 'Get a collection by ID within a repository',
                path: 'repository/{repositoryId}/collection/{collectionId}',
                method: 'GET',
                environment: {
                    ...baseEnvironment,
                },
            },
            {
                name: 'delete_collection',
                resource: 'repository',
                description: 'Delete a collection within a repository',
                path: 'repository/{repositoryId}/collection/{collectionId}',
                method: 'DELETE',
                environment: {
                    ...baseEnvironment,
                },
            }
        ];

        const lambdaPath = config.lambdaPath || LAMBDA_PATH;
        apis.forEach((f) => {
            const lambdaFunction = registerAPIEndpoint(
                this,
                restApi,
                lambdaPath,
                commonLayers,
                f,
                getDefaultRuntime(),
                vpc,
                securityGroups,
                authorizer,
                lambdaExecutionRole,
            );

            // Capture create_collection Lambda for backward compatibility
            if (f.name === 'create_collection') {
                this.createCollectionFunction = lambdaFunction;
            }
        });
    }
}

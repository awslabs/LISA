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

import * as path from 'node:path';

import { CfnOutput, RemovalPolicy, Stack, StackProps } from 'aws-cdk-lib';
import { AwsIntegration, RestApi } from 'aws-cdk-lib/aws-apigateway';
import { Role, ServicePrincipal } from 'aws-cdk-lib/aws-iam';
import { BlockPublicAccess, Bucket, BucketEncryption } from 'aws-cdk-lib/aws-s3';
import { BucketDeployment, Source } from 'aws-cdk-lib/aws-s3-deployment';
import { Construct } from 'constructs';


/**
 * Properties for UserInterface Construct.
 *
 * @property {Architecture} architecture - Lambda runtime architecture.
 */
type DocsProps = {} & StackProps;


/**
 * User Interface Construct.
 */
export class DocsStack extends Stack {

    /**
   * @param {Construct} scope - The parent or owner of the construct.
   * @param {string} id - The unique identifier for the construct within its scope.
   * @param {DocsProps} props - The properties of the construct.
   */
    constructor (scope: Construct, id: string, props: DocsProps) {
        super(scope, id, props);

        const docsPath = path.join(path.dirname(__dirname), 'user-interface', 'react', 'dist', 'docs');

        // Create Docs S3 bucket
        const docsBucket = new Bucket(this, 'DocsBucket', {
            removalPolicy: RemovalPolicy.DESTROY,
            autoDeleteObjects: true,
            encryption: BucketEncryption.S3_MANAGED,
            enforceSSL: true,
            blockPublicAccess: BlockPublicAccess.BLOCK_ALL,
        });

        // Deploy local folder to S3
        new BucketDeployment(this, 'DeployDocsWebsite', {
            sources: [Source.asset(docsPath)],
            destinationBucket: docsBucket,
        });

        // Create API Gateway
        const api = new RestApi(this, 'DocsApi', {
            description: 'API Gateway for S3 hosted website',
        });

        // REST API GW S3 role
        const apiGatewayRole = new Role(this, `${Stack.of(this).stackName}-s3-reader-role`, {
            assumedBy: new ServicePrincipal('apigateway.amazonaws.com'),
            description: 'Allows API gateway to proxy static website assets',
        });
        docsBucket.grantRead(apiGatewayRole);

        // Create API Gateway integration with S3
        const s3Integration = new AwsIntegration({
            service: 's3',
            integrationHttpMethod: 'GET',
            path: `${docsBucket.bucketName}/{key}`,
            options: {
                credentialsRole: apiGatewayRole,
                requestParameters: {
                    'integration.request.path.key': 'method.request.path.key',
                },
                integrationResponses: [
                    {
                        statusCode: '200',
                        responseParameters: {
                            'method.response.header.Content-Type': 'integration.response.header.Content-Type',
                        },
                    },
                    {
                        selectionPattern: '403',
                        statusCode: '403',
                        responseTemplates: {
                            'application/json': '{"message": "Access Denied"}',
                        },
                    },
                    {
                        selectionPattern: '404',
                        statusCode: '404',
                        responseTemplates: {
                            'application/json': '{"message": "Not Found"}',
                        },
                    },
                ],
            },
        });

        // Add GET method to API Gateway
        api.root.addMethod('GET', s3Integration, {
            requestParameters: {
                'method.request.path.key': true,
            },
            methodResponses: [
                {
                    statusCode: '200',
                    responseParameters: {
                        'method.response.header.Content-Type': true,
                    },
                },
                { statusCode: '403' },
                { statusCode: '404' },
            ],
        });

        // Add a catch-all proxy resource
        const proxyResource = api.root.addResource('{key+}');
        proxyResource.addMethod('GET', s3Integration, {
            requestParameters: {
                'method.request.path.key': true,
            },
            methodResponses: [
                {
                    statusCode: '200',
                    responseParameters: {
                        'method.response.header.Content-Type': true,
                    },
                },
                { statusCode: '403' },
                { statusCode: '404' },
            ],
        });

        // Output the API Gateway URL
        new CfnOutput(this, 'DocsApiGatewayUrl', {
            value: api.url,
            description: 'API Gateway URL',
        });
    }
}
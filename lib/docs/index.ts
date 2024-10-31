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
import * as fs from 'node:fs';

import { CfnOutput, RemovalPolicy, Stack, StackProps } from 'aws-cdk-lib';
import { AwsIntegration, RestApi } from 'aws-cdk-lib/aws-apigateway';
import { Role, ServicePrincipal } from 'aws-cdk-lib/aws-iam';
import { BlockPublicAccess, Bucket, BucketEncryption } from 'aws-cdk-lib/aws-s3';
import { BucketDeployment, Source } from 'aws-cdk-lib/aws-s3-deployment';
import { Construct } from 'constructs';
import { BaseProps } from '../schema';

/**
 * Properties for DocsStack Construct.
 */
type DocsProps = {} & BaseProps & StackProps;

/**
 * User Interface Construct.
 */
export class LisaDocsStack extends Stack {

    /**
     * @param {Construct} scope - The parent or owner of the construct.
     * @param {string} id - The unique identifier for the construct within its scope.
     * @param {DocsProps} props - The properties of the construct.
     */
    constructor (scope: Construct, id: string, props: DocsProps) {
        super(scope, id, props);
        const { config } = props;

        // Create Docs S3 bucket
        const docsBucket = new Bucket(this, 'DocsBucket', {
            removalPolicy: RemovalPolicy.DESTROY,
            autoDeleteObjects: true,
            encryption: BucketEncryption.S3_MANAGED,
            enforceSSL: true,
            blockPublicAccess: BlockPublicAccess.BLOCK_ALL,
            websiteIndexDocument: 'index.html',
            websiteErrorDocument: '404.html',
        });

        // Ensure dist folder is created (for tests)
        const docsPath = path.join(__dirname, 'dist');
        if (!fs.existsSync(docsPath)) {
            fs.mkdirSync(docsPath);
        }
        // Deploy local folder to S3
        new BucketDeployment(this, 'DeployDocsWebsite', {
            sources: [Source.asset(docsPath)],
            destinationBucket: docsBucket,
        });

        // REST API GW S3 role
        const apiGatewayRole = new Role(this, `${Stack.of(this).stackName}-s3-reader-role`, {
            assumedBy: new ServicePrincipal('apigateway.amazonaws.com'),
            description: 'Allows API gateway to proxy static website assets',
        });
        docsBucket.grantRead(apiGatewayRole);

        // Create API Gateway
        const api = new RestApi(this, 'DocsApi', {
            description: 'API Gateway for S3 hosted website',
            deployOptions: {
                stageName: 'lisa',
            },
            binaryMediaTypes: ['*/*'],
        });

        const defaultIntegration = new AwsIntegration({
            service: 's3',
            region: config.region,
            integrationHttpMethod: 'GET',
            path: `${docsBucket.bucketName}/index.html`,
            options: {
                credentialsRole: apiGatewayRole,
                integrationResponses: [{
                    statusCode: '200',
                    responseParameters: {
                        'method.response.header.Content-Type': '\'text/html\'',
                    },
                }],
            },
        });

        // Create API Gateway integration with S3
        const s3Integration = new AwsIntegration({
            service: 's3',
            region: config.region,
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
                            'method.response.header.Content-Disposition': 'integration.response.header.Content-Disposition',
                            'method.response.header.Content-Length': 'integration.response.header.Content-Length',
                        },
                    },
                    {
                        selectionPattern: '403',
                        statusCode: '404',
                        responseParameters: {
                            'method.response.header.Content-Type': '\'text/html\'',
                        },
                        responseTemplates: {
                            'text/html': `#set($context.responseOverride.header.Content-Type = 'text/html')
                             #set($context.responseOverride.status = 404)
                             #set($context.responseOverride.header.Location = "$context.domainName/404.html")`,
                        },
                    },
                ],
            },
        });

        // Add GET method to API Gateway
        api.root.addMethod('GET', defaultIntegration, {
            methodResponses: [
                {
                    statusCode: '200',
                    responseParameters: {
                        'method.response.header.Content-Type': true,
                    },
                },
            ],
        });

        api.root.addResource('{key+}').addMethod('GET', s3Integration, {
            requestParameters: {
                'method.request.path.key': true,
            },
            methodResponses: [
                {
                    statusCode: '200',
                    responseParameters: {
                        'method.response.header.Content-Type': true,
                        'method.response.header.Content-Disposition': true,
                        'method.response.header.Content-Length': true,
                    },
                },
                {
                    statusCode: '404',
                    responseParameters: {
                        'method.response.header.Content-Type': true,
                    },
                },
            ],
        });

        // Output the API Gateway URL
        new CfnOutput(this, 'DocsApiGatewayUrl', {
            value: api.url,
            description: 'API Gateway URL',
        });
    }
}

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

import { ExecSyncOptionsWithBufferEncoding, execSync } from 'node:child_process';
import * as fs from 'node:fs';
import * as path from 'node:path';

import { RemovalPolicy, Stack, StackProps } from 'aws-cdk-lib';
import { AwsIntegration, RestApi } from 'aws-cdk-lib/aws-apigateway';
import { ManagedPolicy, Role, ServicePrincipal } from 'aws-cdk-lib/aws-iam';
import { Architecture, Runtime } from 'aws-cdk-lib/aws-lambda';
import { BlockPublicAccess, Bucket, BucketEncryption } from 'aws-cdk-lib/aws-s3';
import { BucketDeployment, Source } from 'aws-cdk-lib/aws-s3-deployment';
import { Construct } from 'constructs';

import { BaseProps } from '../schema';

/**
 * Properties for UserInterface Construct.
 *
 * @property {Architecture} architecture - Lambda runtime architecture.
 */
type CustomUserInterfaceProps = {
    architecture: Architecture;
    restApiId: string;
    rootResourceId: string;
} & BaseProps;

type UserInterfaceProps = CustomUserInterfaceProps & StackProps;

/**
 * User Interface Construct.
 */
export class UserInterfaceStack extends Stack {
    /**
   * @param {Construct} scope - The parent or owner of the construct.
   * @param {string} id - The unique identifier for the construct within its scope.
   * @param {UserInterfaceProps} props - The properties of the construct.
   */
    constructor (scope: Construct, id: string, props: UserInterfaceProps) {
        super(scope, id, props);

        const { architecture, config, restApiId, rootResourceId } = props;
        const appPath = path.join(__dirname, '.', 'react');
        const distPath = path.join(appPath, 'dist');

        // Create website S3 bucket
        const websiteBucket = new Bucket(this, 'Bucket', {
            removalPolicy: RemovalPolicy.DESTROY,
            autoDeleteObjects: true,
            websiteIndexDocument: 'index.html',
            websiteErrorDocument: 'index.html',
            publicReadAccess: false,
            blockPublicAccess: BlockPublicAccess.BLOCK_ALL,
            encryption: BucketEncryption.S3_MANAGED,
            enforceSSL: true,
        });

        // REST APIGW config
        // S3 role
        const s3ReaderRole = new Role(this, `${Stack.of(this).stackName}-s3-reader-role`, {
            assumedBy: new ServicePrincipal('apigateway.amazonaws.com'),
            roleName: `${Stack.of(this).stackName}-s3-reader-role`,
            managedPolicies: [ManagedPolicy.fromAwsManagedPolicyName('AmazonS3ReadOnlyAccess')],
            description: 'Allows API gateway to proxy static website assets',
        });

        // Configure static site resources
        const proxyMethodResponse = [
            {
                statusCode: '200',
                responseParameters: {
                    'method.response.header.Content-Length': true,
                    'method.response.header.Content-Type': true,
                    'method.response.header.Content-Disposition': true,
                },
            },
        ];
        const proxyRequestParameters = {
            'method.request.header.Accept': true,
            'method.request.header.Content-Type': true,
            'method.request.header.Content-Disposition': true,
        };
        const proxyIntegrationResponse = [
            {
                statusCode: '200',
                responseParameters: {
                    'method.response.header.Content-Length': 'integration.response.header.Content-Length',
                    'method.response.header.Content-Type': 'integration.response.header.Content-Type',
                    'method.response.header.Content-Disposition': 'integration.response.header.Content-Disposition',
                },
            },
        ];
        const proxyIntegrationRequestParameters = {
            'integration.request.header.Accept': 'method.request.header.Accept',
            'integration.request.header.Content-Disposition': 'method.request.header.Content-Disposition',
            'integration.request.header.Content-Type': 'method.request.header.Content-Type',
        };

        const restApi = RestApi.fromRestApiAttributes(this, 'RestApi', {
            restApiId: restApiId,
            rootResourceId: rootResourceId,
        });
        // API methods
        restApi.root.addMethod(
            'GET',
            new AwsIntegration({
                region: config.region,
                service: 's3',
                path: `${websiteBucket.bucketName}/index.html`,
                integrationHttpMethod: 'GET',
                options: {
                    credentialsRole: s3ReaderRole,
                    integrationResponses: proxyIntegrationResponse,
                    requestParameters: proxyIntegrationRequestParameters,
                },
            }),
            {
                methodResponses: proxyMethodResponse,
                requestParameters: proxyRequestParameters,
            },
        );

        restApi.root.addResource('{proxy+}').addMethod(
            'GET',
            new AwsIntegration({
                region: config.region,
                service: 's3',
                path: `${websiteBucket.bucketName}/{proxy}`,
                integrationHttpMethod: 'ANY',
                options: {
                    credentialsRole: s3ReaderRole,
                    integrationResponses: proxyIntegrationResponse,
                    requestParameters: {
                        ...proxyIntegrationRequestParameters,
                        'integration.request.path.proxy': 'method.request.path.proxy',
                    },
                },
            }),
            {
                requestParameters: {
                    ...proxyRequestParameters,
                    'method.request.path.proxy': true,
                },
                methodResponses: proxyMethodResponse,
            },
        );

        const ecsModels = config.ecsModels.map((modelConfig) => {
            return {
                model: modelConfig.modelId,
                streaming: modelConfig.streaming,
                modelType: modelConfig.modelType,
            };
        });
        const litellmModels = config.litellmConfig.model_list ? config.litellmConfig.model_list : [];
        const modelsList = ecsModels.concat(
            litellmModels.map((model) => {
                return {
                    model: model.model_name,
                    streaming: model.lisa_params.streaming,
                    modelType: model.lisa_params.model_type,
                };
            }),
        );

        // Website bucket deployment
        // Copy auth and LISA-Serve info to UI deployment bucket
        const appEnvConfig = {
            AUTHORITY: config.authConfig!.authority,
            CLIENT_ID: config.authConfig!.clientId,
            ADMIN_GROUP: config.authConfig!.adminGroup,
            JWT_GROUPS_PROP: config.authConfig!.jwtGroupsProperty,
            CUSTOM_SCOPES: config.authConfig!.additionalScopes,
            RESTAPI_ID: config.apiGatewayConfig?.domainName ? '/llm' : `/${config.deploymentStage}/llm`,
            RESTAPI_VERSION: config.restApiConfig.apiVersion,
            RAG_ENABLED: config.deployRag,
            SYSTEM_BANNER: {
                text: config.systemBanner?.text,
                backgroundColor: config.systemBanner?.backgroundColor,
                fontColor: config.systemBanner?.fontColor,
            },
            API_BASE_URL: config.apiGatewayConfig?.domainName ? '/' : `/${config.deploymentStage}/`,
            MODELS: modelsList,
        };

        const appEnvSource = Source.data('env.js', `window.env = ${JSON.stringify(appEnvConfig)}`);
        const uriSuffix = config.apiGatewayConfig?.domainName ? '' : `${config.deploymentStage}/`;
        let webappAssets;
        if (!config.webAppAssetsPath) {
            webappAssets = Source.asset(appPath, {
                bundling: {
                    image: Runtime.NODEJS_18_X.bundlingImage,
                    platform: architecture.dockerPlatform,
                    command: [
                        'sh',
                        '-c',
                        [
                            'set -x',
                            'npm --cache /tmp/.npm install',
                            `npm --cache /tmp/.npm run build -- --base="/${uriSuffix}"`,
                            'cp -aur /asset-input/dist/* /asset-output/',
                        ].join(' && '),
                    ],
                    local: {
                        tryBundle (outputDir: string) {
                            try {
                                const options: ExecSyncOptionsWithBufferEncoding = {
                                    stdio: 'inherit',
                                    env: {
                                        ...process.env,
                                    },
                                };

                                execSync(`npm --silent --prefix "${appPath}" ci`, options);
                                execSync(`npm --silent --prefix "${appPath}" run build -- --base="/${uriSuffix}"`, options);
                                copyDirRecursive(distPath, outputDir);
                            } catch (e) {
                                return false;
                            }
                            return true;
                        },
                    },
                },
            });
        } else {
            webappAssets = Source.asset(config.webAppAssetsPath);
        }
        new BucketDeployment(this, 'AwsExportsDepolyment', {
            sources: [webappAssets, appEnvSource],
            retainOnDelete: false,
            destinationBucket: websiteBucket,
        });
    }
}

/**
 * Copy files recursively from source directory to destination directory.
 * @param {string} sourceDir - Source directory to copy from.
 * @param {string} targetDir - Target directory to copy to.
 */
function copyDirRecursive (sourceDir: string, targetDir: string): void {
    if (!fs.existsSync(targetDir)) {
        fs.mkdirSync(targetDir);
    }

    const files = fs.readdirSync(sourceDir);

    for (const file of files) {
        const sourceFilePath = path.join(sourceDir, file);
        const targetFilePath = path.join(targetDir, file);
        const stats = fs.statSync(sourceFilePath);

        if (stats.isDirectory()) {
            copyDirRecursive(sourceFilePath, targetFilePath);
        } else {
            fs.copyFileSync(sourceFilePath, targetFilePath);
        }
    }
}

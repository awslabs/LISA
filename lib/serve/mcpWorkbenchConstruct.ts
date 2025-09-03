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

import { IAuthorizer, RestApi } from 'aws-cdk-lib/aws-apigateway';
import { ISecurityGroup } from 'aws-cdk-lib/aws-ec2';
import { Construct } from 'constructs';
import { Vpc } from '../networking/vpc';
import { BaseProps, Config } from '../schema';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { RemovalPolicy, StackProps } from 'aws-cdk-lib';
import { createCdkId } from '../core/utils';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import { getDefaultRuntime, PythonLambdaFunction, registerAPIEndpoint } from '../api-base/utils';
import * as iam from 'aws-cdk-lib/aws-iam';
import { LAMBDA_PATH } from '../util';
import * as lambda from 'aws-cdk-lib/aws-lambda';

export type McpWorkbenchConstructProps = {
    authorizer: IAuthorizer;
    restApiId: string;
    rootResourceId: string;
    securityGroups: ISecurityGroup[];
    vpc: Vpc;
} & BaseProps & StackProps;

export default class McpWorkbenchConstruct extends Construct {
    constructor (scope: Construct, id: string, props: McpWorkbenchConstructProps) {
        super(scope, id);

        const { authorizer, config, restApiId, rootResourceId, securityGroups, vpc } = props;

        const workbenchBucket = this.createWorkbenchBucket(scope, config);
        this.createWorkbenchApi(restApiId, rootResourceId, config, vpc, securityGroups, authorizer, workbenchBucket);
    }

    private createWorkbenchApi (restApiId: string, rootResourceId: string, config: Config, vpc: Vpc, securityGroups: ISecurityGroup[], authorizer: IAuthorizer, workbenchBucket: s3.Bucket) {
        const restApi = RestApi.fromRestApiAttributes(this, 'RestApi', {
            restApiId: restApiId,
            rootResourceId: rootResourceId,
        });

        // Get common layer based on arn from SSM due to issues with cross stack references
        const commonLambdaLayer = lambda.LayerVersion.fromLayerVersionArn(
            this,
            'mcp-common-lambda-layer',
            ssm.StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/layerVersion/common`),
        );

        const fastapiLambdaLayer = lambda.LayerVersion.fromLayerVersionArn(
            this,
            'mcp-fastapi-lambda-layer',
            ssm.StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/layerVersion/fastapi`),
        );

        const env = {
            ADMIN_GROUP: config.authConfig?.adminGroup || '',
            WORKBENCH_BUCKET: workbenchBucket.bucketName
        };

        // Create API Lambda functions
        const apis: PythonLambdaFunction[] = [{
            name: 'list',
            resource: 'mcp_workbench',
            description: 'Lists available MCP Workbench tools',
            method: 'GET',
            environment: env,
            path: 'mcp-workbench'
        }, {
            name: 'create',
            resource: 'mcp_workbench',
            description: 'Create MCP Workbench tools',
            method: 'POST',
            environment: env,
            path: 'mcp-workbench'
        }, {
            name: 'read',
            resource: 'mcp_workbench',
            description: 'Get MCP Workbench tool',
            method: 'GET',
            environment: env,
            path: 'mcp-workbench/{toolId}'
        }, {
            name: 'update',
            resource: 'mcp_workbench',
            description: 'Update MCP Workbench tool',
            method: 'PUT',
            environment: env,
            path: 'mcp-workbench/{toolId}'
        }, {
            name: 'delete',
            resource: 'mcp_workbench',
            description: 'Delete MCP Workbench tool',
            method: 'DELETE',
            environment: env,
            path: 'mcp-workbench/{toolId}'
        }];

        // Create IAM role for Lambda
        const lambdaRole = new iam.Role(this, 'LambdaExecutionRole', {
            assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
            description: 'IAM role for Lambda function execution',
            inlinePolicies: {
                'EC2NetworkInterfaces': new iam.PolicyDocument({
                    statements: [
                        new iam.PolicyStatement({
                            effect: iam.Effect.ALLOW,
                            actions: ['ec2:CreateNetworkInterface', 'ec2:DescribeNetworkInterfaces', 'ec2:DeleteNetworkInterface'],
                            resources: ['*'],
                        }),
                    ],
                }),
            },
        });

        // Attach AWSLambdaBasicExecutionRole policy to the role
        lambdaRole.addManagedPolicy(
            iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole')
        );

        const lambdaPath = config.lambdaPath || LAMBDA_PATH;
        apis.forEach((f) => {
            const lambdaFunction = registerAPIEndpoint(
                this,
                restApi,
                lambdaPath,
                [commonLambdaLayer, fastapiLambdaLayer],
                f,
                getDefaultRuntime(),
                vpc,
                securityGroups,
                authorizer,
                lambdaRole,
            );
            if (f.method === 'POST' || f.method === 'PUT') {
                workbenchBucket.grantWrite(lambdaFunction);
            } else if (f.method === 'GET') {
                workbenchBucket.grantRead(lambdaFunction);
            } else if (f.method === 'DELETE') {
                workbenchBucket.grantDelete(lambdaFunction);
            }
        });
    }

    private createWorkbenchBucket (scope: Construct, config: any): s3.Bucket {
        const bucketAccessLogsBucket = s3.Bucket.fromBucketArn(scope, 'BucketAccessLogsBucket',
            ssm.StringParameter.valueForStringParameter(scope, `${config.deploymentPrefix}/bucket/bucket-access-logs`),
        );

        return new s3.Bucket(scope, createCdkId(['LISA', 'MCPWorkbench', config.deploymentName, config.deploymentStage]), {
            removalPolicy: config.removalPolicy,
            autoDeleteObjects: config.removalPolicy === RemovalPolicy.DESTROY,
            enforceSSL: true,
            serverAccessLogsBucket: bucketAccessLogsBucket,
            serverAccessLogsPrefix: 'logs/mcpworkbench-bucket/',
        });
    }
}

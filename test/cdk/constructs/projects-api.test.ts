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

import { App, Stack } from 'aws-cdk-lib';
import { Match, Template } from 'aws-cdk-lib/assertions';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import { ProjectsApi } from '../../../lib/chat/api/projects';
import ConfigParser from '../mocks/ConfigParser';
import { Vpc } from '../../../lib/networking/vpc';

const TEST_MOCK_DIR = './test/cdk/mocks/layers';

describe('ProjectsApi Construct', () => {
    let stack: Stack;
    let template: Template;

    beforeAll(() => {
        const config = ConfigParser.parseConfig();
        const app = new App();
        stack = new Stack(app, 'TestStack', {
            env: { account: '012345678901', region: config.region },
        });

        const vpc = new Vpc(stack, 'TestVpc', { config });

        const sessionTable = new dynamodb.Table(stack, 'SessionTable', {
            partitionKey: { name: 'sessionId', type: dynamodb.AttributeType.STRING },
            sortKey: { name: 'userId', type: dynamodb.AttributeType.STRING },
        });

        const configTable = new dynamodb.Table(stack, 'ConfigTable', {
            partitionKey: { name: 'configScope', type: dynamodb.AttributeType.STRING },
            sortKey: { name: 'versionId', type: dynamodb.AttributeType.NUMBER },
        });

        // Stub SSM parameters required by registerAPIEndpoint
        new ssm.StringParameter(stack, 'CommonLayer', {
            parameterName: `${config.deploymentPrefix}/layerVersion/common`,
            stringValue: `arn:aws:lambda:${config.region}:012345678901:layer:common:1`,
        });
        new ssm.StringParameter(stack, 'FastApiLayer', {
            parameterName: `${config.deploymentPrefix}/layerVersion/fastapi`,
            stringValue: `arn:aws:lambda:${config.region}:012345678901:layer:fastapi:1`,
        });

        // Minimal mock authorizer
        const restApi = new apigateway.RestApi(stack, 'TestApi');
        const authorizer = new apigateway.TokenAuthorizer(stack, 'TestAuth', {
            handler: new lambda.Function(stack, 'AuthFn', {
                runtime: lambda.Runtime.PYTHON_3_13,
                handler: 'index.handler',
                code: lambda.Code.fromAsset(TEST_MOCK_DIR),
            }),
        });

        new ProjectsApi(stack, 'ProjectsApi', {
            config,
            authorizer,
            restApiId: restApi.restApiId,
            rootResourceId: restApi.restApiRootResourceId,
            securityGroups: [vpc.securityGroups.lambdaSg],
            vpc,
            sessionTable,
            configTable,
        });

        // CDK requires at least one method on the RestApi to pass synthesis validation.
        // ProjectsApi adds methods via fromRestApiAttributes (imported ref), so we add a
        // placeholder method directly on the original restApi construct.
        restApi.root.addMethod('ANY');

        template = Template.fromStack(stack);
    });

    describe('DynamoDB Table', () => {
        it('creates a ProjectsTable with userId partition key and projectId sort key', () => {
            template.hasResourceProperties('AWS::DynamoDB::Table', {
                KeySchema: Match.arrayWith([
                    Match.objectLike({ AttributeName: 'userId', KeyType: 'HASH' }),
                    Match.objectLike({ AttributeName: 'projectId', KeyType: 'RANGE' }),
                ]),
            });
        });

        it('uses AWS_MANAGED encryption on the ProjectsTable', () => {
            template.hasResourceProperties('AWS::DynamoDB::Table', {
                KeySchema: Match.arrayWith([
                    Match.objectLike({ AttributeName: 'userId', KeyType: 'HASH' }),
                ]),
                SSESpecification: { SSEEnabled: true },
            });
        });
    });

    describe('Lambda Functions', () => {
        it('creates a list_projects Lambda function', () => {
            template.hasResourceProperties('AWS::Lambda::Function', {
                Environment: {
                    Variables: Match.objectLike({
                        PROJECTS_TABLE_NAME: Match.anyValue(),
                        SESSIONS_TABLE_NAME: Match.anyValue(),
                        CONFIG_TABLE_NAME: Match.anyValue(),
                        SESSIONS_BY_USER_ID_INDEX_NAME: 'byUserId',
                    }),
                },
            });
        });
    });

    describe('API Gateway', () => {
        it('registers a GET method on the /project resource', () => {
            template.hasResourceProperties('AWS::ApiGateway::Method', {
                HttpMethod: 'GET',
                AuthorizationType: Match.anyValue(),
            });
        });
    });

    describe('IAM Permissions', () => {
        it('grants the Lambda role read access to the SessionsTable byUserId GSI', () => {
            template.hasResourceProperties('AWS::IAM::Policy', {
                PolicyDocument: {
                    Statement: Match.arrayWith([
                        Match.objectLike({
                            Effect: 'Allow',
                            Action: Match.arrayWith(['dynamodb:Query']),
                        }),
                    ]),
                },
            });
        });

        it('grants the Lambda role read access to the ConfigTable', () => {
            template.hasResourceProperties('AWS::IAM::Policy', {
                PolicyDocument: {
                    Statement: Match.arrayWith([
                        Match.objectLike({
                            Effect: 'Allow',
                            Action: Match.arrayWith(['dynamodb:GetItem', 'dynamodb:Query']),
                        }),
                    ]),
                },
            });
        });
    });
});

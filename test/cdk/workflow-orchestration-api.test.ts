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
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import { WorkflowOrchestrationApi } from '../../lib/chat/api/workflow-orchestration-api';
import ConfigParser from './mocks/ConfigParser';
import { Vpc } from '../../lib/networking/vpc';

const TEST_MOCK_DIR = './test/cdk/mocks/layers';

describe('WorkflowOrchestrationApi Construct', () => {
    let template: Template;

    beforeAll(() => {
        const config = ConfigParser.parseConfig();
        const app = new App();
        const stack = new Stack(app, 'TestWorkflowApiStack', {
            env: { account: '012345678901', region: config.region },
        });
        const vpc = new Vpc(stack, 'TestVpc', { config });

        new ssm.StringParameter(stack, 'CommonLayer', {
            parameterName: `${config.deploymentPrefix}/layerVersion/common`,
            stringValue: `arn:aws:lambda:${config.region}:012345678901:layer:common:1`,
        });
        new ssm.StringParameter(stack, 'FastApiLayer', {
            parameterName: `${config.deploymentPrefix}/layerVersion/fastapi`,
            stringValue: `arn:aws:lambda:${config.region}:012345678901:layer:fastapi:1`,
        });

        const restApi = new apigateway.RestApi(stack, 'TestApi');
        const authorizer = new apigateway.TokenAuthorizer(stack, 'TestAuth', {
            handler: new lambda.Function(stack, 'AuthFn', {
                runtime: lambda.Runtime.PYTHON_3_13,
                handler: 'index.handler',
                code: lambda.Code.fromAsset(TEST_MOCK_DIR),
            }),
        });

        new WorkflowOrchestrationApi(stack, 'WorkflowOrchestrationApi', {
            config,
            authorizer,
            restApiId: restApi.restApiId,
            rootResourceId: restApi.restApiRootResourceId,
            securityGroups: [vpc.securityGroups.lambdaSg],
            vpc,
        });

        restApi.root.addMethod('ANY');
        template = Template.fromStack(stack);
    });

    it('creates the workflow orchestration DynamoDB table with workflowId key', () => {
        template.hasResourceProperties('AWS::DynamoDB::Table', {
            KeySchema: Match.arrayWith([Match.objectLike({ AttributeName: 'workflowId', KeyType: 'HASH' })]),
        });
    });

    it('creates lambdas with WORKFLOW_ORCHESTRATION_TABLE_NAME env var', () => {
        template.hasResourceProperties('AWS::Lambda::Function', {
            Environment: {
                Variables: Match.objectLike({
                    WORKFLOW_ORCHESTRATION_TABLE_NAME: Match.anyValue(),
                }),
            },
        });
    });

    it('creates lambdas with WORKFLOW_SCHEDULE_RULE_PREFIX env var', () => {
        template.hasResourceProperties('AWS::Lambda::Function', {
            Environment: {
                Variables: Match.objectLike({
                    WORKFLOW_SCHEDULE_RULE_PREFIX: 'test-lisa-workflow',
                }),
            },
        });
    });

    it('creates lambdas with WORKFLOW_SCHEDULER_TARGET_ARN env var', () => {
        template.hasResourceProperties('AWS::Lambda::Function', {
            Environment: {
                Variables: Match.objectLike({
                    WORKFLOW_SCHEDULER_TARGET_ARN: Match.anyValue(),
                }),
            },
        });
    });

    it('creates lambdas with WORKFLOW_EXECUTION_SFN_ARN env var', () => {
        template.hasResourceProperties('AWS::Lambda::Function', {
            Environment: {
                Variables: Match.objectLike({
                    WORKFLOW_EXECUTION_SFN_ARN: Match.anyValue(),
                }),
            },
        });
    });

    it('creates lambdas with WORKFLOW_SCHEDULER_TARGET_ROLE_ARN env var', () => {
        template.hasResourceProperties('AWS::Lambda::Function', {
            Environment: {
                Variables: Match.objectLike({
                    WORKFLOW_SCHEDULER_TARGET_ROLE_ARN: {
                        'Fn::GetAtt': [Match.stringLikeRegexp('WorkflowSchedulerTargetInvokeRole'), 'Arn'],
                    },
                }),
            },
        });
    });

    it('registers GET, POST, PUT, and DELETE API methods', () => {
        template.hasResourceProperties('AWS::ApiGateway::Method', { HttpMethod: 'GET' });
        template.hasResourceProperties('AWS::ApiGateway::Method', { HttpMethod: 'POST' });
        template.hasResourceProperties('AWS::ApiGateway::Method', { HttpMethod: 'PUT' });
        template.hasResourceProperties('AWS::ApiGateway::Method', { HttpMethod: 'DELETE' });
    });

    it('registers approval endpoint at workflows/approve', () => {
        template.hasResourceProperties('AWS::ApiGateway::Resource', { PathPart: 'approve' });
    });

    it('registers execute-step endpoint at workflows/execute-step', () => {
        template.hasResourceProperties('AWS::ApiGateway::Resource', { PathPart: 'execute-step' });
    });

    it('grants approval route lambda read and write access to workflows table', () => {
        const resources = template.findResources('AWS::Lambda::Function');
        const approveLambda = Object.entries(resources).find(([, resource]) => {
            const properties = resource.Properties as { Description?: string };
            return properties.Description === 'Approve workflow step';
        });

        expect(approveLambda).toBeDefined();
        const [approveLambdaLogicalId] = approveLambda!;
        const approveLambdaResource = template.toJSON().Resources[approveLambdaLogicalId] as {
            Properties: { Role: { 'Fn::GetAtt': [string, string] } };
        };
        const approvalRoleLogicalId = approveLambdaResource.Properties.Role['Fn::GetAtt'][0];

        const policies = template.findResources('AWS::IAM::Policy');
        const approvalPolicies = Object.values(policies).filter((policy) => {
            const roles = (policy.Properties as { Roles?: unknown[] }).Roles ?? [];
            return roles.some((role) => {
                const roleRef = role as { Ref?: string };
                return roleRef.Ref === approvalRoleLogicalId;
            });
        });

        expect(approvalPolicies.length).toBeGreaterThan(0);
        expect(approvalPolicies).toEqual(
            expect.arrayContaining([
                expect.objectContaining({
                    Properties: expect.objectContaining({
                        PolicyDocument: expect.objectContaining({
                            Statement: expect.arrayContaining([
                                expect.objectContaining({
                                    Effect: 'Allow',
                                    Action: expect.arrayContaining([
                                        'dynamodb:GetItem',
                                        'dynamodb:UpdateItem',
                                    ]),
                                }),
                            ]),
                        }),
                    }),
                }),
            ]),
        );
    });

    it('scopes EventBridge workflow rule mutations to deployment workflow rule ARNs', () => {
        const templateJson = template.toJSON() as {
            Resources: Record<string, { Properties?: { PolicyDocument?: { Statement?: Array<{ Action?: string[]; Resource?: string | string[] }> } } }>;
        };
        const policyResources = Object.values(templateJson.Resources)
            .filter((resource) => resource.Properties?.PolicyDocument?.Statement);
        const eventBridgeStatement = policyResources
            .flatMap((resource) => resource.Properties?.PolicyDocument?.Statement ?? [])
            .find((statement) => {
                const actions = statement.Action ?? [];
                return actions.includes('events:PutRule')
                    && actions.includes('events:DeleteRule')
                    && actions.includes('events:PutTargets')
                    && actions.includes('events:RemoveTargets');
            });

        expect(eventBridgeStatement).toBeDefined();
        expect(eventBridgeStatement?.Resource).not.toBe('*');
        expect(eventBridgeStatement?.Resource).toBe('arn:aws:events:us-iso-east-1:012345678901:rule/test-lisa-workflow-*');
    });

    it('grants scheduler target invocation role states:StartExecution on workflow target ARN', () => {
        template.hasResourceProperties('AWS::IAM::Policy', {
            PolicyDocument: {
                Statement: Match.arrayWith([
                    Match.objectLike({
                        Effect: 'Allow',
                        Action: 'states:StartExecution',
                        Resource: Match.anyValue(),
                    }),
                ]),
            },
        });
    });

    it('grants lambda role iam:PassRole for scheduler target role constrained to EventBridge', () => {
        template.hasResourceProperties('AWS::IAM::Policy', {
            PolicyDocument: {
                Statement: Match.arrayWith([
                    Match.objectLike({
                        Effect: 'Allow',
                        Action: 'iam:PassRole',
                        Resource: {
                            'Fn::GetAtt': [Match.stringLikeRegexp('WorkflowSchedulerTargetInvokeRole'), 'Arn'],
                        },
                        Condition: {
                            StringEquals: {
                                'iam:PassedToService': 'events.amazonaws.com',
                            },
                        },
                    }),
                ]),
            },
        });
    });

    it('creates workflow execution state machine and references its ARN for scheduler target env', () => {
        template.hasResourceProperties('AWS::StepFunctions::StateMachine', Match.anyValue());
        template.hasResourceProperties('AWS::Lambda::Function', {
            Environment: {
                Variables: Match.objectLike({
                    WORKFLOW_SCHEDULER_TARGET_ARN: {
                        Ref: Match.stringLikeRegexp('WorkflowExecutionWorkflowExecutionStateMachine'),
                    },
                }),
            },
        });
    });

    it('uses a lambda-based result summarization step for final workflow status', () => {
        const stateMachines = template.findResources('AWS::StepFunctions::StateMachine');
        const definitionStrings = Object.values(stateMachines).map((resource) =>
            JSON.stringify((resource.Properties as { DefinitionString?: unknown }).DefinitionString ?? {}),
        );
        const serializedDefinition = definitionStrings.join('\n');

        expect(serializedDefinition).toContain('SummarizeExecution');
        expect(serializedDefinition).toContain('summarize_results');
        expect(serializedDefinition).not.toContain('"status":"SUCCEEDED"');
    });
});

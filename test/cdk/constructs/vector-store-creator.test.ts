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

import { Stack } from 'aws-cdk-lib';
import { Match, Template } from 'aws-cdk-lib/assertions';
import MockApp from '../mocks/MockApp';
import ConfigParser from '../mocks/ConfigParser';

describe('VectorStoreCreator IAM Self-Targeting Prevention', () => {
    let stacks: Stack[];
    let template: Template;

    beforeAll(() => {
        const config = ConfigParser.parseConfig(['config-test.yaml', 'assets.yaml']);
        stacks = MockApp.create(config).stacks;

        // Find the RAG stack which contains VectorStoreCreator
        const ragStack = stacks.find((stack) => stack.stackName.includes('RAG'));
        expect(ragStack).toBeDefined();
        template = Template.fromStack(ragStack!);
    });

    describe('IAM Policy Self-Targeting Prevention', () => {
        it('should prevent the VectorStoreCreator role from modifying itself', () => {
            // Find the VectorStoreCreator role
            const roles = template.findResources('AWS::IAM::Role', {
                Properties: {
                    AssumeRolePolicyDocument: {
                        Statement: Match.arrayWith([
                            Match.objectLike({
                                Principal: {
                                    Service: 'lambda.amazonaws.com',
                                },
                            }),
                        ]),
                    },
                    ManagedPolicyArns: Match.arrayWith([
                        Match.objectLike({
                            'Fn::Join': Match.arrayWith([
                                Match.arrayWith([
                                    Match.stringLikeRegexp('.*AWSCloudFormationFullAccess'),
                                ]),
                            ]),
                        }),
                    ]),
                },
            });

            // Should find exactly one VectorStoreCreator role
            const roleKeys = Object.keys(roles);
            expect(roleKeys.length).toBeGreaterThan(0);

            // Get the role logical ID
            const roleLogicalId = roleKeys[0];

            // The policies are added via addToPolicy which creates separate AWS::IAM::Policy resources
            // Find all IAM policies
            const allPolicies = template.findResources('AWS::IAM::Policy');

            // Find the policy attached to our role
            let targetPolicy: any = null;
            for (const [, policy] of Object.entries(allPolicies)) {
                const policyProps = (policy as any).Properties;
                if (policyProps.Roles && policyProps.Roles.some((role: any) =>
                    role.Ref === roleLogicalId
                )) {
                    targetPolicy = policyProps;
                    break;
                }
            }

            expect(targetPolicy).toBeDefined();
            expect(targetPolicy.PolicyDocument).toBeDefined();
            expect(targetPolicy.PolicyDocument.Statement).toBeDefined();

            // Find the policy statement that contains permission mutation actions
            const permissionMutationStatement = targetPolicy.PolicyDocument.Statement.find((stmt: any) =>
                Array.isArray(stmt.Action) && stmt.Action.includes('iam:AttachRolePolicy')
            );

            expect(permissionMutationStatement).toBeDefined();
            expect(permissionMutationStatement.Condition).toBeDefined();
            expect(permissionMutationStatement.Condition.ArnNotEquals).toBeDefined();
            expect(permissionMutationStatement.Condition.ArnNotEquals['iam:ResourceArn']).toBeDefined();

            // Verify the condition references the role's ARN
            const arnNotEqualsValue = permissionMutationStatement.Condition.ArnNotEquals['iam:ResourceArn'];
            expect(arnNotEqualsValue).toEqual(
                expect.objectContaining({
                    'Fn::GetAtt': expect.arrayContaining([roleLogicalId, 'Arn']),
                })
            );
        });

        it('should allow role creation for vector stores with naming pattern restriction', () => {
            // Find the VectorStoreCreator role
            const roles = template.findResources('AWS::IAM::Role', {
                Properties: {
                    AssumeRolePolicyDocument: {
                        Statement: Match.arrayWith([
                            Match.objectLike({
                                Principal: {
                                    Service: 'lambda.amazonaws.com',
                                },
                            }),
                        ]),
                    },
                    ManagedPolicyArns: Match.arrayWith([
                        Match.objectLike({
                            'Fn::Join': Match.arrayWith([
                                Match.arrayWith([
                                    Match.stringLikeRegexp('.*AWSCloudFormationFullAccess'),
                                ]),
                            ]),
                        }),
                    ]),
                },
            });

            const roleKeys = Object.keys(roles);
            expect(roleKeys.length).toBeGreaterThan(0);
            const roleLogicalId = roleKeys[0];

            // Find the policy attached to our role
            const allPolicies = template.findResources('AWS::IAM::Policy');
            let targetPolicy: any = null;
            for (const [, policy] of Object.entries(allPolicies)) {
                const policyProps = (policy as any).Properties;
                if (policyProps.Roles && policyProps.Roles.some((role: any) =>
                    role.Ref === roleLogicalId
                )) {
                    targetPolicy = policyProps;
                    break;
                }
            }

            expect(targetPolicy).toBeDefined();

            // Find the policy statement that allows role creation
            const roleManagementStatement = targetPolicy.PolicyDocument.Statement.find((stmt: any) =>
                Array.isArray(stmt.Action) && stmt.Action.includes('iam:CreateRole')
            );

            expect(roleManagementStatement).toBeDefined();
            expect(roleManagementStatement.Resource).toBeDefined();
            expect(Array.isArray(roleManagementStatement.Resource)).toBe(true);

            // Verify resources follow vector store naming pattern
            const resources = roleManagementStatement.Resource;
            expect(resources.some((r: any) =>
                typeof r === 'string' ? r.includes('vector') : r['Fn::Join']?.[1]?.some((part: string) => part.includes('vector'))
            )).toBe(true);
        });

        it('should restrict AssumeRole to CDK bootstrap roles only', () => {
            // Find the VectorStoreCreator role
            const roles = template.findResources('AWS::IAM::Role', {
                Properties: {
                    AssumeRolePolicyDocument: {
                        Statement: Match.arrayWith([
                            Match.objectLike({
                                Principal: {
                                    Service: 'lambda.amazonaws.com',
                                },
                            }),
                        ]),
                    },
                    ManagedPolicyArns: Match.arrayWith([
                        Match.objectLike({
                            'Fn::Join': Match.arrayWith([
                                Match.arrayWith([
                                    Match.stringLikeRegexp('.*AWSCloudFormationFullAccess'),
                                ]),
                            ]),
                        }),
                    ]),
                },
            });

            const roleKeys = Object.keys(roles);
            expect(roleKeys.length).toBeGreaterThan(0);
            const roleLogicalId = roleKeys[0];

            // Find the policy attached to our role
            const allPolicies = template.findResources('AWS::IAM::Policy');
            let targetPolicy: any = null;
            for (const [, policy] of Object.entries(allPolicies)) {
                const policyProps = (policy as any).Properties;
                if (policyProps.Roles && policyProps.Roles.some((role: any) =>
                    role.Ref === roleLogicalId
                )) {
                    targetPolicy = policyProps;
                    break;
                }
            }

            expect(targetPolicy).toBeDefined();

            // Find the policy statement that allows AssumeRole
            const assumeRoleStatement = targetPolicy.PolicyDocument.Statement.find((stmt: any) =>
                stmt.Action === 'iam:AssumeRole'
            );

            expect(assumeRoleStatement).toBeDefined();
            expect(assumeRoleStatement.Resource).toBeDefined();
            expect(Array.isArray(assumeRoleStatement.Resource)).toBe(true);

            // Verify resources are CDK bootstrap roles
            const resources = assumeRoleStatement.Resource;
            expect(resources.every((r: any) => {
                const arnString = typeof r === 'string' ? r : r['Fn::Join']?.[1]?.join('');
                return arnString?.includes('cdk-') && arnString?.includes('deploy-role');
            })).toBe(true);
        });

        it('should allow PassRole only to specific AWS services', () => {
            // Find the VectorStoreCreator role
            const roles = template.findResources('AWS::IAM::Role', {
                Properties: {
                    AssumeRolePolicyDocument: {
                        Statement: Match.arrayWith([
                            Match.objectLike({
                                Principal: {
                                    Service: 'lambda.amazonaws.com',
                                },
                            }),
                        ]),
                    },
                    ManagedPolicyArns: Match.arrayWith([
                        Match.objectLike({
                            'Fn::Join': Match.arrayWith([
                                Match.arrayWith([
                                    Match.stringLikeRegexp('.*AWSCloudFormationFullAccess'),
                                ]),
                            ]),
                        }),
                    ]),
                },
            });

            const roleKeys = Object.keys(roles);
            expect(roleKeys.length).toBeGreaterThan(0);
            const roleLogicalId = roleKeys[0];

            // Find the policy attached to our role
            const allPolicies = template.findResources('AWS::IAM::Policy');
            let targetPolicy: any = null;
            for (const [, policy] of Object.entries(allPolicies)) {
                const policyProps = (policy as any).Properties;
                if (policyProps.Roles && policyProps.Roles.some((role: any) =>
                    role.Ref === roleLogicalId
                )) {
                    targetPolicy = policyProps;
                    break;
                }
            }

            expect(targetPolicy).toBeDefined();

            // Find the policy statement that allows PassRole
            const passRoleStatement = targetPolicy.PolicyDocument.Statement.find((stmt: any) =>
                stmt.Action === 'iam:PassRole'
            );

            expect(passRoleStatement).toBeDefined();
            expect(passRoleStatement.Condition).toBeDefined();
            expect(passRoleStatement.Condition.StringEquals).toBeDefined();
            expect(passRoleStatement.Condition.StringEquals['iam:PassedToService']).toBeDefined();

            // Verify allowed services
            const allowedServices = passRoleStatement.Condition.StringEquals['iam:PassedToService'];
            expect(allowedServices).toContain('cloudformation.amazonaws.com');
            expect(allowedServices).toContain('lambda.amazonaws.com');
            expect(allowedServices).toContain('events.amazonaws.com');
        });
    });

    describe('IAM Policy Structure Validation', () => {
        it('should create the VectorStoreCreator Lambda function with correct role', () => {
            // Verify Lambda function exists
            template.hasResourceProperties('AWS::Lambda::Function', {
                Runtime: Match.stringLikeRegexp('nodejs.*'),
                Timeout: 900, // 15 minutes
                MemorySize: 1024,
            });
        });

        it('should grant necessary permissions for CloudFormation operations', () => {
            // Verify the role has CloudFormation managed policy
            const roles = template.findResources('AWS::IAM::Role', {
                Properties: {
                    ManagedPolicyArns: Match.arrayWith([
                        Match.objectLike({
                            'Fn::Join': Match.arrayWith([
                                Match.arrayWith([
                                    Match.stringLikeRegexp('.*AWSCloudFormationFullAccess'),
                                ]),
                            ]),
                        }),
                    ]),
                },
            });

            expect(Object.keys(roles).length).toBeGreaterThan(0);
        });

        it('should allow service-linked role creation for required services', () => {
            // Find the VectorStoreCreator role
            const roles = template.findResources('AWS::IAM::Role', {
                Properties: {
                    AssumeRolePolicyDocument: {
                        Statement: Match.arrayWith([
                            Match.objectLike({
                                Principal: {
                                    Service: 'lambda.amazonaws.com',
                                },
                            }),
                        ]),
                    },
                    ManagedPolicyArns: Match.arrayWith([
                        Match.objectLike({
                            'Fn::Join': Match.arrayWith([
                                Match.arrayWith([
                                    Match.stringLikeRegexp('.*AWSCloudFormationFullAccess'),
                                ]),
                            ]),
                        }),
                    ]),
                },
            });

            const roleKeys = Object.keys(roles);
            expect(roleKeys.length).toBeGreaterThan(0);
            const roleLogicalId = roleKeys[0];

            // Find the policy attached to our role
            const allPolicies = template.findResources('AWS::IAM::Policy');
            let targetPolicy: any = null;
            for (const [, policy] of Object.entries(allPolicies)) {
                const policyProps = (policy as any).Properties;
                if (policyProps.Roles && policyProps.Roles.some((role: any) =>
                    role.Ref === roleLogicalId
                )) {
                    targetPolicy = policyProps;
                    break;
                }
            }

            expect(targetPolicy).toBeDefined();

            // Find the policy statement that allows CreateServiceLinkedRole
            const serviceLinkedRoleStatement = targetPolicy.PolicyDocument.Statement.find((stmt: any) =>
                stmt.Action === 'iam:CreateServiceLinkedRole'
            );

            expect(serviceLinkedRoleStatement).toBeDefined();
            expect(serviceLinkedRoleStatement.Condition).toBeDefined();
            expect(serviceLinkedRoleStatement.Condition.StringEquals).toBeDefined();
            expect(serviceLinkedRoleStatement.Condition.StringEquals['iam:AWSServiceName']).toBeDefined();

            // Verify allowed services
            const allowedServices = serviceLinkedRoleStatement.Condition.StringEquals['iam:AWSServiceName'];
            expect(allowedServices).toContain('opensearchservice.amazonaws.com');
            expect(allowedServices).toContain('rds.amazonaws.com');
        });
    });
});

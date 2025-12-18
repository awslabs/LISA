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

import { Template } from 'aws-cdk-lib/assertions';
import MockApp from '../mocks/MockApp';
import ConfigParser from '../mocks/ConfigParser';

const LAMBDA_RESOURCE = 'AWS::Lambda::Function';

describe('VPC Configuration Validation', () => {
    // Parse config and print VPC configuration information
    const config = ConfigParser.parseConfig(['config-test.yaml', 'vpc.yaml']);

    beforeAll(() => {
        console.log('\n=== LISA VPC Configuration ===');
        console.log(`VPC ID: ${config.vpcId}`);

        console.log(`Configured Subnets: ${config.subnets?.length}`);
        config.subnets?.forEach((subnet, index) => {
            console.log(`  Subnet ${index + 1}: ${subnet.subnetId} (${subnet.ipv4CidrBlock}) - AZ: ${subnet.availabilityZone}`);
        });
        console.log('===============================\n');
    });

    describe('Lambda VPC and VPC Subnets consistency', () => {
        const stacks = MockApp.create(config).stacks;

        for (const stack of stacks) {
            it(`${stack.stackName} should have consistent VPC configuration for all Lambda functions`, () => {
                const template = Template.fromStack(stack);

                // Get all Lambda functions in the stack
                const lambdaFunctions = template.findResources(LAMBDA_RESOURCE);
                const totalLambdas = Object.keys(lambdaFunctions).length;
                let vpcConfiguredLambdas = 0;
                let nonVpcLambdas = 0;
                let userCreatedNonVpcLambdas = 0;
                const nonVpcLambdaNames: string[] = [];
                const userCreatedNonVpcLambdaNames: string[] = [];

                // CDK-generated function patterns to exclude from VPC requirement
                const cdkGeneratedPatterns = [
                    /^AWS[0-9a-fA-F]+$/,  // AWS CDK custom resources (various lengths)
                    /^Custom.*Provider.*Handler/,  // CDK custom resource providers
                    /^BucketNotificationsHandler/,  // S3 bucket notifications
                    /^LogRetention/,  // CloudWatch log retention
                    /^.*CustomResourceProvider/,  // General custom resource providers
                    /^.*AutoDeleteObjects.*Handler/,  // S3 auto-delete handlers
                    /^.*BucketDeployment.*$/,  // CDK bucket deployment handlers
                    /^.*ASGDrainECSHookFunction/,  // ECS ASG lifecycle hooks
                    /^.*ProviderframeworkonEvent/,  // CDK Provider framework functions
                    /^.*Provider.*onEvent/,  // CDK Provider framework variations
                ];

                console.log(`\n--- ${stack.stackName} Lambda Analysis ---`);
                console.log(`Total Lambda functions: ${totalLambdas}`);

                // Check each Lambda function
                Object.entries(lambdaFunctions).forEach(([functionName, functionResource]) => {
                    const properties = functionResource.Properties;

                    // Check if this is a CDK-generated function
                    const isCdkGenerated = cdkGeneratedPatterns.some((pattern) => pattern.test(functionName));

                    // If VpcConfig is present, validate its structure
                    if (properties?.VpcConfig) {
                        vpcConfiguredLambdas++;
                        const vpcConfig = properties.VpcConfig;

                        // If VpcConfig exists, both SecurityGroupIds and SubnetIds should be present
                        expect(vpcConfig).toHaveProperty('SecurityGroupIds');
                        expect(vpcConfig).toHaveProperty('SubnetIds');

                        // SecurityGroupIds should be an array and not empty
                        expect(Array.isArray(vpcConfig.SecurityGroupIds)).toBe(true);
                        expect(vpcConfig.SecurityGroupIds.length).toBeGreaterThan(0);

                        // SubnetIds should be an array and not empty
                        expect(Array.isArray(vpcConfig.SubnetIds)).toBe(true);
                        expect(vpcConfig.SubnetIds.length).toBeGreaterThan(0);

                        console.log(`  ✓ ${functionName} - VPC configured ${isCdkGenerated ? '(CDK)' : '(User)'}`);
                    } else {
                        nonVpcLambdas++;
                        nonVpcLambdaNames.push(functionName);

                        if (isCdkGenerated) {
                            console.log(`  ℹ ${functionName} - No VPC configuration (CDK-generated, OK)`);
                        } else {
                            userCreatedNonVpcLambdas++;
                            userCreatedNonVpcLambdaNames.push(functionName);
                            console.log(`  ❌ ${functionName} - No VPC configuration (USER-CREATED, should have VPC)`);
                        }
                    }
                });

                console.log(`VPC-configured Lambdas: ${vpcConfiguredLambdas}/${totalLambdas}`);
                console.log(`Non-VPC Lambdas: ${nonVpcLambdas}/${totalLambdas}`);
                console.log(`User-created non-VPC Lambdas: ${userCreatedNonVpcLambdas}/${totalLambdas}`);

                if (nonVpcLambdas > 0) {
                    console.log(`All non-VPC Lambda functions: ${nonVpcLambdaNames.join(', ')}`);
                }

                if (userCreatedNonVpcLambdas > 0) {
                    console.log(`❌ User-created Lambdas missing VPC: ${userCreatedNonVpcLambdaNames.join(', ')}`);
                }

                console.log(`--- End ${stack.stackName} Analysis ---\n`);

                // ENFORCE: All user-created Lambda functions should have VPC configuration when VPC is configured
                if (config.vpcId) {
                    if (userCreatedNonVpcLambdas > 0) {
                        console.error(`\n🚨 ENFORCEMENT FAILURE: Stack ${stack.stackName}`);
                        console.error(`   ${userCreatedNonVpcLambdas} user-created Lambda function(s) missing VPC configuration:`);
                        userCreatedNonVpcLambdaNames.forEach((name) => {
                            console.error(`   ❌ ${name}`);
                        });
                        console.error(`   VPC is configured (${config.vpcId}) - all user-created Lambdas must have VPC settings!\n`);
                    }
                    expect(userCreatedNonVpcLambdas).toBe(0);
                }
            });
        }
    });

    describe('VPC configuration completeness', () => {
        const stacks = MockApp.create(config).stacks;

        for (const stack of stacks) {
            it(`${stack.stackName} Lambda functions with VPC should have complete configuration`, () => {
                const template = Template.fromStack(stack);

                // Get all Lambda functions in the stack
                const lambdaFunctions = template.findResources(LAMBDA_RESOURCE);

                let vpcConfiguredFunctions = 0;
                let incompleteVpcFunctions: string[] = [];

                Object.entries(lambdaFunctions).forEach(([functionName, functionResource]) => {
                    const properties = functionResource.Properties;

                    if (properties?.VpcConfig) {
                        vpcConfiguredFunctions++;
                        const vpcConfig = properties.VpcConfig;

                        // Check for incomplete VPC configuration
                        const hasSecurityGroups = vpcConfig.SecurityGroupIds &&
                                                Array.isArray(vpcConfig.SecurityGroupIds) &&
                                                vpcConfig.SecurityGroupIds.length > 0;

                        const hasSubnets = vpcConfig.SubnetIds &&
                                         Array.isArray(vpcConfig.SubnetIds) &&
                                         vpcConfig.SubnetIds.length > 0;

                        if (!hasSecurityGroups || !hasSubnets) {
                            incompleteVpcFunctions.push(functionName);
                        }
                    }
                });

                // If there are VPC-configured functions, none should have incomplete configuration
                if (vpcConfiguredFunctions > 0) {
                    expect(incompleteVpcFunctions).toEqual([]);

                    if (incompleteVpcFunctions.length > 0) {
                        console.error(`❌ ${stack.stackName} has Lambda functions with incomplete VPC configuration:`, incompleteVpcFunctions);
                    } else {
                        console.log(`✓ ${stack.stackName} has ${vpcConfiguredFunctions} Lambda functions with complete VPC configuration`);
                    }
                }
            });
        }
    });

    describe('Overall Lambda VPC Statistics', () => {
        const stacks = MockApp.create(config).stacks;

        it('should provide summary statistics for all Lambda VPC configurations', () => {
            let totalLambdasAcrossStacks = 0;
            let totalVpcConfiguredLambdas = 0;
            let totalNonVpcLambdas = 0;
            let totalUserCreatedLambdas = 0;
            let totalUserCreatedVpcLambdas = 0;
            let totalUserCreatedNonVpcLambdas = 0;
            const stackSummary: Array<{
                stackName: string,
                total: number,
                vpcConfigured: number,
                nonVpc: number,
                userCreated: number,
                userCreatedVpc: number,
                userCreatedNonVpc: number
            }> = [];

            // CDK-generated function patterns
            const cdkGeneratedPatterns = [
                /^AWS[0-9a-fA-F]+$/,
                /^Custom.*Provider.*Handler/,
                /^BucketNotificationsHandler/,
                /^LogRetention/,
                /^.*CustomResourceProvider/,
                /^.*AutoDeleteObjects.*Handler/,
                /^.*BucketDeployment.*$/,
                /^.*ASGDrainECSHookFunction/,
                /^.*ProviderframeworkonEvent/,
                /^.*Provider.*onEvent/,
            ];

            stacks.forEach((stack) => {
                const template = Template.fromStack(stack);
                const lambdaFunctions = template.findResources(LAMBDA_RESOURCE);
                const stackTotal = Object.keys(lambdaFunctions).length;
                let stackVpcConfigured = 0;
                let stackNonVpc = 0;
                let stackUserCreated = 0;
                let stackUserCreatedVpc = 0;
                let stackUserCreatedNonVpc = 0;

                Object.entries(lambdaFunctions).forEach(([_functionName, functionResource]) => {
                    const isCdkGenerated = cdkGeneratedPatterns.some((pattern) => pattern.test(_functionName));
                    const hasVpcConfig = !!functionResource.Properties?.VpcConfig;

                    if (hasVpcConfig) {
                        stackVpcConfigured++;
                    } else {
                        stackNonVpc++;
                    }

                    if (!isCdkGenerated) {
                        stackUserCreated++;
                        if (hasVpcConfig) {
                            stackUserCreatedVpc++;
                        } else {
                            stackUserCreatedNonVpc++;
                        }
                    }
                });

                totalLambdasAcrossStacks += stackTotal;
                totalVpcConfiguredLambdas += stackVpcConfigured;
                totalNonVpcLambdas += stackNonVpc;
                totalUserCreatedLambdas += stackUserCreated;
                totalUserCreatedVpcLambdas += stackUserCreatedVpc;
                totalUserCreatedNonVpcLambdas += stackUserCreatedNonVpc;

                stackSummary.push({
                    stackName: stack.stackName,
                    total: stackTotal,
                    vpcConfigured: stackVpcConfigured,
                    nonVpc: stackNonVpc,
                    userCreated: stackUserCreated,
                    userCreatedVpc: stackUserCreatedVpc,
                    userCreatedNonVpc: stackUserCreatedNonVpc
                });
            });

            console.log('\n=== OVERALL LAMBDA VPC STATISTICS ===');
            console.log(`Total Lambda functions across all stacks: ${totalLambdasAcrossStacks}`);
            console.log(`VPC-configured Lambdas: ${totalVpcConfiguredLambdas} (${((totalVpcConfiguredLambdas / totalLambdasAcrossStacks) * 100).toFixed(1)}%)`);
            console.log(`Non-VPC Lambdas: ${totalNonVpcLambdas} (${((totalNonVpcLambdas / totalLambdasAcrossStacks) * 100).toFixed(1)}%)`);
            console.log('');
            console.log(`USER-CREATED Lambda functions: ${totalUserCreatedLambdas}`);
            console.log(`User-created VPC-configured: ${totalUserCreatedVpcLambdas} (${totalUserCreatedLambdas > 0 ? ((totalUserCreatedVpcLambdas / totalUserCreatedLambdas) * 100).toFixed(1) : '0'}%)`);
            console.log(`User-created non-VPC: ${totalUserCreatedNonVpcLambdas} (${totalUserCreatedLambdas > 0 ? ((totalUserCreatedNonVpcLambdas / totalUserCreatedLambdas) * 100).toFixed(1) : '0'}%)`);
            console.log('\nPer-stack breakdown:');
            stackSummary.forEach((summary) => {
                if (summary.total > 0) {
                    console.log(`  ${summary.stackName}: ${summary.vpcConfigured}/${summary.total} VPC-configured (${summary.userCreatedVpc}/${summary.userCreated} user-created)`);
                }
            });

            if (totalUserCreatedNonVpcLambdas > 0) {
                console.log(`\n🚨 CRITICAL ISSUE: ${totalUserCreatedNonVpcLambdas} user-created Lambda functions are missing VPC configuration!`);
                console.log('\nLambda functions that need VPC configuration:');

                // Collect all problematic functions across stacks
                const problematicFunctions: string[] = [];
                stacks.forEach((stack) => {
                    const template = Template.fromStack(stack);
                    const lambdaFunctions = template.findResources(LAMBDA_RESOURCE);

                    Object.entries(lambdaFunctions).forEach(([functionName, functionResource]) => {
                        const isCdkGenerated = cdkGeneratedPatterns.some((pattern) => pattern.test(functionName));
                        const hasVpcConfig = !!functionResource.Properties?.VpcConfig;

                        if (!isCdkGenerated && !hasVpcConfig) {
                            problematicFunctions.push(`${stack.stackName}:${functionName}`);
                        }
                    });
                });

                problematicFunctions.forEach((func) => {
                    console.log(`  ❌ ${func}`);
                });

                console.log('\n💡 Action Required: Add VPC configuration to these Lambda functions');
                console.log('   Each function should have: vpc, vpcSubnets, and securityGroups properties');
            } else {
                console.log('\n✅ SUCCESS: All user-created Lambda functions have VPC configuration!');
            }

            console.log('=====================================\n');

            // This test always passes - it's just for reporting statistics
            expect(totalLambdasAcrossStacks).toBeGreaterThanOrEqual(0);
        });
    });

    describe('Security Groups validation when VPC is configured', () => {
        const stacks = MockApp.create(config).stacks;

        for (const stack of stacks) {
            it(`${stack.stackName} Lambda functions should have security groups when VPC is configured in system`, () => {
                const template = Template.fromStack(stack);

                // Get all Lambda functions in the stack
                const lambdaFunctions = template.findResources(LAMBDA_RESOURCE);
                let lambdasWithoutSecurityGroups: string[] = [];
                let userCreatedLambdasWithoutSecurityGroups: string[] = [];
                let totalLambdas = Object.keys(lambdaFunctions).length;
                let totalUserCreatedLambdas = 0;

                // CDK-generated function patterns to exclude from security group requirement
                const cdkGeneratedPatterns = [
                    /^AWS[0-9a-fA-F]+$/,
                    /^Custom.*Provider.*Handler/,
                    /^BucketNotificationsHandler/,
                    /^LogRetention/,
                    /^.*CustomResourceProvider/,
                    /^.*AutoDeleteObjects.*Handler/,
                    /^.*BucketDeployment.*$/,
                    /^.*ASGDrainECSHookFunction/,
                    /^.*ProviderframeworkonEvent/,
                    /^.*Provider.*onEvent/,
                ];

                console.log(`\n--- ${stack.stackName} Security Groups Check (VPC System: ${config.vpcId ? 'CONFIGURED' : 'NOT CONFIGURED'}) ---`);

                // Only enforce security groups if VPC is configured in the system
                if (config.vpcId) {
                    Object.entries(lambdaFunctions).forEach(([functionName, functionResource]) => {
                        const properties = functionResource.Properties;
                        const isCdkGenerated = cdkGeneratedPatterns.some((pattern) => pattern.test(functionName));

                        if (!isCdkGenerated) {
                            totalUserCreatedLambdas++;
                        }

                        // Check if Lambda has VPC configuration with security groups
                        const hasVpcConfig = !!properties?.VpcConfig;
                        const hasSecurityGroups = hasVpcConfig &&
                                                properties.VpcConfig.SecurityGroupIds &&
                                                Array.isArray(properties.VpcConfig.SecurityGroupIds) &&
                                                properties.VpcConfig.SecurityGroupIds.length > 0;

                        if (hasVpcConfig && hasSecurityGroups) {
                            console.log(`  ✓ ${functionName} - VPC with ${properties.VpcConfig.SecurityGroupIds.length} security group(s) ${isCdkGenerated ? '(CDK)' : '(User)'}`);
                        } else if (hasVpcConfig && !hasSecurityGroups) {
                            lambdasWithoutSecurityGroups.push(functionName);
                            if (!isCdkGenerated) {
                                userCreatedLambdasWithoutSecurityGroups.push(functionName);
                            }
                            console.log(`  ❌ ${functionName} - VPC configured but NO security groups ${isCdkGenerated ? '(CDK)' : '(User)'}`);
                        } else if (!hasVpcConfig) {
                            // Lambda without VPC config - this should have been caught by previous tests
                            lambdasWithoutSecurityGroups.push(functionName);
                            if (!isCdkGenerated) {
                                userCreatedLambdasWithoutSecurityGroups.push(functionName);
                            }
                            console.log(`  ❌ ${functionName} - NO VPC configuration (missing security groups) ${isCdkGenerated ? '(CDK)' : '(User)'}`);
                        }
                    });

                    console.log(`Total Lambdas: ${totalLambdas}`);
                    console.log(`User-created Lambdas: ${totalUserCreatedLambdas}`);
                    console.log(`Lambdas with proper security groups: ${totalLambdas - lambdasWithoutSecurityGroups.length}/${totalLambdas}`);
                    console.log(`User-created Lambdas with proper security groups: ${totalUserCreatedLambdas - userCreatedLambdasWithoutSecurityGroups.length}/${totalUserCreatedLambdas}`);

                    if (lambdasWithoutSecurityGroups.length > 0) {
                        console.log(`❌ All Lambdas missing security groups: ${lambdasWithoutSecurityGroups.join(', ')}`);
                    }

                    if (userCreatedLambdasWithoutSecurityGroups.length > 0) {
                        console.log(`❌ User-created Lambdas missing security groups: ${userCreatedLambdasWithoutSecurityGroups.join(', ')}`);
                    }

                    console.log(`--- End ${stack.stackName} Security Groups Check ---\n`);

                    // ENFORCE: When VPC is configured, all user-created Lambda functions must have security groups
                    expect(userCreatedLambdasWithoutSecurityGroups).toEqual([]);
                    if (userCreatedLambdasWithoutSecurityGroups.length > 0) {
                        throw new Error(`Stack ${stack.stackName} has ${userCreatedLambdasWithoutSecurityGroups.length} user-created Lambda functions without security groups when VPC is configured: ${userCreatedLambdasWithoutSecurityGroups.join(', ')}`);
                    }
                } else {
                    console.log('VPC not configured in system - skipping security groups validation');
                    console.log(`--- End ${stack.stackName} Security Groups Check ---\n`);

                    // When VPC is not configured, this test passes (no security groups required)
                    expect(true).toBe(true);
                }
            });
        }
    });

    describe('Security Groups and Subnets validation', () => {
        const stacks = MockApp.create(config).stacks;

        for (const stack of stacks) {
            it(`${stack.stackName} Lambda VPC configurations should reference valid resources`, () => {
                const template = Template.fromStack(stack);

                // Get all Lambda functions in the stack
                const lambdaFunctions = template.findResources(LAMBDA_RESOURCE);

                Object.entries(lambdaFunctions).forEach(([, functionResource]) => {
                    const properties = functionResource.Properties;

                    if (properties?.VpcConfig) {
                        const vpcConfig = properties.VpcConfig;

                        // Validate SecurityGroupIds structure
                        if (vpcConfig.SecurityGroupIds) {
                            vpcConfig.SecurityGroupIds.forEach((sgId: any) => {
                                // Security group IDs should be either strings or references
                                expect(typeof sgId === 'string' || typeof sgId === 'object').toBe(true);

                                // If it's a reference object, it should have a Ref or Fn::GetAtt property
                                if (typeof sgId === 'object') {
                                    expect(sgId.Ref || sgId['Fn::GetAtt'] || sgId['Fn::ImportValue']).toBeDefined();
                                }
                            });
                        }

                        // Validate SubnetIds structure
                        if (vpcConfig.SubnetIds) {
                            vpcConfig.SubnetIds.forEach((subnetId: any) => {
                                // Subnet IDs should be either strings or references
                                expect(typeof subnetId === 'string' || typeof subnetId === 'object').toBe(true);

                                // If it's a reference object, it should have a Ref or Fn::GetAtt property
                                if (typeof subnetId === 'object') {
                                    expect(subnetId.Ref || subnetId['Fn::GetAtt'] || subnetId['Fn::ImportValue']).toBeDefined();
                                }
                            });
                        }
                    }
                });
            });
        }
    });
});

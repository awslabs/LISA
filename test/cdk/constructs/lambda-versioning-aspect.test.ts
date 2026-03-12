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

import { App, Aspects, Stack } from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as fc from 'fast-check';
import { LambdaVersioningAspect } from '../../../lib/util/lambdaVersioningAspect';

/**
 * Validates: Requirements 1.1, 1.2, 1.3
 *
 * Property 1: Bug Condition - Lambda Functions Missing Version Resources
 *
 * For any CDK construct that is an instance of lambda.Function, there should
 * exist a corresponding AWS::Lambda::Version resource in the synthesized
 * CloudFormation template. On unfixed code (no LambdaVersioningAspect),
 * this test is EXPECTED TO FAIL, confirming the bug exists.
 */
describe('Bug Condition Exploration: Lambda Functions Missing Version Resources', () => {
    // Generator for Lambda runtime selection (only runtimes that support inline code)
    const runtimeArb = fc.constantFrom(
        lambda.Runtime.PYTHON_3_12,
        lambda.Runtime.NODEJS_20_X,
    );

    // Generator for handler names
    const handlerArb = fc.constantFrom(
        'index.handler',
        'main.lambda_handler',
        'app.handle',
    );

    // Generator for memory sizes (valid Lambda memory range)
    const memorySizeArb = fc.constantFrom(128, 256, 512, 1024);

    // Generator for Lambda function configurations
    const lambdaConfigArb = fc.record({
        runtime: runtimeArb,
        handler: handlerArb,
        memorySize: memorySizeArb,
    });

    it('every AWS::Lambda::Function should have a corresponding AWS::Lambda::Version resource', () => {
        fc.assert(
            fc.property(
                fc.array(lambdaConfigArb, { minLength: 1, maxLength: 5 }),
                (lambdaConfigs) => {
                    const app = new App();
                    const stack = new Stack(app, 'TestStack');

                    // Create Lambda functions with varying configurations
                    lambdaConfigs.forEach((config, index) => {
                        new lambda.Function(stack, `TestFunction${index}`, {
                            runtime: config.runtime,
                            handler: config.handler,
                            code: lambda.Code.fromInline('exports.handler = async () => {}'),
                            memorySize: config.memorySize,
                        });
                    });

                    // Apply the LambdaVersioningAspect to the stack
                    Aspects.of(stack).add(new LambdaVersioningAspect());

                    const template = Template.fromStack(stack);
                    const functions = template.findResources('AWS::Lambda::Function');
                    const functionLogicalIds = Object.keys(functions);

                    // There must be at least one Lambda function
                    expect(functionLogicalIds.length).toBeGreaterThanOrEqual(lambdaConfigs.length);

                    // Find all Lambda version resources
                    const versions = template.findResources('AWS::Lambda::Version');
                    const versionLogicalIds = Object.keys(versions);

                    // Bug condition check: every Lambda function must have a corresponding Version
                    // On unfixed code, this will FAIL because no versions exist
                    expect(versionLogicalIds.length).toBeGreaterThanOrEqual(functionLogicalIds.length);

                    // Additionally verify each version references a function
                    for (const versionId of versionLogicalIds) {
                        const versionProps = versions[versionId].Properties;
                        expect(versionProps.FunctionName).toBeDefined();
                    }
                },
            ),
            { numRuns: 10 },
        );
    });
});

import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import { RemovalPolicy } from 'aws-cdk-lib';

/**
 * Validates: Requirements 3.1, 3.2, 3.3, 3.4
 *
 * Property 2: Preservation - Non-Lambda Constructs Unchanged
 *
 * For any CDK construct that is NOT an instance of lambda.Function,
 * the LambdaVersioningAspect SHALL not create any child resources or
 * modify the construct in any way.
 */
describe('Preservation: Non-Lambda Constructs Unchanged', () => {
    const aspect = new LambdaVersioningAspect();

    it('DynamoDB Table child count is unchanged after visit', () => {
        const app = new App();
        const stack = new Stack(app, 'TestStack');
        const table = new dynamodb.Table(stack, 'TestTable', {
            partitionKey: { name: 'id', type: dynamodb.AttributeType.STRING },
            removalPolicy: RemovalPolicy.DESTROY,
        });

        const childCountBefore = table.node.children.length;
        aspect.visit(table);
        expect(table.node.children.length).toBe(childCountBefore);
    });

    it('S3 Bucket child count is unchanged after visit', () => {
        const app = new App();
        const stack = new Stack(app, 'TestStack');
        const bucket = new s3.Bucket(stack, 'TestBucket', {
            removalPolicy: RemovalPolicy.DESTROY,
        });

        const childCountBefore = bucket.node.children.length;
        aspect.visit(bucket);
        expect(bucket.node.children.length).toBe(childCountBefore);
    });

    it('SQS Queue child count is unchanged after visit', () => {
        const app = new App();
        const stack = new Stack(app, 'TestStack');
        const queue = new sqs.Queue(stack, 'TestQueue');

        const childCountBefore = queue.node.children.length;
        aspect.visit(queue);
        expect(queue.node.children.length).toBe(childCountBefore);
    });

    it('no AWS::Lambda::Version resources are created for non-Lambda constructs', () => {
        fc.assert(
            fc.property(
                fc.constantFrom('dynamodb', 's3', 'sqs'),
                (constructType) => {
                    const app = new App();
                    const stack = new Stack(app, 'TestStack');

                    switch (constructType) {
                        case 'dynamodb':
                            new dynamodb.Table(stack, 'Resource', {
                                partitionKey: { name: 'id', type: dynamodb.AttributeType.STRING },
                                removalPolicy: RemovalPolicy.DESTROY,
                            });
                            break;
                        case 's3':
                            new s3.Bucket(stack, 'Resource', {
                                removalPolicy: RemovalPolicy.DESTROY,
                            });
                            break;
                        case 'sqs':
                            new sqs.Queue(stack, 'Resource');
                            break;
                    }

                    // Apply aspect via visit on all children
                    stack.node.findAll().forEach((child) => aspect.visit(child));

                    const template = Template.fromStack(stack);
                    const versions = template.findResources('AWS::Lambda::Version');
                    expect(Object.keys(versions).length).toBe(0);
                },
            ),
            { numRuns: 10 },
        );
    });
});

/**
 * Validates: Requirements 3.1, 3.3
 *
 * Preservation: Lambda function properties (runtime, handler, environment)
 * are not modified by the aspect.
 */
describe('Preservation: Lambda Function Properties Unchanged', () => {
    const aspect = new LambdaVersioningAspect();

    it('existing Lambda function properties are not modified by the aspect', () => {
        fc.assert(
            fc.property(
                fc.record({
                    runtime: fc.constantFrom(
                        lambda.Runtime.PYTHON_3_12,
                        lambda.Runtime.NODEJS_20_X,
                    ),
                    handler: fc.constantFrom('index.handler', 'main.lambda_handler', 'app.handle'),
                    memorySize: fc.constantFrom(128, 256, 512, 1024),
                    envKey: fc.constantFrom('ENV_VAR_A', 'ENV_VAR_B'),
                    envVal: fc.constantFrom('value1', 'value2'),
                }),
                (config) => {
                    const app = new App();
                    const stack = new Stack(app, 'TestStack');

                    const fn = new lambda.Function(stack, 'TestFunction', {
                        runtime: config.runtime,
                        handler: config.handler,
                        code: lambda.Code.fromInline('exports.handler = async () => {}'),
                        memorySize: config.memorySize,
                        environment: { [config.envKey]: config.envVal },
                    });

                    // Capture properties before visit
                    const runtimeBefore = fn.runtime;
                    const handlerBefore = fn.node.tryGetContext('handler') ?? config.handler;

                    aspect.visit(fn);

                    // Verify runtime and handler are unchanged
                    expect(fn.runtime).toBe(runtimeBefore);

                    // Synthesize and verify CloudFormation properties
                    const template = Template.fromStack(stack);
                    template.hasResourceProperties('AWS::Lambda::Function', {
                        Runtime: config.runtime.name,
                        Handler: config.handler,
                        MemorySize: config.memorySize,
                        Environment: {
                            Variables: {
                                [config.envKey]: config.envVal,
                            },
                        },
                    });
                },
            ),
            { numRuns: 10 },
        );
    });
});

/**
 * Validates: Requirements 3.2
 *
 * Preservation: The aspect does not create duplicate versions if visited
 * twice on the same function. With the no-op stub, this is trivially true.
 */
describe('Preservation: No Duplicate Versions on Double Visit', () => {
    const aspect = new LambdaVersioningAspect();

    it('visiting the same Lambda function twice does not create duplicate versions', () => {
        const app = new App();
        const stack = new Stack(app, 'TestStack');

        const fn = new lambda.Function(stack, 'TestFunction', {
            runtime: lambda.Runtime.NODEJS_20_X,
            handler: 'index.handler',
            code: lambda.Code.fromInline('exports.handler = async () => {}'),
        });

        aspect.visit(fn);
        const childCountAfterFirst = fn.node.children.length;
        aspect.visit(fn);
        const childCountAfterSecond = fn.node.children.length;

        // After first visit, a Version child is added; second visit should not add another
        expect(childCountAfterSecond).toBe(childCountAfterFirst);
    });
});

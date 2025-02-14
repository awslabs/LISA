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
import { Aspects, Stack } from 'aws-cdk-lib';
import { Annotations, Match } from 'aws-cdk-lib/assertions';
import { AwsSolutionsChecks, NIST80053R5Checks } from 'cdk-nag';

import MockApp from '../mocks/MockApp';

type NagResult = {
    [key: string]: [number, number, number, number]
};

enum NagType {
    AWSNAGWARN,
    AWSNAGERROR,
    NISTWARN,
    NISTERROR
}

const nagResults: NagResult = {
    LisaApiBase: [1,7,0,5],
    LisaApiDeployment: [0,0,0,0],
    LisaChat: [2,20,0,11],
    LisaCore: [0,0,0,0],
    LisaDocs: [1,23,0,13],
    LisaIAM: [0,14,0,0],
    LisaModels: [1,74,0,28],
    LisaNetworking: [1,2,3,5],
    LisaRAG: [2,66,0,31],
    LisaServe: [1,21,0,31],
    LisaUI: [0,16,0,8],
};

describe('Nag Pack Tests', () => {
    const stacks: Stack[] = MockApp.getStacks();

    beforeAll(() => {
        stacks.forEach((stack) => {
            Aspects.of(stack).add(new AwsSolutionsChecks({ verbose: true }));
            Aspects.of(stack).add(new NIST80053R5Checks({ verbose: true }));
        });
    });

    describe('AwsSolutions CDK NAG Warnings', () => {
        test.each(stacks)('AwsSolutions CDK NAG Warnings for $_stackName', (stack) => {
            const warnings = Annotations.fromStack(stack).findWarning('*', Match.stringLikeRegexp('AwsSolutions-.*'));
            expect(warnings.length).toBe(nagResults[stack.stackName][NagType.AWSNAGWARN] || 0);
        });
    });

    describe('AwsSolutions CDK NAG Errors', () => {
        test.each(stacks)('AwsSolutions CDK NAG Errors for $_stackName', (stack) => {
            const errors = Annotations.fromStack(stack).findError('*', Match.stringLikeRegexp('AwsSolutions-.*'));
            expect(errors.length).toBe(nagResults[stack.stackName][NagType.AWSNAGERROR] || 0);
        });
    });

    describe('NIST800.53r5 CDK NAG Warnings', () => {
        test.each(stacks)('NIST800.53r5 CDK NAG Warnings for $_stackName', (stack) => {
            const warnings = Annotations.fromStack(stack).findWarning('*', Match.stringLikeRegexp('NIST.*'));
            expect(warnings.length).toBe(nagResults[stack.stackName][NagType.NISTWARN] || 0);
        });
    });

    describe('NIST800.53r5 CDK NAG Errors', () => {
        test.each(stacks)('NIST800.53r5 CDK NAG Errors for $_stackName', (stack) => {
            const errors = Annotations.fromStack(stack).findError('*', Match.stringLikeRegexp('NIST.*'));
            expect(errors.length).toBe(nagResults[stack.stackName][NagType.NISTERROR] || 0);
        });
    });
});

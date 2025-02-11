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
import { App, Aspects, Stack, StackProps } from 'aws-cdk-lib';
import { Annotations, Match } from 'aws-cdk-lib/assertions';
import { AwsSolutionsChecks, NIST80053R5Checks } from 'cdk-nag';

import { createCdkId } from '../../../lib/core/utils';
import { LisaNetworkingStack } from '../../../lib/networking';
import { BaseProps, Config } from '../../../lib/schema';
import ConfigParser from '../mocks/ConfigParser';

type TestConfig = [string, number, number, number, number];
type TestValues = [number, number, number, number];

const defaultWarnings: TestValues = [1, 1, 3, 5];
const regions: TestConfig[] = [
    ['us-east-1', ...defaultWarnings],
    ['us-gov-west-1', ...defaultWarnings],
    ['us-gov-east-1', ...defaultWarnings],
    ['us-isob-east-1', ...defaultWarnings],
    ['us-iso-east-1', ...defaultWarnings],
    ['us-iso-west-1', ...defaultWarnings],
];

describe.each<TestConfig>(regions)(
    'Network Nag Pack Tests | Region Test: %s',
    (awsRegion, awsSolWarns, awsSolErr, nistWarn, nistErr) => {
        let app: App;
        let stack: Stack;
        let config: Config;
        let baseStackProps: BaseProps & StackProps;

        beforeAll(() => {
            app = new App();
            config = ConfigParser.parseConfig();
            baseStackProps = {
                env: {
                    account: '012345678901',
                    region: awsRegion,
                },
                config,
            };
        });

        beforeEach(() => {
            stack = new LisaNetworkingStack(app, `TestNetworking${awsRegion}`, {
                ...baseStackProps,
                config: config,
                stackName: createCdkId([config.deploymentName, config.appName, 'networking', config.deploymentStage]),
                description: `LISA-networking: ${config.deploymentName}-${config.deploymentStage}`,
            });
            // WHEN
            Aspects.of(stack).add(new AwsSolutionsChecks({ verbose: true }));
            Aspects.of(stack).add(new NIST80053R5Checks({ verbose: true }));
        });

        afterEach(() => {
            app = new App();
            stack = new Stack();
        });

        //TODO Update expect values to remediate CDK NAG findings and remove debug
        test('AwsSolutions CDK NAG Warnings', () => {
            const warnings = Annotations.fromStack(stack).findWarning('*', Match.stringLikeRegexp('AwsSolutions-.*'));
            expect(warnings.length).toBe(awsSolWarns);
        });

        test('AwsSolutions CDK NAG Errors', () => {
            const errors = Annotations.fromStack(stack).findError('*', Match.stringLikeRegexp('AwsSolutions-.*'));
            expect(errors.length).toBe(awsSolErr);
        });

        test('NIST800.53r5 CDK NAG Warnings', () => {
            const warnings = Annotations.fromStack(stack).findWarning('*', Match.stringLikeRegexp('NIST.*'));
            expect(warnings.length).toBe(nistWarn);
        });

        test('NIST800.53r5 CDK NAG Errors', () => {
            const errors = Annotations.fromStack(stack).findError('*', Match.stringLikeRegexp('NIST.*'));
            expect(errors.length).toBe(nistErr);
        });
    },
);

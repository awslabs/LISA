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

import { LisaApiBaseStack } from '../../../lib/core/api_base';
import { createCdkId } from '../../../lib/core/utils';
import { LisaNetworkingStack } from '../../../lib/networking';
import { BaseProps, Config } from '../../../lib/schema';
import ConfigParser from '../mocks/ConfigParser';

const regions = ['us-east-1', 'us-gov-west-1', 'us-gov-east-1', 'us-isob-east-1', 'us-iso-east-1', 'us-iso-west-1'];

describe.each(regions)('API Core Nag Pack Tests | Region Test: %s', (awsRegion) => {
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
        const networkingStack = new LisaNetworkingStack(app, `TestNetworking${awsRegion}`, {
            ...baseStackProps,
            stackName: createCdkId([config.deploymentName, config.appName, 'networking', config.deploymentStage]),
            description: `LISA-networking: ${config.deploymentName}-${config.deploymentStage}`,
        });

        const tempStack = new LisaApiBaseStack(app, 'LisaApiBase', {
            ...baseStackProps,
            stackName: createCdkId([config.deploymentName, config.appName, 'API']),
            description: `LISA-API: ${config.deploymentName}-${config.deploymentStage}`,
            vpc: networkingStack.vpc,
        });

        tempStack.authorizer._attachToApi(tempStack.restApi);
        stack = tempStack;

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
        expect(warnings.length).toBe(1);
    });

    test('AwsSolutions CDK NAG Errors', () => {
        const errors = Annotations.fromStack(stack).findError('*', Match.stringLikeRegexp('AwsSolutions-.*'));
        expect(errors.length).toBe(9);
    });

    test('NIST800.53r5 CDK NAG Warnings', () => {
        const warnings = Annotations.fromStack(stack).findWarning('*', Match.stringLikeRegexp('NIST.*'));
        expect(warnings.length).toBe(0);
    });

    test('NIST800.53r5 CDK NAG Errors', () => {
        const errors = Annotations.fromStack(stack).findError('*', Match.stringLikeRegexp('NIST.*'));
        expect(errors.length).toBe(5);
    });
});

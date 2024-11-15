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

import * as fs from 'fs';
import * as path from 'path';

import { App, Aspects, Stack, StackProps } from 'aws-cdk-lib';
import { Annotations, Match } from 'aws-cdk-lib/assertions';
import { AwsSolutionsChecks, NIST80053R5Checks } from 'cdk-nag';
import * as yaml from 'js-yaml';

import { ARCHITECTURE } from '../../../lib/core';
import { LisaApiBaseStack } from '../../../lib/core/api_base';
import { createCdkId } from '../../../lib/core/utils';
import { LisaNetworkingStack } from '../../../lib/networking/index';
import { BaseProps, Config, ConfigFile, ConfigSchema } from '../../../lib/schema';
import { UserInterfaceStack } from '../../../lib/user-interface';

const regions = ['us-east-1', 'us-gov-west-1', 'us-gov-east-1', 'us-isob-east-1', 'us-iso-east-1', 'us-iso-west-1'];

describe.each(regions)('UI Nag Pack Tests | Region Test: %s', (awsRegion) => {
    let app: App;
    let stack: Stack;
    let config: Config;
    let baseStackProps: BaseProps & StackProps;

    beforeAll(() => {
        app = new App();

        // Read configuration file
        const configFilePath = path.join(__dirname, '../../../test/cdk/mocks/config.yaml');
        const configFile = yaml.load(fs.readFileSync(configFilePath, 'utf8')) as ConfigFile;
        const configEnv = configFile.env || 'dev';
        const configData = configFile[configEnv];
        if (!configData) {
            throw new Error(`Configuration for environment "${configEnv}" not found.`);
        }
        // Validate and parse configuration
        try {
            config = ConfigSchema.parse(configData);
        } catch (error) {
            if (error instanceof Error) {
                console.error('Error parsing the configuration:', error.message);
            } else {
                console.error('An unexpected error occurred:', error);
            }
            process.exit(1);
        }

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

        const apiBaseStack = new LisaApiBaseStack(app, 'LisaApiBase', {
            ...baseStackProps,
            stackName: createCdkId([config.deploymentName, config.appName, 'API']),
            description: `LISA-API: ${config.deploymentName}-${config.deploymentStage}`,
            vpc: networkingStack.vpc,
        });

        stack = new UserInterfaceStack(app, 'LisaUserInterface', {
            ...baseStackProps,
            architecture: ARCHITECTURE,
            stackName: createCdkId([config.deploymentName, config.appName, 'ui', config.deploymentStage]),
            description: `LISA-user-interface: ${config.deploymentName}-${config.deploymentStage}`,
            restApiId: apiBaseStack.restApiId,
            rootResourceId: apiBaseStack.rootResourceId,
        });

        apiBaseStack.authorizer._attachToApi(apiBaseStack.restApi);

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
        expect(warnings.length).toBe(0);
    });

    test('AwsSolutions CDK NAG Errors', () => {
        const errors = Annotations.fromStack(stack).findError('*', Match.stringLikeRegexp('AwsSolutions-.*'));
        expect(errors.length).toBe(16);
    });

    test('NIST800.53r5 CDK NAG Warnings', () => {
        const warnings = Annotations.fromStack(stack).findWarning('*', Match.stringLikeRegexp('NIST.*'));
        expect(warnings.length).toBe(0);
    });

    test('NIST800.53r5 CDK NAG Errors', () => {
        const errors = Annotations.fromStack(stack).findError('*', Match.stringLikeRegexp('NIST.*'));
        expect(errors.length).toBe(8);
    });
});

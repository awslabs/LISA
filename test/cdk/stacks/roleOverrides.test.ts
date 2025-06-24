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
import MockApp from '../mocks/MockApp'; // Import your actual stack
import ConfigParser from '../mocks/ConfigParser';
import { Roles } from '../../../lib/core/iam/roles';
import { Stack } from 'aws-cdk-lib';

const stackRolesOverrides: Record<string, number> = {
    'LisaApiBase': 1,
    'LisaServe': 3,
    'LisaUI': 1,
    'LisaDocs': 2,
    'LisaRAG': 4,
    'LisaChat': 1,
    'LisaCore': 1,
};

const stackRoles: Record<string, number> = {
    'LisaApiBase': 2,
    'LisaServe': 4,
    'LisaUI': 3,
    'LisaNetworking': 0,
    'LisaChat': 5,
    'LisaCore': 1,
    'LisaApiDeployment': 0,
    'LisaIAM': 2,
    'LisaDocs': 4,
    'LisaModels': 9,
    'LisaRAG': 4,
};

describe('Verify role overrides', () => {
    const config = ConfigParser.parseConfig(['config-test.yaml', 'roles.yaml']);
    expect(Object.keys(config.roles || {}).length).toBe(Object.keys(Roles).length);

    const { stacks } = MockApp.create(config);
    describe('Number of IAM Roles created with overrides', () => {
        for (const stack of stacks) {
            const expectedRoles = stackRolesOverrides[stack.stackName] || 0;

            it(`${stack} should contain ${expectedRoles} roles`, () => {
                const template = Template.fromStack(stack);
                template.resourceCountIs('AWS::IAM::Role', expectedRoles);
            });
        }
    });
});

describe('Verify created roles', () => {
    const stacks: Stack[] = MockApp.getStacks();
    describe('Number of IAM Roles created', () => {

        for (const stack of stacks) {
            const expectedRoles = stackRoles[stack.stackName] || 0;

            it(`${stack} should contain ${expectedRoles} roles`, () => {
                const template = Template.fromStack(stack);
                console.log(stack.stackName);
                template.resourceCountIs('AWS::IAM::Role', expectedRoles);
            });
        }
    });
});

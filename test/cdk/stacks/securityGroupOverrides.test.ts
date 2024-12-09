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

const stackGroupOverrides: Record<string, number> = {
    LisaServe: 1,
};

const stackGroups: Record<string, number> = {
    LisaServe: 2,
    LisaNetworking: 3,
    LisaRAG: 1,
};
const RESOURCE = 'AWS::EC2::SecurityGroup';

describe('Verify security group overrides', () => {
    describe('Number of Security Groups created with overrides', () => {
        const config = ConfigParser.parseConfig(['config.yaml', 'security-groups.yaml']);

        const { stacks } = MockApp.create(config);

        for (const stack of stacks) {
            const expectedGroups = stackGroupOverrides[stack.stackName] || 0;

            it(`${stack} should contain ${expectedGroups} Groups`, () => {
                const template = Template.fromStack(stack);
                template.resourceCountIs(RESOURCE, expectedGroups);
            });
        }
    });
});

describe('Verify created security groups', () => {
    describe('Number of Security Groups created', () => {
        const { stacks } = MockApp.create();

        for (const stack of stacks) {
            const expectedGroups = stackGroups[stack.stackName] || 0;

            it(`${stack} should contain ${expectedGroups} groups`, () => {
                const template = Template.fromStack(stack);
                template.resourceCountIs(RESOURCE, expectedGroups);
            });
        }
    });
});

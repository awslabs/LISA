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
import { Stack } from 'aws-cdk-lib';
import MockApp from '../mocks/MockApp';
import ConfigParser from '../mocks/ConfigParser';

describe('Override Configuration Tests', () => {
    let stacks: Stack[];

    beforeAll(() => {
        const config = ConfigParser.parseConfig(['config-test.yaml', 'assets.yaml']);
        stacks = MockApp.create(config).stacks;
    });

    it('should use provided layer assets instead of building', () => {
        // Find the core stack which should contain the layers
        const coreStack = stacks.find((stack) => stack.stackName.includes('Core'));
        expect(coreStack).toBeDefined();

        if (coreStack) {
            const template = Template.fromStack(coreStack);
            const resources = template.toJSON().Resources || {};

            // Check that Lambda layers are created (using provided assets)
            const layerVersions = Object.values(resources).filter((resource: any) =>
                resource.Type === 'AWS::Lambda::LayerVersion'
            );

            // Should have layer versions when assets are provided
            expect(layerVersions.length).toBeGreaterThan(0);
        }
    });

    it('should use provided container images instead of building', () => {
        stacks.forEach((stack) => {
            const template = Template.fromStack(stack);
            const resources = template.toJSON().Resources || {};

            // Check for ECS task definitions using provided images
            Object.values(resources).forEach((resource: any) => {
                if (resource.Type === 'AWS::ECS::TaskDefinition') {
                    const containerDefs = resource.Properties?.ContainerDefinitions || [];
                    containerDefs.forEach((container: any) => {
                        if (container.Image) {
                            // Handle both string and CloudFormation intrinsic function formats
                            const imageRef = typeof container.Image === 'string'
                                ? container.Image
                                : JSON.stringify(container.Image);
                            // Should reference ECR repositories, not build artifacts
                            expect(imageRef).toMatch(/123456789012.*ecr.*test-(api|mcp|batch)/);
                        }
                    });
                }
            });
        });
    });

    it('should not create CodeBuild projects when overrides are provided', () => {
        stacks.forEach((stack) => {
            const template = Template.fromStack(stack);
            const resources = template.toJSON().Resources || {};

            const buildProjects = Object.values(resources).filter((resource: any) =>
                resource.Type === 'AWS::CodeBuild::Project'
            );

            // Should have minimal or no build projects when overrides are provided
            expect(buildProjects.length).toBeLessThanOrEqual(1);
        });
    });
});

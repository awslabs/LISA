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
import fs from 'fs';
import path from 'path';

const BASELINE_DIR = path.join(__dirname, '__baselines__');

describe('Stack Migration Tests', () => {
    const stacks = MockApp.getStacks();

    stacks?.forEach((stack: Stack) => {
        xit(`${stack.stackName} is compatible with baseline`, () => {
            const template = Template.fromStack(stack);
            const current = template.toJSON();
            const baselinePath = path.join(BASELINE_DIR, `${stack.stackName}.json`);

            if (!fs.existsSync(baselinePath)) {
                console.warn(`No baseline found for ${stack.stackName}, creating one`);
                fs.mkdirSync(BASELINE_DIR, { recursive: true });
                fs.writeFileSync(baselinePath, JSON.stringify(current, null, 2));
                return;
            }

            const baseline = JSON.parse(fs.readFileSync(baselinePath, 'utf-8'));
            const replacements = detectResourceReplacements(baseline, current);

            expect(replacements).toEqual([]);
        });
    });
});

function detectResourceReplacements(baseline: any, current: any): string[] {
    const replacements: string[] = [];
    const baselineResources = baseline.Resources || {};
    const currentResources = current.Resources || {};

    for (const [logicalId, baselineResource] of Object.entries(baselineResources)) {
        const currentResource = currentResources[logicalId];

        if (!currentResource) {
            replacements.push(`Resource ${logicalId} was removed`);
        } else if ((baselineResource as any).Type !== (currentResource as any).Type) {
            replacements.push(`Resource ${logicalId} type changed from ${(baselineResource as any).Type} to ${(currentResource as any).Type}`);
        }
    }

    return replacements;
}

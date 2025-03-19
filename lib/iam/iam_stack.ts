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
import { Stack } from 'aws-cdk-lib';
import { NagSuppressions } from 'cdk-nag';
import { Construct } from 'constructs';

import { LisaIAMStackProps, LisaServeIAMSConstruct } from './iamConstruct';

/**
 * LisaServe IAM stack.
 */
export class LisaServeIAMStack extends Stack {

    /**
     * @param {Construct} scope - The parent or owner of the construct.
     * @param {string} id - The unique identifier for the construct within its scope.
     * @param {LisaIAMStackProps} props - Properties for the Stack.
     */
    constructor (scope: Construct, id: string, props: LisaIAMStackProps) {
        super(scope, id, props);
        // Add suppression for IAM4 (use of managed policy)
        NagSuppressions.addStackSuppressions(this, [
            {
                id: 'AwsSolutions-IAM4',
                reason: 'Allow use of AmazonSSMManagedInstanceCore policy to allow EC2 to enable SSM core functionality.',
            },
        ]);

        (new LisaServeIAMSConstruct(this, id + 'Resources', props)).node.addMetadata('aws:cdk:path', this.node.path);
    }
}

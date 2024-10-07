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

import { Stack, StackProps } from 'aws-cdk-lib';

import { Vpc, SecurityGroup } from 'aws-cdk-lib/aws-ec2';

import { Construct } from 'constructs';
import { EcsModel } from './ecs-model';

import { Config, ModelConfig } from './schema';

export type LisaModelStackProps = {
    vpcId: string;
    securityGroupId: string;
    config: Config;
    modelConfig: ModelConfig;
} & StackProps;

export class LisaModelStack extends Stack {
    constructor (scope: Construct, id: string, props: LisaModelStackProps) {
        super(scope, id, props);

        const vpc = Vpc.fromLookup(this, 'vpc', {
            vpcId: props.vpcId
        });

        const securityGroup = SecurityGroup.fromLookupById(this, 'sg', props.securityGroupId);

        new EcsModel(this, 'EcsModel', {
            config: props.config,
            modelConfig: props.modelConfig,
            securityGroup: securityGroup,
            vpc: vpc
        });
    }
}

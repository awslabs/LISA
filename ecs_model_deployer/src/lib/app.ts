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

import { AddPermissionBoundary } from '@cdklabs/cdk-enterprise-iac';
import { Aspects, App } from 'aws-cdk-lib';
import { LisaModelStack, LisaModelStackProps } from './lisa_model_stack';

import { ConfigFile, ConfigSchema } from './ecs-schema';

export const app = new App();

const configFile = JSON.parse(process.env['LISA_CONFIG']!) as ConfigFile;
const config = ConfigSchema.parse(configFile);

const modelConfig = JSON.parse(process.env['LISA_MODEL_CONFIG']!);

const stackProps: LisaModelStackProps = {
    env: {
        account: process.env['CDK_DEFAULT_ACCOUNT'],
        region: process.env['CDK_DEFAULT_REGION']
    },
    vpcId: process.env['LISA_VPC_ID']!,
    securityGroupId: process.env['LISA_SECURITY_GROUP_ID']!,
    config: config,
    modelConfig: modelConfig
};

const lisaModelStack = new LisaModelStack(app, `${config.deploymentName}-${modelConfig.modelId}`, stackProps);

if (config.permissionsBoundaryAspect) {
    Aspects.of(lisaModelStack).add(new AddPermissionBoundary(config.permissionsBoundaryAspect!));
}

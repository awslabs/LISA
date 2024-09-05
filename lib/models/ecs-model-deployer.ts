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

import { Construct } from 'constructs';
import { Code, Function, Runtime } from 'aws-cdk-lib/aws-lambda';
import { Role, ServicePrincipal, Policy, PolicyStatement } from 'aws-cdk-lib/aws-iam';
import { Stack, Duration, Size } from 'aws-cdk-lib';

import { createCdkId } from '../core/utils';
import { BaseProps, Config } from '../schema';

export type ECSModelDeployerProps = {
    vpcId: string;
    securityGroupId: string;
    config: Config;
} & BaseProps;

export class ECSModelDeployer extends Construct {
    constructor (scope: Construct, id: string, props: ECSModelDeployerProps) {
        super(scope, id);
        const stackName = Stack.of(scope).stackName;
        const role = new Role(this, createCdkId([stackName, 'ecs-model-deployer-role']), {
            assumedBy: new ServicePrincipal('lambda.amazonaws.com')
        });

        const assumeCdkPolicy = new Policy(this, createCdkId([stackName, 'ecs-model-deployer-policy']), {
            statements: [
                new PolicyStatement({
                    actions: ['sts:AssumeRole'],
                    resources: ['arn:*:iam::*:role/cdk-*']
                })
            ]
        });

        role.attachInlinePolicy(assumeCdkPolicy);

        const stripped_config = {
            'appName': props.config.appName,
            'deploymentName': props.config.deploymentName,
            'region': props.config.region,
            'deploymentStage': props.config.deploymentStage,
            'removalPolicy': props.config.removalPolicy,
            's3BucketModels': props.config.s3BucketModels,
            'mountS3DebUrl': props.config.mountS3DebUrl
        };

        const functionId = createCdkId([stackName, 'ecs_model_deployer']);
        new Function(this, functionId, {
            functionName: functionId,
            runtime: Runtime.NODEJS_18_X,
            handler: 'index.handler',
            code: Code.fromAsset('./ecs_model_deployer/dist/'),
            timeout: Duration.minutes(10),
            ephemeralStorageSize: Size.mebibytes(2048),
            memorySize: 1024,
            role: role,
            environment: {
                'LISA_VPC_ID': props.vpcId,
                'LISA_SECURITY_GROUP_ID': props.securityGroupId,
                'LISA_CONFIG': JSON.stringify(stripped_config)
            }
        });
    }
}

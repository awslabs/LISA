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
import { Role, InstanceProfile, ServicePrincipal, ManagedPolicy, Policy, PolicyStatement } from 'aws-cdk-lib/aws-iam';
import { Stack, Duration } from 'aws-cdk-lib';
import { Bucket } from 'aws-cdk-lib/aws-s3';
import { BucketDeployment, Source } from 'aws-cdk-lib/aws-s3-deployment';

import { createCdkId } from '../core/utils';

export type DockerImageBuilderProps = {
    ecrUri: string;
    mountS3DebUrl: string;
};

export class DockerImageBuilder extends Construct {
    readonly dockerImageBuilderFn: Function;

    constructor (scope: Construct, id: string, props: DockerImageBuilderProps) {
        super(scope, id);

        const stackName = Stack.of(scope).stackName;

        const ec2InstanceProfileRole = new Role(this, createCdkId([stackName, 'docker-image-builder-ec2-role']), {
            roleName: createCdkId([stackName, 'docker-image-builder-ec2-role']),
            assumedBy: new ServicePrincipal('ec2.amazonaws.com')
        });

        const ec2DockerBucket = new Bucket(this, createCdkId([stackName, 'docker-image-builder-ec2-bucket']));
        new BucketDeployment(this, createCdkId([stackName, 'docker-image-builder-ec2-dplmnt']), {
            sources: [Source.asset('./lib/serve/ecs-model/')],
            destinationBucket: ec2DockerBucket
        });

        const ec2InstanceProfilePolicy = new Policy(this, createCdkId([stackName, 'docker-image-builder-ec2-policy']), {
            statements: [
                new PolicyStatement({
                    actions: [
                        's3:GetObject',
                    ],
                    resources: [`${ec2DockerBucket.bucketArn}/*`]
                }),
                new PolicyStatement({
                    actions: [
                        's3:ListBucket',
                    ],
                    resources: [ec2DockerBucket.bucketArn]
                }),
                new PolicyStatement({
                    actions: [
                        'ecr:GetAuthorizationToken',
                        'ecr:InitiateLayerUpload',
                        'ecr:UploadLayerPart',
                        'ecr:CompleteLayerUpload',
                        'ecr:PutImage',
                        'ecr:BatchCheckLayerAvailability'
                    ],
                    resources: ['*']
                })
            ]
        });

        ec2InstanceProfileRole.attachInlinePolicy(ec2InstanceProfilePolicy);

        const role = new Role(this, createCdkId([stackName, 'docker_image_builder_role']), {
            roleName: createCdkId([stackName, 'docker_image_builder_role']),
            assumedBy: new ServicePrincipal('lambda.amazonaws.com')
        });

        const assumeCdkPolicy = new Policy(this, createCdkId([stackName, 'docker-image-builder-policy']), {
            statements: [
                new PolicyStatement({
                    actions: [
                        'ec2:RunInstances',
                        'ec2:CreateTags'
                    ],
                    resources: ['*']
                }),
                new PolicyStatement({
                    actions: ['iam:PassRole'],
                    resources: [ec2InstanceProfileRole.roleArn]
                }),
                new PolicyStatement({
                    actions: ['ssm:GetParameter'],
                    resources: ['arn:*:ssm:*::parameter/aws/service/*']
                })
            ]
        });

        role.attachInlinePolicy(assumeCdkPolicy);
        role.addManagedPolicy(ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'));

        const ec2InstanceProfileId = createCdkId([stackName, 'docker-image-builder-profile']);
        const ec2InstanceProfile = new InstanceProfile(this, ec2InstanceProfileId, {
            instanceProfileName: ec2InstanceProfileId,
            role: ec2InstanceProfileRole
        });

        const functionId = createCdkId([stackName, 'docker-image-builder']);
        this.dockerImageBuilderFn = new Function(this, functionId, {
            functionName: functionId,
            runtime: Runtime.PYTHON_3_12,
            handler: 'dockerimagebuilder.handler',
            code: Code.fromAsset('./lambda/'),
            timeout: Duration.minutes(1),
            memorySize: 1024,
            role: role,
            environment: {
                'LISA_DOCKER_BUCKET': ec2DockerBucket.bucketName,
                'LISA_ECR_URI': props.ecrUri,
                'LISA_INSTANCE_PROFILE': ec2InstanceProfile.instanceProfileArn,
                'LISA_MOUNTS3_DEB_URL': props.mountS3DebUrl
            }
        });

    }
}

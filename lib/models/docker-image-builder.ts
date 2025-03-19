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
import {
    InstanceProfile,
    IRole,
    ManagedPolicy,
    Policy,
    PolicyStatement,
    Role,
    ServicePrincipal,
} from 'aws-cdk-lib/aws-iam';
import { Code, Function } from 'aws-cdk-lib/aws-lambda';
import { Duration, Stack } from 'aws-cdk-lib';
import { Bucket } from 'aws-cdk-lib/aws-s3';
import { BucketDeployment, Source } from 'aws-cdk-lib/aws-s3-deployment';
import { ISecurityGroup } from 'aws-cdk-lib/aws-ec2';
import { createCdkId } from '../core/utils';
import { BaseProps } from '../schema';
import { Vpc } from '../networking/vpc';
import { Roles } from '../core/iam/roles';
import { Queue } from 'aws-cdk-lib/aws-sqs';
import { getDefaultRuntime } from '../api-base/utils';
import * as path from 'path';

const HERE = path.resolve(__dirname);

export type DockerImageBuilderProps = BaseProps & {
    ecrUri: string;
    mountS3DebUrl: string;
    securityGroups: ISecurityGroup[];
    vpc: Vpc;
};

export class DockerImageBuilder extends Construct {
    readonly dockerImageBuilderFn: Function;

    constructor (scope: Construct, id: string, props: DockerImageBuilderProps) {
        super(scope, id);

        const stackName = Stack.of(scope).stackName;

        const { config } = props;

        const ec2DockerBucket = new Bucket(this, createCdkId([stackName, 'docker-image-builder-ec2-bucket']));
        const ecsModelPath = path.join(HERE, '..', 'serve', 'ecs-model');
        new BucketDeployment(this, createCdkId([stackName, 'docker-image-builder-ec2-dplmnt']), {
            sources: [Source.asset(ecsModelPath)],
            destinationBucket: ec2DockerBucket,
            ...(config.roles &&
              {
                  role: Role.fromRoleName(this, createCdkId([stackName, Roles.DOCKER_IMAGE_BUILDER_DEPLOYMENT_ROLE]), config.roles.DockerImageBuilderDeploymentRole),
              }),
        });

        const ec2InstanceRoleName = createCdkId([stackName, 'docker-image-builder-ec2-role']);
        const ec2InstanceProfileRole = config.roles ?
            Role.fromRoleName(this, ec2InstanceRoleName, config.roles.DockerImageBuilderEC2Role) :
            this.createEc2InstanceRole(stackName, ec2InstanceRoleName, ec2DockerBucket.bucketArn);


        const ec2BuilderRoleName = createCdkId([stackName, 'docker_image_builder_role']);
        const ec2BuilderRole = config.roles ?
            Role.fromRoleName(this, ec2BuilderRoleName, config.roles.DockerImageBuilderRole) :
            this.createEc2BuilderRole(stackName, ec2BuilderRoleName, ec2InstanceProfileRole.roleArn);

        const ec2InstanceProfileId = createCdkId([stackName, 'docker-image-builder-profile']);
        const ec2InstanceProfile = new InstanceProfile(this, ec2InstanceProfileId, {
            instanceProfileName: ec2InstanceProfileId,
            role: ec2InstanceProfileRole,
        });

        const lambdaPath = path.join(HERE, '..', '..', 'lambda');
        const functionId = createCdkId([stackName, 'docker-image-builder']);
        this.dockerImageBuilderFn = new Function(this, functionId, {
            deadLetterQueueEnabled: true,
            deadLetterQueue: new Queue(this, 'docker-image-builderDLQ', {
                queueName: 'docker-image-builderDLQ',
                enforceSSL: true,
            }),
            functionName: functionId,
            runtime: getDefaultRuntime(),
            handler: 'dockerimagebuilder.handler',
            code: Code.fromAsset(lambdaPath),
            timeout: Duration.minutes(1),
            memorySize: 1024,
            role: ec2BuilderRole,
            environment: {
                'LISA_DOCKER_BUCKET': ec2DockerBucket.bucketName,
                'LISA_ECR_URI': props.ecrUri,
                'LISA_INSTANCE_PROFILE': ec2InstanceProfile.instanceProfileArn,
                'LISA_MOUNTS3_DEB_URL': props.mountS3DebUrl,
                'LISA_IMAGEBUILDER_VOLUME_SIZE': String(config.imageBuilderVolumeSize),
                ...props.vpc.subnetSelection?.subnets && props.vpc.subnetSelection?.subnets[0].subnetId ? {'LISA_SUBNET_ID': props.vpc.subnetSelection?.subnets[0].subnetId} : {}
            },
            vpc: props.vpc.vpc,
            vpcSubnets: props.vpc.subnetSelection,
            securityGroups: props.securityGroups,
        });
    }

    /**
     * Create EC2 instance role
     * @param stackName - deployment stack name
     * @param roleName - role name
     * @param dockerBucketArn - bucket arn containing docker images
     * @returns new role
     */
    createEc2InstanceRole (stackName: string, roleName: string, dockerBucketArn: string): IRole {
        const role = new Role(this, roleName, {
            roleName,
            assumedBy: new ServicePrincipal('ec2.amazonaws.com'),
        });

        const ec2InstanceProfilePolicy = new Policy(this, createCdkId([stackName, 'docker-image-builder-ec2-policy']), {
            statements: [
                new PolicyStatement({
                    actions: [
                        's3:GetObject',
                    ],
                    resources: [`${dockerBucketArn}/*`],
                }),
                new PolicyStatement({
                    actions: [
                        's3:ListBucket',
                    ],
                    resources: [dockerBucketArn],
                }),
                new PolicyStatement({
                    actions: [
                        'ecr:GetAuthorizationToken',
                        'ecr:InitiateLayerUpload',
                        'ecr:UploadLayerPart',
                        'ecr:CompleteLayerUpload',
                        'ecr:PutImage',
                        'ecr:BatchCheckLayerAvailability',
                    ],
                    resources: ['*'],
                }),
            ],
        });

        role.attachInlinePolicy(ec2InstanceProfilePolicy);

        return role;
    }

    /**
     * Create EC2 builder role
     * @param stackName - deployment stack name
     * @param roleName - role name
     * @param ec2InstanceRoleArn - EC2 Instance role arn
     * @returns new role
     */
    createEc2BuilderRole (stackName: string, roleName: string, ec2InstanceRoleArn: string): IRole {
        const role = new Role(this, roleName, {
            roleName,
            assumedBy: new ServicePrincipal('lambda.amazonaws.com'),
        });

        const assumeCdkPolicy = new Policy(this, createCdkId([stackName, 'docker-image-builder-policy']), {
            statements: [
                new PolicyStatement({
                    actions: [
                        'ec2:RunInstances',
                        'ec2:CreateTags',
                        'ec2:CreateNetworkInterface',
                        'ec2:DescribeNetworkInterfaces',
                        'ec2:DescribeSubnets',
                        'ec2:DeleteNetworkInterface',
                        'ec2:AssignPrivateIpAddresses',
                        'ec2:UnassignPrivateIpAddresses'
                    ],
                    resources: ['*'],
                }),
                new PolicyStatement({
                    actions: ['iam:PassRole'],
                    resources: [ec2InstanceRoleArn],
                }),
                new PolicyStatement({
                    actions: ['ssm:GetParameter'],
                    resources: ['arn:*:ssm:*::parameter/aws/service/*'],
                }),
            ],
        });

        role.attachInlinePolicy(assumeCdkPolicy);
        role.addManagedPolicy(ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'));
        role.addManagedPolicy(ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaVPCAccessExecutionRole'));

        return role;
    }

}

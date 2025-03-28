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
import { DockerImageCode, DockerImageFunction, IFunction } from 'aws-cdk-lib/aws-lambda';
import {
    Effect,
    IRole,
    ManagedPolicy,
    PolicyDocument,
    PolicyStatement,
    Role,
    ServicePrincipal,
} from 'aws-cdk-lib/aws-iam';
import { Duration, Size, Stack } from 'aws-cdk-lib';

import { createCdkId } from '../core/utils';
import { BaseProps, Config } from '../schema';
import { Vpc } from '../networking/vpc';
import * as path from 'path';
import { EcrReplicatorConstruct } from '../core/ecrReplicatorConstruct';

const HERE = path.resolve(__dirname);

export type ECSModelDeployerProps = {
    securityGroupId: string;
    config: Config;
    vpc: Vpc;
} & BaseProps;

export class ECSModelDeployer extends Construct {
    readonly ecsModelDeployerFn: IFunction;

    constructor (scope: Construct, id: string, props: ECSModelDeployerProps) {
        super(scope, id);
        const stackName = Stack.of(scope).stackName;
        const { config } = props;

        const role = config.roles ?
            Role.fromRoleName(this, createCdkId([stackName, 'ecs-model-deployer-role']), config.roles.ECSModelDeployerRole) :
            this.createRole(stackName);

        const stripped_config = {
            'appName': props.config.appName,
            'deploymentName': props.config.deploymentName,
            'deploymentPrefix': props.config.deploymentPrefix,
            'region': props.config.region,
            'deploymentStage': props.config.deploymentStage,
            'removalPolicy': props.config.removalPolicy,
            's3BucketModels': props.config.s3BucketModels,
            'mountS3DebUrl': props.config.mountS3DebUrl,
            'permissionsBoundaryAspect': props.config.permissionsBoundaryAspect,
            'subnets': props.config.subnets,
            'taskRole': props.config.roles?.ECSModelTaskRole,
            'certificateAuthorityBundle': props.config.certificateAuthorityBundle,
            'pypiConfig': props.config.pypiConfig,
            'nvmeContainerMountPath': props.config.nvmeContainerMountPath,
            'nvmeHostMountPath': props.config.nvmeHostMountPath,
            'condaUrl': props.config.condaUrl
        };

        const ecsModelDeployerPath = config.ecsModelDeployerPath || path.join(HERE, '..', '..', 'ecs_model_deployer');
        const functionId = createCdkId([stackName, 'ecs_model_deployer']);
        if (config.tagContainers) {
            new EcrReplicatorConstruct(this, 'LisaEcsModelDeployer', {
                path: ecsModelDeployerPath,
                buildArgs: { BASE_IMAGE: config.nodejsImage }
            });
        }
        this.ecsModelDeployerFn = new DockerImageFunction(this, functionId, {
            functionName: functionId,
            code: DockerImageCode.fromImageAsset(ecsModelDeployerPath, {
                buildArgs: {
                    BASE_IMAGE: config.nodejsImage
                }
            }),
            timeout: Duration.minutes(10),
            ephemeralStorageSize: Size.mebibytes(2048),
            memorySize: 1024,
            role,
            environment: {
                'LISA_VPC_ID': props.vpc.vpc.vpcId,
                'LISA_SECURITY_GROUP_ID': props.securityGroupId,
                'LISA_CONFIG': JSON.stringify(stripped_config),
            },
            vpcSubnets: props.vpc.subnetSelection,
            vpc: props.vpc.vpc,
            securityGroups: [props.vpc.securityGroups.lambdaSg],
        });
    }


    /**
     * Create ECS Model Deployer role
     * @param stackName - deployment stack name
     * @returns new role
     */
    createRole (stackName: string): IRole {
        return new Role(this, createCdkId([stackName, 'ecs-model-deployer-role']), {
            assumedBy: new ServicePrincipal('lambda.amazonaws.com'),
            managedPolicies: [
                ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaVPCAccessExecutionRole'),
            ],
            inlinePolicies: {
                lambdaPermissions: new PolicyDocument({
                    statements: [
                        new PolicyStatement({
                            actions: ['sts:AssumeRole'],
                            resources: ['arn:*:iam::*:role/cdk-*'],
                        }),
                        new PolicyStatement({
                            effect: Effect.ALLOW,
                            actions: [
                                'ec2:CreateNetworkInterface',
                                'ec2:DescribeNetworkInterfaces',
                                'ec2:DescribeSubnets',
                                'ec2:DeleteNetworkInterface',
                                'ec2:AssignPrivateIpAddresses',
                                'ec2:UnassignPrivateIpAddresses',
                            ],
                            resources: ['*'],
                        }),
                    ],
                }),

            },
        });
    }
}

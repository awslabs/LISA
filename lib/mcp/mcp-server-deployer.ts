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
import { IFunction } from 'aws-cdk-lib/aws-lambda';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as ssm from 'aws-cdk-lib/aws-ssm';
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
import { CodeFactory, MCP_SERVER_DEPLOYER_DIST_PATH } from '../util';
import { getNodeRuntime } from '../api-base/utils';

export type McpServerDeployerProps = {
    securityGroupId: string;
    config: Config;
    vpc: Vpc;
    restApiId: string;
    rootResourceId: string;
    hostingBucketArn: string;
    mcpResourceId: string;
    authorizerId?: string;
} & BaseProps;

export class McpServerDeployer extends Construct {
    readonly mcpServerDeployerFn: IFunction;

    constructor (scope: Construct, id: string, props: McpServerDeployerProps) {
        super(scope, id);
        const stackName = Stack.of(scope).stackName;
        const { config } = props;

        const role = config.roles ?
            Role.fromRoleName(this, createCdkId([stackName, 'ecs-model-deployer-role']), config.roles.McpServerDeployerRole) :
            this.createRole(stackName);

        const stripped_config = {
            'appName': props.config.appName,
            'deploymentName': props.config.deploymentName,
            'deploymentPrefix': props.config.deploymentPrefix,
            'region': props.config.region,
            'deploymentStage': props.config.deploymentStage,
            'removalPolicy': props.config.removalPolicy,
            'subnets': props.config.subnets,
            'taskRole': props.config.roles?.ECSModelTaskRole,
            'certificateAuthorityBundle': props.config.certificateAuthorityBundle,
            'pypiConfig': props.config.pypiConfig,
        };

        // Get CDK layer for deployer Lambda
        const cdkLambdaLayer = lambda.LayerVersion.fromLayerVersionArn(
            this,
            'cdk-lambda-layer',
            ssm.StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/layerVersion/cdk`),
        );

        const functionId = createCdkId([stackName, 'mcp_server_deployer', 'Func']);
        const mcpServerDeployerPath = config.mcpServerDeployerPath || MCP_SERVER_DEPLOYER_DIST_PATH;
        this.mcpServerDeployerFn = new lambda.Function(this, functionId, {
            functionName: functionId,
            code: CodeFactory.createCode(mcpServerDeployerPath),
            timeout: Duration.minutes(10),
            ephemeralStorageSize: Size.mebibytes(2048),
            runtime: getNodeRuntime(),
            handler: 'index.handler',
            memorySize: 1024,
            role,
            layers: [cdkLambdaLayer],
            environment: {
                'LISA_VPC_ID': props.vpc.vpc.vpcId,
                'LISA_SECURITY_GROUP_ID': props.securityGroupId,
                'LISA_CONFIG': JSON.stringify(stripped_config),
                'LISA_REST_API_ID': props.restApiId,
                'LISA_ROOT_RESOURCE_ID': props.rootResourceId,
                'LISA_HOSTING_BUCKET_ARN': props.hostingBucketArn,
                'LISA_MCP_RESOURCE_ID': props.mcpResourceId,
                ...(props.authorizerId && { 'LISA_AUTHORIZER_ID': props.authorizerId }),
            },
            vpcSubnets: props.vpc.subnetSelection,
            vpc: props.vpc.vpc,
            securityGroups: [props.vpc.securityGroups.lambdaSg],
        });
    }


    /**
     * Create MCP Server Deployer role
     * @param stackName - deployment stack name
     * @returns new role
     */
    createRole (stackName: string): IRole {
        return new Role(this, createCdkId([stackName, 'mcp-server-deployer-role']), {
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

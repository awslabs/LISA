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
import { StackProps, Duration, Size, CfnOutput } from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';
import { createCdkId, pickFields } from '../../core/utils';
import { BaseProps } from '../../schema';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import { Vpc } from '../../networking/vpc';
import { CreateStoreStateMachine } from './state_machine/create-store';
import { DeleteStoreStateMachine } from './state_machine/delete-store';
import { Roles } from '../../core/iam/roles';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import { ILayerVersion, Runtime } from 'aws-cdk-lib/aws-lambda';
import { CodeFactory, VECTOR_STORE_DEPLOYER_DIST_PATH } from '../../util';
import { NodejsFunction } from 'aws-cdk-lib/aws-lambda-nodejs';

export type VectorStoreCreatorStackProps = StackProps & BaseProps & {
    ragVectorStoreTable: CfnOutput;
    vpc: Vpc;
    baseEnvironment: Record<string, string>
    layers: ILayerVersion[],
};

// Main stack that contains the Lambda function
export class VectorStoreCreatorStack extends Construct {
    readonly vectorStoreCreatorFn: lambda.IFunction;

    constructor (scope: Construct, id: string, props: VectorStoreCreatorStackProps) {
        super(scope, id);

        const { baseEnvironment, config, layers, ragVectorStoreTable, vpc } = props;

        const vectorStoreTable = dynamodb.Table.fromTableArn(this, createCdkId([config.deploymentPrefix, 'RagVectorStoreTable']), ragVectorStoreTable.value);

        // Create Lambda role with permissions to create CloudFormation stacks
        const cdkRole = new iam.Role(this, `${config.deploymentPrefix}/roles/${createCdkId([config.deploymentName, Roles.VECTOR_STORE_CREATOR_ROLE])}`, {
            assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
            managedPolicies: [
                iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
                iam.ManagedPolicy.fromAwsManagedPolicyName('AWSCloudFormationFullAccess'),
            ],
        });

        cdkRole.addToPolicy(new iam.PolicyStatement({
            actions: [
                's3:*',
                'ec2:*',
                'rds:*',
                'opensearch:*',
                'ssm:*',
            ],
            resources: ['*']
        }));// Additional CloudFormation permissions that might be needed

        const lambdaExecutionRole = iam.Role.fromRoleArn(
            this,
            `${Roles.RAG_LAMBDA_EXECUTION_ROLE}-VectorStore`,
            ssm.StringParameter.valueForStringParameter(
                this,
                `${config.deploymentPrefix}/roles/${createCdkId([config.deploymentName, Roles.RAG_LAMBDA_EXECUTION_ROLE])}`,
            ),
        );

        // IAM: service-linked role creation for required services
        cdkRole.addToPolicy(new iam.PolicyStatement({
            actions: ['iam:CreateServiceLinkedRole'],
            resources: ['*'],
            conditions: {
                StringEquals: {
                    'iam:AWSServiceName': ['opensearchservice.amazonaws.com', 'rds.amazonaws.com']
                }
            }
        }));

        // IAM: manage roles created within the dynamic stacks and allow passing to services
        cdkRole.addToPolicy(new iam.PolicyStatement({
            actions: [
                'iam:CreateRole',
                'iam:DeleteRole',
                'iam:AttachRolePolicy',
                'iam:DetachRolePolicy',
                'iam:PutRolePolicy',
                'iam:DeleteRolePolicy',
                'iam:TagRole',
                'iam:UntagRole',
                'iam:GetRole',
                'iam:GetRolePolicy',
                'iam:ListRolePolicies',
                'iam:ListAttachedRolePolicies',
                'iam:GetRolePolicy',
                'iam:ListRoleTags',
                'iam:UpdateAssumeRolePolicy'
            ],
            resources: ['*'],
        }));

        // IAM: assume CDK bootstrap roles for deployment
        cdkRole.addToPolicy(new iam.PolicyStatement({
            actions: ['iam:AssumeRole'],
            resources: [
                `arn:${config.partition}:iam::${config.accountNumber}:role/cdk-*-deploy-role-${config.accountNumber}-${config.region}`,
                `arn:${config.partition}:iam::${config.accountNumber}:role/cdk-hnb659fds-deploy-role-${config.accountNumber}-${config.region}`
            ],
        }));

        // IAM: additional permissions for CDK bootstrap operations
        cdkRole.addToPolicy(new iam.PolicyStatement({
            actions: [
                'iam:GetRole',
                'iam:ListRoles',
                'iam:ListRoleTags',
                'iam:GetRolePolicy',
                'iam:ListRolePolicies',
                'iam:ListAttachedRolePolicies'
            ],
            resources: [
                `arn:${config.partition}:iam::${config.accountNumber}:role/cdk-*`,
                `arn:${config.partition}:iam::${config.accountNumber}:role/cdk-*-deploy-role-*`,
                `arn:${config.partition}:iam::${config.accountNumber}:role/cdk-*-file-publishing-role-*`,
                `arn:${config.partition}:iam::${config.accountNumber}:role/cdk-*-image-publishing-role-*`,
                `arn:${config.partition}:iam::${config.accountNumber}:role/cdk-*-lookup-role-*`
            ],
        }));
        cdkRole.addToPolicy(new iam.PolicyStatement({
            actions: ['iam:PassRole'],
            resources: ['*'],
            conditions: {
                StringEquals: {
                    'iam:PassedToService': [
                        'lambda.amazonaws.com',
                        'events.amazonaws.com'
                    ]
                }
            }
        }));

        const stateMachineRole = new iam.Role(this, createCdkId([config.deploymentName, config.deploymentStage, 'StateMachineRole']), {
            assumedBy: new iam.ServicePrincipal('states.amazonaws.com'),
        });
        vectorStoreTable.grantReadWriteData(stateMachineRole);

        // create a stripped down config to store only the fields we care about
        const strippedConfig = {
            ...pickFields(props.config, [
                'accountNumber',
                'appName',
                'deploymentName',
                'deploymentStage',
                'deploymentPrefix',
                'partition',
                'region',
                'removalPolicy',
                'subnets',
                'profile',
                'vpcId',
            ]),
            ...(vpc.vpc.vpcId && { vpcId: vpc.vpc.vpcId })
        };

        const functionId = createCdkId([props.config.deploymentName, props.config.deploymentStage, 'vector_store_deployer', 'Fn']);
        const vectorStoreDeployer = config.vectorStoreDeployerPath || VECTOR_STORE_DEPLOYER_DIST_PATH;
        this.vectorStoreCreatorFn = new NodejsFunction(this, functionId, {
            functionName: functionId,
            code: CodeFactory.createCode(vectorStoreDeployer),
            timeout: Duration.minutes(15),
            ephemeralStorageSize: Size.mebibytes(2048),
            runtime: Runtime.NODEJS_18_X,
            handler: 'index.handler',
            memorySize: 1024,
            role: cdkRole,
            environment: {
                'LISA_CONFIG': JSON.stringify(strippedConfig),
                'LISA_RAG_VECTOR_STORE_TABLE': vectorStoreTable.tableName
            },
            vpcSubnets: vpc.subnetSelection,
            vpc: props.vpc.vpc,
            securityGroups: [props.vpc.securityGroups.lambdaSg],
        });

        // Allow the state machine to invoke the deployer Lambda
        this.vectorStoreCreatorFn.grantInvoke(stateMachineRole);

        // Minimal policies for state machine role
        stateMachineRole.addToPolicy(new iam.PolicyStatement({
            actions: ['lambda:InvokeFunction'],
            resources: [this.vectorStoreCreatorFn.functionArn],
        }));
        stateMachineRole.addToPolicy(new iam.PolicyStatement({
            actions: ['cloudformation:DescribeStacks', 'cloudformation:DeleteStack'],
            resources: ['*'],
        }));
        stateMachineRole.addToPolicy(new iam.PolicyStatement({
            actions: ['dynamodb:PutItem', 'dynamodb:UpdateItem', 'dynamodb:GetItem', 'dynamodb:DeleteItem'],
            resources: [vectorStoreTable.tableArn],
        }));

        new CreateStoreStateMachine(this, 'CreateVectorStoreStateMachine', {
            config: props.config,
            executionRole: lambdaExecutionRole,
            parameterName: baseEnvironment['LISA_RAG_CREATE_STATE_MACHINE_ARN_PARAMETER'],
            role: stateMachineRole,
            vectorStoreConfigTable: vectorStoreTable,
            vectorStoreDeployerFnArn: this.vectorStoreCreatorFn.functionArn,
            vpc: props.vpc,
        });

        new DeleteStoreStateMachine(this, 'DeleteStoreStateMachine', {
            config: props.config,
            executionRole: lambdaExecutionRole,
            lambdaLayers: layers,
            parameterName: baseEnvironment['LISA_RAG_DELETE_STATE_MACHINE_ARN_PARAMETER'],
            role: stateMachineRole,
            ragVectorStoreTable: vectorStoreTable,
            vectorStoreDeployerFnArn: this.vectorStoreCreatorFn.functionArn,
            vpc: props.vpc,
            environment: baseEnvironment
        });
    }
}

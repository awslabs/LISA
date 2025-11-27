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
import { ILayerVersion } from 'aws-cdk-lib/aws-lambda';
import { CodeFactory, LAMBDA_PATH, VECTOR_STORE_DEPLOYER_DIST_PATH } from '../../util';
import { getNodeRuntime, getPythonRuntime } from '../../api-base/utils';

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
                'iam:ListRoleTags',
                'iam:UpdateAssumeRolePolicy',
                'iam:ListRoles'
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


        cdkRole.addToPolicy(new iam.PolicyStatement({
            actions: ['iam:PassRole'],
            resources: ['*'],
            conditions: {
                StringEquals: {
                    'iam:PassedToService': [
                        'cloudformation.amazonaws.com',
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

        // Get CDK layer for deployer Lambda
        const cdkLambdaLayer = lambda.LayerVersion.fromLayerVersionArn(
            this,
            'cdk-lambda-layer',
            ssm.StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/layerVersion/cdk`),
        );

        const functionId = createCdkId([props.config.deploymentName, props.config.deploymentStage, 'vector_store_deployer', 'Func']);
        const vectorStoreDeployer = config.vectorStoreDeployerPath || VECTOR_STORE_DEPLOYER_DIST_PATH;
        this.vectorStoreCreatorFn = new lambda.Function(this, functionId, {
            functionName: functionId,
            code: CodeFactory.createCode(vectorStoreDeployer),
            timeout: Duration.minutes(15),
            ephemeralStorageSize: Size.mebibytes(2048),
            runtime: getNodeRuntime(),
            handler: 'index.handler',
            memorySize: 1024,
            role: cdkRole,
            layers: [cdkLambdaLayer],
            environment: {
                'LISA_CONFIG': JSON.stringify(strippedConfig),
                'LISA_RAG_VECTOR_STORE_TABLE': vectorStoreTable.tableName
            },
            vpcSubnets: vpc.subnetSelection,
            vpc: props.vpc.vpc,
            securityGroups: [props.vpc.securityGroups.lambdaSg],
        });

        // Create Lambda for Bedrock collection creation
        const createBedrockCollectionFn = new lambda.Function(this, 'CreateBedrockCollectionFn', {
            functionName: createCdkId([config.deploymentName, config.deploymentStage, 'create_bedrock_collection']),
            runtime: getPythonRuntime(),
            handler: 'repository.lambda_functions.create_bedrock_collection',
            code: lambda.Code.fromAsset(config.lambdaPath || LAMBDA_PATH),
            timeout: Duration.minutes(5),
            memorySize: 512,
            role: lambdaExecutionRole,
            environment: baseEnvironment,
            vpc: vpc.vpc,
            vpcSubnets: vpc.subnetSelection,
            securityGroups: [vpc.securityGroups.lambdaSg],
            layers: layers,
        });

        // Grant permissions
        vectorStoreTable.grantReadWriteData(createBedrockCollectionFn);

        // Allow the state machine to invoke the deployer Lambda
        this.vectorStoreCreatorFn.grantInvoke(stateMachineRole);
        createBedrockCollectionFn.grantInvoke(stateMachineRole);

        // Minimal policies for state machine role
        stateMachineRole.addToPolicy(new iam.PolicyStatement({
            actions: ['lambda:InvokeFunction'],
            resources: [this.vectorStoreCreatorFn.functionArn, createBedrockCollectionFn.functionArn],
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
            createBedrockCollectionFnArn: createBedrockCollectionFn.functionArn,
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

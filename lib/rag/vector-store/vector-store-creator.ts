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

export type VectorStoreCreatorStackProps = StackProps & BaseProps & {
    ragVectorStoreTable: CfnOutput,
    vpc: Vpc;
    baseEnvironment: Record<string, string>
    layers: ILayerVersion[],
};

// Main stack that contains the Lambda function
export class VectorStoreCreatorStack extends Construct {
    readonly vectorStoreCreatorFn: lambda.IFunction;
    readonly ragRepositoryConfigTable: dynamodb.ITable;

    constructor (scope: Construct, id: string, props: VectorStoreCreatorStackProps) {
        super(scope, id);

        const { baseEnvironment, config, ragVectorStoreTable, vpc, layers } = props;

        const vectorStoreTable = dynamodb.Table.fromTableArn(this, createCdkId([config.deploymentPrefix, 'RagVectorStoreTable']), ragVectorStoreTable.value);

        // Create Lambda role with permissions to create CloudFormation stacks
        const cdkRole = new iam.Role(this, `${config.deploymentPrefix}/roles/${createCdkId([config.deploymentName, Roles.VECTOR_STORE_CREATOR_ROLE])}`, {
            assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
            managedPolicies: [
                iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
                iam.ManagedPolicy.fromAwsManagedPolicyName('AWSCloudFormationFullAccess'),
            ],
        });

        const lambdaExecutionRole = iam.Role.fromRoleArn(
            this,
            Roles.RAG_LAMBDA_EXECUTION_ROLE,
            ssm.StringParameter.valueForStringParameter(
                this,
                `${config.deploymentPrefix}/roles/${createCdkId([config.deploymentName, Roles.RAG_LAMBDA_EXECUTION_ROLE])}`,
            ),
        );

        // Add permissions to create resources that will be in the dynamic stacks
        cdkRole.addToPolicy(new iam.PolicyStatement({
            actions: [
                's3:*',
                'ec2:*',
                'rds:*',
                'opensearch:*',
                'ssm:*',
                'iam:*'
            ],
            resources: ['*'],
        }));

        const stateMachineRole = new iam.Role(this, createCdkId([config.deploymentName, config.deploymentStage, 'StateMachineRole']), {
            assumedBy: new iam.ServicePrincipal('states.amazonaws.com'),
            managedPolicies: [
                iam.ManagedPolicy.fromAwsManagedPolicyName('AWSStepFunctionsFullAccess'),
                iam.ManagedPolicy.fromAwsManagedPolicyName('AWSCloudFormationFullAccess'),
            ],
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
            ...(vpc.vpc.vpcId && {vpcId: vpc.vpc.vpcId})
        };

        const functionId = createCdkId([props.config.deploymentName, props.config.deploymentStage, 'vector_store_deployer']);
        this.vectorStoreCreatorFn = new lambda.DockerImageFunction(this, functionId, {
            functionName: functionId,
            code: lambda.DockerImageCode.fromImageAsset('./vector_store_deployer/'),
            timeout: Duration.minutes(15),
            ephemeralStorageSize: Size.mebibytes(2048),
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

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
import { BaseProps } from '../../../schema';
import { ITable } from 'aws-cdk-lib/aws-dynamodb';
import { ILayerVersion } from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as sfn from 'aws-cdk-lib/aws-stepfunctions';
import * as tasks from 'aws-cdk-lib/aws-stepfunctions-tasks';
import { Duration } from 'aws-cdk-lib';
import { Vpc } from '../../../networking/vpc';
import { IStateMachine } from 'aws-cdk-lib/aws-stepfunctions';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { createCdkId } from '../../../core/utils';

type DeleteStoreStateMachineProps = BaseProps & {
    ragVectorStoreTable: ITable,
    lambdaLayers: ILayerVersion[];
    vectorStoreDeployerFnArn: string;
    vpc: Vpc,
    // securityGroups: ISecurityGroup[];
    role?: iam.IRole,
    executionRole: iam.IRole;
    parameterName: string
};


export class DeleteStoreStateMachine extends Construct {
    readonly stateMachine: IStateMachine;

    constructor (scope: Construct, id: string, props: DeleteStoreStateMachineProps) {
        super(scope, id);

        const {
            config,
            executionRole,
            // lambdaLayers,
            // securityGroups,
            parameterName,
            role,
            ragVectorStoreTable,
        } = props;
        

        // Task to delete a CloudFormation stack
        const deleteStack = new tasks.CallAwsService(this, 'DeleteStack', {
            service: 'cloudformation',
            action: 'deleteStack',
            parameters: {
                StackName: sfn.JsonPath.stringAt('$.stackName'),
            },
            iamResources: ['*'],
            resultPath: '$.deleteResult',
        });

        // Task to delete an entry in DynamoDB with the given repositoryId
        const deleteDynamoDbEntry = new tasks.DynamoDeleteItem(this, 'DeleteDynamoDbEntry', {
            table: ragVectorStoreTable,
            key: {
                repositoryId: tasks.DynamoAttributeValue.fromString(sfn.JsonPath.stringAt('$.repositoryId'))
            },
            resultPath: '$.deleteDynamoDbResult',
        });

        // Task to check the deployment status using a Lambda function
        const checkStackStatus = new tasks.CallAwsService(this, 'Check Stack Status', {
            service: 'cloudformation',
            action: 'describeStacks',
            parameters: {
                StackName: sfn.JsonPath.stringAt('$.stackName'),
            },
            iamResources: ['*'],
            resultSelector: {
                'stackName.$': '$.Stacks[0].StackName',
                'status.$': '$.Stacks[0].StackStatus',
                // 'statusReason.$': '$.Stacks[0].StackStatusReason'
            },
            resultPath: '$.checkResult',
        });

        // Wait task to pause the execution for a specified duration
        const wait = new sfn.Wait(this, 'Wait', {
            time: sfn.WaitTime.duration(Duration.seconds(30)),
        });

        // Task to update the status of the vector store entry to 'FAILED' on deployment failure
        const updateFailureStatus = new tasks.DynamoUpdateItem(this, 'UpdateFailureStatus', {
            table: ragVectorStoreTable,
            key: { id: tasks.DynamoAttributeValue.fromString(sfn.JsonPath.stringAt('$.repositoryId')) },
            updateExpression: 'SET #status = :status, #error = :error',
            expressionAttributeNames: { '#status': 'status', '#error': 'error' },
            expressionAttributeValues: {
                ':status': tasks.DynamoAttributeValue.fromString('$.checkResult.status'),
                // ':error': tasks.DynamoAttributeValue.fromString(sfn.JsonPath.stringAt('$.checkResult.statusReason')),
            },
        });

        // Define the sequence of tasks and conditions in the state machine
        const definition = deleteStack
            .next(checkStackStatus.addCatch(deleteDynamoDbEntry, {
                // errors: ['CloudFormation.CloudFormationException'],
                resultPath: '$.error'
            }))
            .next(
                new sfn.Choice(this, 'DeletionSuccessful?')
                    .when(sfn.Condition.stringEquals('$.checkResult.status', 'DELETE_FAILED'), updateFailureStatus)
                    .otherwise(wait.next(checkStackStatus))
            );

        // Create a new state machine using the definition and roles specified
        this.stateMachine = new sfn.StateMachine(this, 'DeleteStoreStateMachine', {
            definition,
            role,
            stateMachineType: sfn.StateMachineType.STANDARD,
            removalPolicy: config.removalPolicy
        });
        new StringParameter(this, createCdkId([config.deploymentPrefix, 'VectorStoreCreator', 'Delete']), {
            parameterName,
            stringValue: this.stateMachine.stateMachineArn
        });

        executionRole.attachInlinePolicy(new iam.Policy(this, 'StateMachineExecutePolicy', {
            policyName: 'RagVectorStoreStateMacineDeleteExec',
            statements: [
                new iam.PolicyStatement({
                    effect: iam.Effect.ALLOW,
                    actions: ['states:StartExecution'],
                    resources: [this.stateMachine.stateMachineArn]
                })
            ]
        }));
    }
}
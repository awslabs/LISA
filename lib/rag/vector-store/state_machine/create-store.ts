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
import { BaseProps, VectorStoreStatus,  } from '../../../schema';
import * as ddb from 'aws-cdk-lib/aws-dynamodb';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as sfn from 'aws-cdk-lib/aws-stepfunctions';
import * as tasks from 'aws-cdk-lib/aws-stepfunctions-tasks';
import { Duration } from 'aws-cdk-lib';
import { Vpc } from '../../../networking/vpc';
import * as ssm from 'aws-cdk-lib/aws-ssm';

type CreateStoreStateMachineProps = BaseProps & {
    createBedrockCollectionFnArn: string;
    executionRole: iam.IRole;
    parameterName: string,
    role?: iam.IRole,
    vectorStoreConfigTable: ddb.ITable,
    vectorStoreDeployerFnArn: string;
    vpc: Vpc,
};


export class CreateStoreStateMachine extends Construct {
    readonly stateMachine: sfn.IStateMachine;

    constructor (scope: Construct, id: string, props: CreateStoreStateMachineProps) {
        super(scope, id);

        const { config, createBedrockCollectionFnArn, executionRole, parameterName, role, vectorStoreConfigTable, vectorStoreDeployerFnArn } = props;

        // Get reference to the Bedrock collection creation Lambda
        const createBedrockCollectionFn = lambda.Function.fromFunctionArn(
            this,
            'CreateBedrockCollectionFunction',
            createBedrockCollectionFnArn
        );

        // Task to create an entry in DynamoDB for the vector store
        const createVectorStoreEntry = new tasks.DynamoPutItem(this, 'CreateVectorStoreEntry', {
            table: vectorStoreConfigTable,
            item: {
                repositoryId: tasks.DynamoAttributeValue.fromString(sfn.JsonPath.stringAt('$.body.ragConfig.repositoryId')),
                status: tasks.DynamoAttributeValue.fromString(VectorStoreStatus.CREATE_IN_PROGRESS),
                config: tasks.DynamoAttributeValue.mapFromJsonPath('$.config')
            },
            resultPath: '$.dynamoResult',
        });

        // Task to invoke a Lambda function to deploy the vector store
        const deployVectorStore = new tasks.LambdaInvoke(this, 'DeployVectorStore', {
            lambdaFunction: lambda.Function.fromFunctionArn(this, 'VectorStoreDeployer', vectorStoreDeployerFnArn),
            payload: sfn.TaskInput.fromObject({
                ragConfig: sfn.JsonPath.objectAt('$.body.ragConfig'),
            }),
            resultSelector: {
                'stackName.$': '$.Payload.stackName',
            },
            resultPath: '$.deployResult',
        });

        // Task to check the deployment status using a Lambda function
        const checkDeploymentStatus = new tasks.CallAwsService(this, 'CheckDeploymentStatus', {
            service: 'cloudformation',
            action: 'describeStacks',
            parameters: {
                StackName: sfn.JsonPath.stringAt('$.deployResult.stackName'),
            },
            iamResources: ['*'],
            resultSelector: {
                'stackName.$': '$.Stacks[0].StackName',
                'status.$': '$.Stacks[0].StackStatus'
            },
            resultPath: '$.deployResult',
        });

        // Wait task to pause the execution for a specified duration
        const wait = new sfn.Wait(this, 'Wait', {
            time: sfn.WaitTime.duration(Duration.seconds(30)),
        });

        // Task to create default collection for Bedrock KB
        const createDefaultCollectionTask = new tasks.LambdaInvoke(this, 'CreateDefaultCollection', {
            lambdaFunction: createBedrockCollectionFn,
            payload: sfn.TaskInput.fromObject({
                ragConfig: sfn.JsonPath.objectAt('$.body.ragConfig'),
            }),
            resultPath: '$.collectionResult',
        });

        // Task to update the status of the vector store entry to 'COMPLETED' on successful deployment
        // For Bedrock KB without pipelines, stackName may be null
        const updateSuccessStatus = new tasks.DynamoUpdateItem(this, 'UpdateSuccessStatus', {
            table: vectorStoreConfigTable,
            key: { repositoryId: tasks.DynamoAttributeValue.fromString(sfn.JsonPath.stringAt('$.body.ragConfig.repositoryId')) },
            updateExpression: 'SET #status = :status, #stackName = :stackName',
            expressionAttributeNames: { '#status': 'status', '#stackName': 'stackName' },
            expressionAttributeValues: {
                ':status': tasks.DynamoAttributeValue.fromString(VectorStoreStatus.CREATE_COMPLETE),
                ':stackName': tasks.DynamoAttributeValue.fromString(sfn.JsonPath.stringAt('$.deployResult.stackName'))
            },
        });

        // Task to update the status of the vector store entry to 'FAILED' on deployment failure
        const updateFailureStatus = new tasks.DynamoUpdateItem(this, 'UpdateFailureStatus', {
            table: vectorStoreConfigTable,
            key: { repositoryId: tasks.DynamoAttributeValue.fromString(sfn.JsonPath.stringAt('$.body.ragConfig.repositoryId')) },
            updateExpression: 'SET #status = :status',
            expressionAttributeNames: { '#status': 'status' },
            expressionAttributeValues: {
                ':status': tasks.DynamoAttributeValue.fromString(VectorStoreStatus.CREATE_FAILED)
            },
        });

        // Fail state to mark the state machine execution as failed
        const failExecution = new sfn.Fail(this, 'FailExecution', {
            cause: 'Vector store deployment failed',
            error: 'DeploymentFailed',
        });

        // Chain failure status update to fail state
        updateFailureStatus.next(failExecution);

        // Check if this is a Bedrock KB repository to create default collections
        const skipCollectionCreation = new sfn.Pass(this, 'SkipCollectionCreation');

        const checkIfBedrockKB = new sfn.Choice(this, 'IsBedrockKB?')
            .when(
                sfn.Condition.stringEquals('$.body.ragConfig.type', 'bedrock_knowledge_base'),
                createDefaultCollectionTask
            )
            .otherwise(skipCollectionCreation);

        // Both paths converge to update success status
        createDefaultCollectionTask.next(updateSuccessStatus);
        skipCollectionCreation.next(updateSuccessStatus);

        // Define the sequence of tasks and conditions in the state machine
        const deploymentComplete = new sfn.Choice(this, 'DeploymentComplete?')
            .when(
                sfn.Condition.and(
                    sfn.Condition.isPresent('$.deployResult.status'),
                    sfn.Condition.or(
                        sfn.Condition.stringEquals('$.deployResult.status', VectorStoreStatus.CREATE_IN_PROGRESS),
                        sfn.Condition.stringEquals('$.deployResult.status', VectorStoreStatus.UPDATE_IN_PROGRESS),
                        sfn.Condition.stringEquals('$.deployResult.status', VectorStoreStatus.UPDATE_COMPLETE_CLEANUP_IN_PROGRESS),
                    ),
                ),
                wait.next(checkDeploymentStatus)
            )
            .when(
                sfn.Condition.and(
                    sfn.Condition.isPresent('$.deployResult.status'),
                    sfn.Condition.or(
                        sfn.Condition.stringEquals('$.deployResult.status', VectorStoreStatus.CREATE_COMPLETE),
                        sfn.Condition.stringEquals('$.deployResult.status', VectorStoreStatus.UPDATE_COMPLETE),
                    ),
                ),
                checkIfBedrockKB
            )
            .otherwise(updateFailureStatus);

        checkDeploymentStatus.next(deploymentComplete);

        const definition = createVectorStoreEntry
            .next(
                deployVectorStore.addCatch(updateFailureStatus, { resultPath: '$.error' })
                    .next(checkDeploymentStatus)
            );

        // Create a new state machine using the definition and roles specified
        this.stateMachine = new sfn.StateMachine(this, 'CreateStoreStateMachine', {
            definition,
            role,
            stateMachineType: sfn.StateMachineType.STANDARD,
            removalPolicy: config.removalPolicy
        });

        new ssm.StringParameter(this, 'CreateStoreStateMachineArn', {
            parameterName,
            stringValue: this.stateMachine.stateMachineArn,
        });

        executionRole.attachInlinePolicy(new iam.Policy(this, 'StateMachineExecutePolicy', {
            policyName: 'RagVectorStoreStateMacineCreateExec',
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

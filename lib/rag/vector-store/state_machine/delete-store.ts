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
import { ITable } from 'aws-cdk-lib/aws-dynamodb';
import { Code, Function, ILayerVersion } from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as sfn from 'aws-cdk-lib/aws-stepfunctions';
import { Choice, Condition, IStateMachine } from 'aws-cdk-lib/aws-stepfunctions';
import * as tasks from 'aws-cdk-lib/aws-stepfunctions-tasks';
import { LambdaInvoke } from 'aws-cdk-lib/aws-stepfunctions-tasks';
import { Duration } from 'aws-cdk-lib';
import { Vpc } from '../../../networking/vpc';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { createCdkId } from '../../../core/utils';
import { getDefaultRuntime } from '../../../api-base/utils';
import { LAMBDA_MEMORY, LAMBDA_TIMEOUT } from '../../state_machine/constants';
import { OUTPUT_PATH } from '../../../models/state-machine/constants';
import { LAMBDA_PATH } from '../../../util';

type DeleteStoreStateMachineProps = BaseProps & {
    ragVectorStoreTable: ITable,
    vectorStoreDeployerFnArn: string;
    lambdaLayers: ILayerVersion[];
    vpc: Vpc,
    role?: iam.IRole,
    executionRole: iam.IRole;
    parameterName: string,
    environment: {
        [key: string]: string;
    };
};


export class DeleteStoreStateMachine extends Construct {
    readonly stateMachine: IStateMachine;

    constructor (scope: Construct, id: string, props: DeleteStoreStateMachineProps) {
        super(scope, id);

        const {
            config,
            executionRole,
            lambdaLayers,
            parameterName,
            role,
            ragVectorStoreTable,
            vpc,
            environment,
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
            },
        });
        // Task to update the status of the vector store entry to 'COMPLETED' on successful deployment
        const updateDeleteStatus = new tasks.DynamoUpdateItem(this, 'UpdateDeleteStatus', {
            table: ragVectorStoreTable,
            key: { repositoryId: tasks.DynamoAttributeValue.fromString(sfn.JsonPath.stringAt('$.repositoryId')) },
            updateExpression: 'SET #status = :status',
            expressionAttributeNames: { '#status': 'status' },
            expressionAttributeValues: {
                ':status': tasks.DynamoAttributeValue.fromString(VectorStoreStatus.DELETE_IN_PROGRESS),
            },
            resultPath: '$.updateDynamoDbResult',
        });

        const handleCleanupBedrockKnowledgeBase = new Choice(this, 'BedrockKnowledgeBase')
            .when(sfn.Condition.and(sfn.Condition.stringEquals('$.ddbResult.Item.config.M.type.S', 'bedrock_knowledge_base'),
                sfn.Condition.isNull('$.stackName')), deleteDynamoDbEntry)
            .otherwise(deleteStack);

        const getRepoFromDdb = new tasks.DynamoGetItem(this, 'GetRepoFromDdb', {
            table: ragVectorStoreTable,
            key: { repositoryId: tasks.DynamoAttributeValue.fromString(sfn.JsonPath.stringAt('$.repositoryId')) },
            resultPath: '$.ddbResult',
        }).next(handleCleanupBedrockKnowledgeBase);

        const lambdaPath = config.lambdaPath || LAMBDA_PATH;

        const cleanupDocsFunc =  new Function(this, 'CleanupRepositoryDocsFunc', {
            runtime: getDefaultRuntime(),
            handler: 'repository.state_machine.cleanup_repo_docs.lambda_handler',
            code: Code.fromAsset(lambdaPath),
            timeout: LAMBDA_TIMEOUT,
            memorySize: LAMBDA_MEMORY,
            vpc: vpc.vpc,
            environment: environment,
            layers: lambdaLayers,
            role: executionRole,
        });

        const waitForCollectionDeletionsFunc = new Function(this, 'WaitForCollectionDeletionsFunc', {
            runtime: getDefaultRuntime(),
            handler: 'repository.state_machine.wait_for_collection_deletions.lambda_handler',
            code: Code.fromAsset(lambdaPath),
            timeout: Duration.seconds(30),
            memorySize: LAMBDA_MEMORY,
            vpc: vpc.vpc,
            environment: environment,
            layers: lambdaLayers,
            role: executionRole,
        });

        // Allow the Step Functions role to invoke the lambdas
        if (role) {
            cleanupDocsFunc.grantInvoke(role);
            waitForCollectionDeletionsFunc.grantInvoke(role);
        }

        const hasMoreDocs = new Choice(this, 'HasMoreDocs')
            .when(Condition.isNotNull('$.lastEvaluated'), new LambdaInvoke(this, 'CleanupRepositoryDocsRetry', {
                lambdaFunction: cleanupDocsFunc,
                payload: sfn.TaskInput.fromObject({
                    'repositoryId.$': '$.repositoryId',
                    'lastEvaluated.$': '$.lastEvaluated',
                    'stackName.$': '$.stackName'
                }),
                outputPath: OUTPUT_PATH,
            }))
            .otherwise(getRepoFromDdb);

        const cleanupDocs = new LambdaInvoke(this, 'CleanupRepositoryDocs', {
            lambdaFunction: cleanupDocsFunc,
            payload: sfn.TaskInput.fromObject({
                'repositoryId.$': '$.repositoryId',
                'stackName.$': '$.stackName',
            }),
            outputPath: OUTPUT_PATH,
        });

        // Wait for collection deletions to complete
        const waitForCollectionDeletions = new LambdaInvoke(this, 'WaitForCollectionDeletions', {
            lambdaFunction: waitForCollectionDeletionsFunc,
            payload: sfn.TaskInput.fromObject({
                'repositoryId.$': '$.repositoryId',
                'stackName.$': '$.stackName',
            }),
            outputPath: OUTPUT_PATH,
        });

        const waitForCollectionDeletionsRetry = new sfn.Wait(this, 'WaitForCollectionDeletionsRetry', {
            time: sfn.WaitTime.duration(Duration.seconds(10)),
        }).next(waitForCollectionDeletions);

        const checkCollectionDeletionsComplete = new Choice(this, 'CheckCollectionDeletionsComplete')
            .when(Condition.booleanEquals('$.allCollectionDeletionsComplete', true), cleanupDocs.next(hasMoreDocs))
            .otherwise(waitForCollectionDeletionsRetry);

        waitForCollectionDeletions.next(checkCollectionDeletionsComplete);

        const shouldSkipCleanup = new Choice(this, 'ShouldSkipCleanup')
            .when(Condition.and(Condition.isPresent('$.skipDocumentRemoval'), Condition.booleanEquals('$.skipDocumentRemoval', true)),
                handleCleanupBedrockKnowledgeBase)
            .otherwise(waitForCollectionDeletions);

        deleteStack.next(checkStackStatus.addCatch(deleteDynamoDbEntry, {
            resultPath: '$.error'
        }))
            .next(
                new sfn.Choice(this, 'DeletionSuccessful?')
                    .when(sfn.Condition.stringEquals('$.checkResult.status', VectorStoreStatus.DELETE_FAILED), updateFailureStatus)
                    .otherwise(wait.next(checkStackStatus))
            );
        // Define the sequence of tasks and conditions in the state machine
        const definition = updateDeleteStatus
            .next(shouldSkipCleanup);

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
            policyName: 'RagVectorStoreStateMachineDeleteExec',
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

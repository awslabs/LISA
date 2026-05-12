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
import { Duration, Stack } from 'aws-cdk-lib';
import { BaseProps } from '../../schema';
import { ILayerVersion } from 'aws-cdk-lib/aws-lambda';
import { Effect, PolicyStatement, Role, ServicePrincipal } from 'aws-cdk-lib/aws-iam';
import { Vpc } from '../../networking/vpc';
import { ITable } from 'aws-cdk-lib/aws-dynamodb';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { createCdkId } from '../../core/utils';
import { Roles } from '../../core/iam/roles';
import * as sfn from 'aws-cdk-lib/aws-stepfunctions';
import * as tasks from 'aws-cdk-lib/aws-stepfunctions-tasks';
import { LAMBDA_MEMORY, LAMBDA_TIMEOUT, OUTPUT_PATH } from './constants';
import { definePythonLambda } from '../../util';

export type PipelineStateMachineProps = BaseProps & {
    vpc: Vpc;
    layers: ILayerVersion[];
    collectionsTable: ITable;
    baseEnvironment: Record<string, string>;
};

/**
 * Pipeline State Machine for managing collection pipeline lifecycle.
 *
 * This construct creates a Step Functions state machine that orchestrates
 * the creation, update, and deletion of EventBridge rules for collection pipelines.
 */
export class PipelineStateMachine extends Construct {
    public readonly stateMachine: sfn.StateMachine;
    public readonly stateMachineArn: string;

    constructor (scope: Construct, id: string, props: PipelineStateMachineProps) {
        super(scope, id);

        const { config, vpc, layers, collectionsTable, baseEnvironment } = props;
        const stack = Stack.of(this);

        // Get the Lambda execution role from SSM parameter
        const lambdaExecutionRole = Role.fromRoleArn(
            this,
            createCdkId([Roles.RAG_LAMBDA_EXECUTION_ROLE, 'PipelineSM']),
            StringParameter.valueForStringParameter(
                this,
                `${config.deploymentPrefix}/roles/${createCdkId([config.deploymentName, Roles.RAG_LAMBDA_EXECUTION_ROLE])}`,
            ),
        );

        // Grant permissions for EventBridge rule management
        lambdaExecutionRole.addToPrincipalPolicy(new PolicyStatement({
            effect: Effect.ALLOW,
            actions: [
                'events:PutRule',
                'events:DeleteRule',
                'events:PutTargets',
                'events:RemoveTargets',
                'events:DescribeRule',
                'events:ListTargetsByRule',
                'events:ListRules'
            ],
            resources: [
                `arn:${config.partition}:events:${config.region}:${stack.account}:rule/${config.deploymentName}-*`
            ]
        }));

        // Grant permissions for Lambda invocation permissions
        lambdaExecutionRole.addToPrincipalPolicy(new PolicyStatement({
            effect: Effect.ALLOW,
            actions: [
                'lambda:AddPermission',
                'lambda:RemovePermission',
                'lambda:GetPolicy'
            ],
            resources: [
                `arn:${config.partition}:lambda:${config.region}:${stack.account}:function:${config.deploymentName}-*`
            ]
        }));

        // Grant DynamoDB permissions for collections table
        collectionsTable.grantReadWriteData(lambdaExecutionRole);

        const lambdaEnvironment = {
            ...baseEnvironment,
            COLLECTIONS_TABLE_NAME: collectionsTable.tableName,
            DEPLOYMENT_NAME: config.deploymentName,
            DEPLOYMENT_STAGE: config.deploymentStage,
            PARTITION: config.partition,
            REGION: config.region
        };

        const makeFn = (id: string, fnSuffix: string, entry: string, timeout = LAMBDA_TIMEOUT, memorySize = LAMBDA_MEMORY) =>
            definePythonLambda(this, id, {
                functionName: `${config.deploymentName}-${config.deploymentStage}-${fnSuffix}`,
                handlerDir: 'repository',
                entry,
                config,
                timeout,
                memorySize,
                vpc,
                environment: lambdaEnvironment,
                layers,
                role: lambdaExecutionRole,
            });

        const validateInputLambda = makeFn(
            'ValidateInputLambda',
            'pipeline-validate-input',
            'state_machine.pipeline_validate_input.handler',
            Duration.seconds(30),
            256,
        );

        const createPipelineRulesLambda = makeFn(
            'CreatePipelineRulesLambda',
            'pipeline-create-rules',
            'state_machine.pipeline_create_rules.handler',
        );

        const updatePipelineRulesLambda = makeFn(
            'UpdatePipelineRulesLambda',
            'pipeline-update-rules',
            'state_machine.pipeline_update_rules.handler',
        );

        const deletePipelineRulesLambda = makeFn(
            'DeletePipelineRulesLambda',
            'pipeline-delete-rules',
            'state_machine.pipeline_delete_rules.handler',
        );

        const updateCollectionStatusLambda = makeFn(
            'UpdateCollectionStatusLambda',
            'pipeline-update-status',
            'state_machine.pipeline_update_status.handler',
            Duration.seconds(30),
            256,
        );

        // Define Step Functions tasks
        const validateInput = new tasks.LambdaInvoke(this, 'Validate Input', {
            lambdaFunction: validateInputLambda,
            outputPath: OUTPUT_PATH,
            resultPath: '$.validationResult'
        });

        const createRules = new tasks.LambdaInvoke(this, 'Create Pipeline Rules', {
            lambdaFunction: createPipelineRulesLambda,
            outputPath: OUTPUT_PATH,
            resultPath: '$.createResult'
        });

        const updateRules = new tasks.LambdaInvoke(this, 'Update Pipeline Rules', {
            lambdaFunction: updatePipelineRulesLambda,
            outputPath: OUTPUT_PATH,
            resultPath: '$.updateResult'
        });

        const deleteRules = new tasks.LambdaInvoke(this, 'Delete Pipeline Rules', {
            lambdaFunction: deletePipelineRulesLambda,
            outputPath: OUTPUT_PATH,
            resultPath: '$.deleteResult'
        });

        const updateStatusSuccess = new tasks.LambdaInvoke(this, 'Update Status - Success', {
            lambdaFunction: updateCollectionStatusLambda,
            payload: sfn.TaskInput.fromObject({
                'repositoryId.$': '$.repositoryId',
                'collectionId.$': '$.collectionId',
                'status': 'ACTIVE'
            }),
            outputPath: OUTPUT_PATH
        });

        const updateStatusFailed = new tasks.LambdaInvoke(this, 'Update Status - Failed', {
            lambdaFunction: updateCollectionStatusLambda,
            payload: sfn.TaskInput.fromObject({
                'repositoryId.$': '$.repositoryId',
                'collectionId.$': '$.collectionId',
                'status': 'PIPELINE_FAILED',
                'error.$': '$.error'
            }),
            outputPath: OUTPUT_PATH
        });

        const succeed = new sfn.Succeed(this, 'Pipeline Operation Succeeded');
        const fail = new sfn.Fail(this, 'Pipeline Operation Failed', {
            cause: 'Pipeline operation failed',
            error: 'PipelineOperationError'
        });

        // Define operation routing choice
        const operationChoice = new sfn.Choice(this, 'Route by Operation')
            .when(sfn.Condition.stringEquals('$.operation', 'CREATE'), createRules)
            .when(sfn.Condition.stringEquals('$.operation', 'UPDATE'), updateRules)
            .when(sfn.Condition.stringEquals('$.operation', 'DELETE'), deleteRules)
            .otherwise(fail);

        // Define state machine workflow
        const definition = validateInput
            .next(operationChoice);

        createRules
            .addCatch(updateStatusFailed.next(fail), {
                resultPath: '$.error'
            })
            .next(updateStatusSuccess)
            .next(succeed);

        updateRules
            .addCatch(updateStatusFailed.next(fail), {
                resultPath: '$.error'
            })
            .next(updateStatusSuccess)
            .next(succeed);

        deleteRules
            .addCatch(updateStatusFailed.next(fail), {
                resultPath: '$.error'
            })
            .next(updateStatusSuccess)
            .next(succeed);

        // Create IAM role for Step Functions
        const stateMachineRole = new Role(this, 'PipelineStateMachineRole', {
            assumedBy: new ServicePrincipal('states.amazonaws.com'),
            description: 'Role for Pipeline State Machine'
        });

        // Grant permissions to invoke Lambda functions
        validateInputLambda.grantInvoke(stateMachineRole);
        createPipelineRulesLambda.grantInvoke(stateMachineRole);
        updatePipelineRulesLambda.grantInvoke(stateMachineRole);
        deletePipelineRulesLambda.grantInvoke(stateMachineRole);
        updateCollectionStatusLambda.grantInvoke(stateMachineRole);

        // Create the state machine
        this.stateMachine = new sfn.StateMachine(this, 'PipelineStateMachine', {
            stateMachineName: `${config.deploymentName}-${config.deploymentStage}-pipeline-state-machine`,
            definitionBody: sfn.DefinitionBody.fromChainable(definition),
            role: stateMachineRole,
            timeout: Duration.minutes(30),
            tracingEnabled: true
        });

        this.stateMachineArn = this.stateMachine.stateMachineArn;

        // Store state machine ARN in SSM for Collection API to use
        new StringParameter(this, 'PipelineStateMachineArnParameter', {
            parameterName: `${config.deploymentPrefix}/pipeline/statemachine/arn`,
            stringValue: this.stateMachineArn,
            description: 'ARN of the Pipeline State Machine'
        });
    }
}

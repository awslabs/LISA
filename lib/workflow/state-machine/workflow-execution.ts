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
import { BaseProps } from '../../schema';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as sfn from 'aws-cdk-lib/aws-stepfunctions';
import * as tasks from 'aws-cdk-lib/aws-stepfunctions-tasks';

export type WorkflowExecutionStateMachineProps = BaseProps & {
    stepExecutorLambda: lambda.IFunction;
    role?: iam.IRole;
};

export class WorkflowExecutionStateMachine extends Construct {
    public readonly stateMachine: sfn.StateMachine;

    constructor (scope: Construct, id: string, props: WorkflowExecutionStateMachineProps) {
        super(scope, id);

        const { config, stepExecutorLambda, role } = props;

        const start = new sfn.Pass(this, 'StartExecution');

        const executeStep = new tasks.LambdaInvoke(this, 'ExecuteStep', {
            lambdaFunction: stepExecutorLambda,
            payload: sfn.TaskInput.fromObject({
                step: sfn.JsonPath.objectAt('$.step'),
                context: sfn.JsonPath.objectAt('$.context'),
            }),
            resultPath: '$.stepResult',
            outputPath: '$.Payload',
        });

        const executeAllSteps = new sfn.Map(this, 'ExecuteSteps', {
            itemsPath: sfn.JsonPath.stringAt('$.steps'),
            resultPath: '$.stepResults',
            itemSelector: {
                'step.$': '$$.Map.Item.Value',
                'context.$': '$.context',
            },
        }).itemProcessor(executeStep);

        const summarizeExecution = new tasks.LambdaInvoke(this, 'SummarizeExecution', {
            lambdaFunction: stepExecutorLambda,
            payload: sfn.TaskInput.fromObject({
                mode: 'summarize_results',
                stepResults: sfn.JsonPath.listAt('$.stepResults'),
            }),
            outputPath: '$.Payload',
        });

        const definition = start.next(executeAllSteps).next(summarizeExecution);

        this.stateMachine = new sfn.StateMachine(this, 'WorkflowExecutionStateMachine', {
            definitionBody: sfn.DefinitionBody.fromChainable(definition),
            role,
            stateMachineType: sfn.StateMachineType.STANDARD,
            removalPolicy: config.removalPolicy,
        });
    }
}

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


import { BaseProps } from '../../schema';
import { ITable } from 'aws-cdk-lib/aws-dynamodb';
import { Code, Function, ILayerVersion } from 'aws-cdk-lib/aws-lambda';
import { IRole } from 'aws-cdk-lib/aws-iam';
import { ISecurityGroup } from 'aws-cdk-lib/aws-ec2';
import { IStringParameter } from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';
import { LambdaInvoke } from 'aws-cdk-lib/aws-stepfunctions-tasks';
import { LAMBDA_MEMORY, LAMBDA_TIMEOUT, OUTPUT_PATH, POLLING_TIMEOUT } from './constants';
import {
    Choice,
    Condition,
    DefinitionBody,
    StateMachine,
    Succeed,
    Wait,
    WaitTime,
} from 'aws-cdk-lib/aws-stepfunctions';
import { Vpc } from '../../networking/vpc';
import { Queue } from 'aws-cdk-lib/aws-sqs';
import { getDefaultRuntime } from '../../api-base/utils';
import * as cdk from 'aws-cdk-lib';


type UpdateModelStateMachineProps = BaseProps & {
    modelTable: ITable,
    lambdaLayers: ILayerVersion[],
    vpc: Vpc,
    securityGroups: ISecurityGroup[];
    restApiContainerEndpointPs: IStringParameter;
    managementKeyName: string;
    role?: IRole,
    executionRole?: IRole;
};


/**
 * State Machine for updating models.
 */
export class UpdateModelStateMachine extends Construct {
    readonly stateMachineArn: string;

    constructor (scope: Construct, id: string, props: UpdateModelStateMachineProps) {
        super(scope, id);

        const {
            config,
            modelTable,
            lambdaLayers,
            role,
            vpc,
            securityGroups,
            restApiContainerEndpointPs,
            managementKeyName,
            executionRole
        } = props;

        const environment = {  // Environment variables to set in all Lambda functions
            MODEL_TABLE_NAME: modelTable.tableName,
            LISA_API_URL_PS_NAME: restApiContainerEndpointPs.parameterName,
            REST_API_VERSION: 'v2',
            MANAGEMENT_KEY_NAME: managementKeyName,
            RESTAPI_SSL_CERT_ARN: config.restApiConfig?.sslCertIamArn ?? '',
        };

        const handleJobIntake = new LambdaInvoke(this, 'HandleJobIntake', {
            lambdaFunction: new Function(this, 'HandleJobIntakeFunc', {
                deadLetterQueueEnabled: true,
                deadLetterQueue: new Queue(this, 'HandleJobIntakeDLQ', {
                    queueName: `${cdk.Stack.of(this).stackName}-HandleJobIntakeDLQ`,
                    enforceSSL: true,
                }),
                runtime: getDefaultRuntime(),
                handler: 'models.state_machine.update_model.handle_job_intake',
                code: Code.fromAsset('./lambda'),
                timeout: LAMBDA_TIMEOUT,
                memorySize: LAMBDA_MEMORY,
                reservedConcurrentExecutions: 5,
                role: role,
                vpc: vpc.vpc,
                vpcSubnets: vpc.subnetSelection,
                securityGroups: securityGroups,
                layers: lambdaLayers,
                environment: environment,
            }),
            outputPath: OUTPUT_PATH,
        });

        const handlePollCapacity = new LambdaInvoke(this, 'HandlePollCapacity', {
            lambdaFunction: new Function(this, 'HandlePollCapacityFunc', {
                deadLetterQueueEnabled: true,
                deadLetterQueue: new Queue(this, 'HandlePollCapacityDLQ', {
                    queueName: `${cdk.Stack.of(this).stackName}-HandlePollCapacityDLQ`,
                    enforceSSL: true,
                }),
                runtime: getDefaultRuntime(),
                handler: 'models.state_machine.update_model.handle_poll_capacity',
                code: Code.fromAsset('./lambda'),
                timeout: LAMBDA_TIMEOUT,
                memorySize: LAMBDA_MEMORY,
                reservedConcurrentExecutions: 5,
                role: role,
                vpc: vpc.vpc,
                vpcSubnets: vpc.subnetSelection,
                securityGroups: securityGroups,
                layers: lambdaLayers,
                environment: environment,
            }),
            outputPath: OUTPUT_PATH,
        });

        const handleFinishUpdate = new LambdaInvoke(this, 'HandleFinishUpdate', {
            lambdaFunction: new Function(this, 'HandleFinishUpdateFunc', {
                deadLetterQueueEnabled: true,
                deadLetterQueue: new Queue(this, 'HandleFinishUpdateDLQ', {
                    queueName: `${cdk.Stack.of(this).stackName}-HandleFinishUpdateDLQ`,
                    enforceSSL: true,
                }),
                runtime: getDefaultRuntime(),
                handler: 'models.state_machine.update_model.handle_finish_update',
                code: Code.fromAsset('./lambda'),
                timeout: LAMBDA_TIMEOUT,
                memorySize: LAMBDA_MEMORY,
                reservedConcurrentExecutions: 5,
                role: role,
                vpc: vpc.vpc,
                vpcSubnets: vpc.subnetSelection,
                securityGroups: securityGroups,
                layers: lambdaLayers,
                environment: environment,
            }),
            outputPath: OUTPUT_PATH,
        });

        // terminal states
        const successState = new Succeed(this, 'UpdateSuccess');

        // choice states
        const hasCapacityUpdateChoice = new Choice(this, 'HasCapacityUpdateChoice');
        const pollAsgChoice = new Choice(this, 'PollAsgChoice');

        // wait states
        const waitBeforePollAsg = new Wait(this, 'WaitBeforePollAsg', {
            time: POLLING_TIMEOUT
        });
        const waitBeforeModelAvailable = new Wait(this, 'WaitBeforeModelAvailable', {
            time: WaitTime.secondsPath('$.model_warmup_seconds'),
        });

        // State Machine definition
        handleJobIntake.next(hasCapacityUpdateChoice);
        hasCapacityUpdateChoice
            .when(Condition.booleanEquals('$.has_capacity_update', true), handlePollCapacity)
            .otherwise(handleFinishUpdate);

        handlePollCapacity.next(pollAsgChoice);
        pollAsgChoice.when(Condition.booleanEquals('$.should_continue_capacity_polling', true), waitBeforePollAsg)
            .otherwise(waitBeforeModelAvailable);
        waitBeforePollAsg.next(handlePollCapacity);

        waitBeforeModelAvailable.next(handleFinishUpdate);

        handleFinishUpdate.next(successState);

        const stateMachine = new StateMachine(this, 'UpdateModelSM', {
            definitionBody: DefinitionBody.fromChainable(handleJobIntake),
            ...(executionRole &&
            {
                role: executionRole
            })
        });

        this.stateMachineArn = stateMachine.stateMachineArn;

    }
}

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
import { LambdaInvoke } from 'aws-cdk-lib/aws-stepfunctions-tasks';
import {
    Choice,
    Condition,
    DefinitionBody,
    StateMachine,
    Succeed,
    Wait,
} from 'aws-cdk-lib/aws-stepfunctions';
import { Code, Function, ILayerVersion } from 'aws-cdk-lib/aws-lambda';
import { BaseProps } from '../../schema';
import { IRole } from 'aws-cdk-lib/aws-iam';
import { ISecurityGroup } from 'aws-cdk-lib/aws-ec2';
import { ITable } from 'aws-cdk-lib/aws-dynamodb';
import { LAMBDA_MEMORY, LAMBDA_TIMEOUT, OUTPUT_PATH, POLLING_TIMEOUT } from './constants';
import { IStringParameter } from 'aws-cdk-lib/aws-ssm';
import { Vpc } from '../../networking/vpc';
import { getDefaultRuntime } from '../../api-base/utils';
import * as path from 'path';
import { Stack } from 'aws-cdk-lib';

const HERE = path.resolve(__dirname);
type DeleteModelStateMachineProps = BaseProps & {
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
 * State Machine for deleting models.
 */
export class DeleteModelStateMachine extends Construct {
    readonly stateMachineArn: string;

    constructor (scope: Construct, id: string, props: DeleteModelStateMachineProps) {
        super(scope, id);

        const { config, modelTable, lambdaLayers, role, vpc, securityGroups, restApiContainerEndpointPs, managementKeyName, executionRole } = props;

        const environment = {  // Environment variables to set in all Lambda functions
            MODEL_TABLE_NAME: modelTable.tableName,
            LISA_API_URL_PS_NAME: restApiContainerEndpointPs.parameterName,
            REST_API_VERSION: 'v2',
            MANAGEMENT_KEY_NAME: managementKeyName,
            RESTAPI_SSL_CERT_ARN: config.restApiConfig?.sslCertIamArn ?? '',
        };
        const lambdaPath = path.join(HERE, '..', '..','..', 'lambda');
        // Needs to return if model has a stack to delete or if it is only in LiteLLM. Updates model state to DELETING.
        // Input payload to state machine contains the model name that we want to delete.
        const setModelToDeleting = new LambdaInvoke(this, 'SetModelToDeleting', {
            lambdaFunction: new Function(this, 'SetModelToDeletingFunc', {
                runtime: getDefaultRuntime(),
                handler: 'models.state_machine.delete_model.handle_set_model_to_deleting',
                code: Code.fromAsset(lambdaPath),
                timeout: LAMBDA_TIMEOUT,
                memorySize: LAMBDA_MEMORY,
                role: role,
                vpc: vpc.vpc,
                vpcSubnets: vpc.subnetSelection,
                securityGroups: securityGroups,
                layers: lambdaLayers,
                environment: environment,
            }),
            outputPath: OUTPUT_PATH,
        });

        const deleteFromLitellm = new LambdaInvoke(this, 'DeleteFromLitellm', {
            lambdaFunction: new Function(this, 'DeleteFromLitellmFunc', {
                runtime: getDefaultRuntime(),
                handler: 'models.state_machine.delete_model.handle_delete_from_litellm',
                code: Code.fromAsset(lambdaPath),
                timeout: LAMBDA_TIMEOUT,
                memorySize: LAMBDA_MEMORY,
                role: role,
                vpc: vpc.vpc,
                vpcSubnets: vpc.subnetSelection,
                securityGroups: securityGroups,
                layers: lambdaLayers,
                environment: environment,
            }),
            outputPath: OUTPUT_PATH,
        });

        const deleteStack = new LambdaInvoke(this, 'DeleteStack', {
            lambdaFunction: new Function(this, 'DeleteStackFunc', {
                runtime: getDefaultRuntime(),
                handler: 'models.state_machine.delete_model.handle_delete_stack',
                code: Code.fromAsset(lambdaPath),
                timeout: LAMBDA_TIMEOUT,
                memorySize: LAMBDA_MEMORY,
                role: role,
                vpc: vpc.vpc,
                vpcSubnets: vpc.subnetSelection,
                securityGroups: securityGroups,
                layers: lambdaLayers,
                environment: environment,
            }),
            outputPath: OUTPUT_PATH,
        });

        const monitorDeleteStack = new LambdaInvoke(this, 'MonitorDeleteStack', {
            lambdaFunction: new Function(this, 'MonitorDeleteStackFunc', {
                runtime: getDefaultRuntime(),
                handler: 'models.state_machine.delete_model.handle_monitor_delete_stack',
                code: Code.fromAsset(lambdaPath),
                timeout: LAMBDA_TIMEOUT,
                memorySize: LAMBDA_MEMORY,
                role: role,
                vpc: vpc.vpc,
                vpcSubnets: vpc.subnetSelection,
                securityGroups: securityGroups,
                layers: lambdaLayers,
                environment: environment,
            }),
            outputPath: OUTPUT_PATH,
        });

        const deleteFromDdb = new LambdaInvoke(this, 'DeleteFromDdb', {
            lambdaFunction: new Function(this, 'DeleteFromDdbFunc', {
                runtime: getDefaultRuntime(),
                handler: 'models.state_machine.delete_model.handle_delete_from_ddb',
                code: Code.fromAsset(lambdaPath),
                timeout: LAMBDA_TIMEOUT,
                memorySize: LAMBDA_MEMORY,
                role: role,
                vpc: vpc.vpc,
                vpcSubnets: vpc.subnetSelection,
                securityGroups: securityGroups,
                layers: lambdaLayers,
                environment: environment,
            }),
            outputPath: OUTPUT_PATH,
        });

        const successState = new Succeed(this, 'DeleteSuccess');

        const deleteStackChoice = new Choice(this, 'DeleteStackChoice');
        const pollDeleteStackChoice = new Choice(this, 'PollDeleteStackChoice');
        const waitBeforePollingStackStatus = new Wait(this, 'WaitBeforePollDeleteStack', {
            time: POLLING_TIMEOUT,
        });

        // State Machine definition
        setModelToDeleting.next(deleteFromLitellm);
        deleteFromLitellm.next(deleteStackChoice);

        deleteStackChoice
            .when(Condition.isNotNull('$.cloudformation_stack_arn'), deleteStack)
            .otherwise(deleteFromDdb);

        deleteStack.next(monitorDeleteStack);
        monitorDeleteStack.next(pollDeleteStackChoice);

        waitBeforePollingStackStatus.next(monitorDeleteStack);

        pollDeleteStackChoice
            .when(Condition.booleanEquals('$.continue_polling', true), waitBeforePollingStackStatus)
            .otherwise(deleteFromDdb);


        deleteFromDdb.next(successState);

        const stateMachine = new StateMachine(this, 'DeleteModelSM', {
            definitionBody: DefinitionBody.fromChainable(setModelToDeleting),
            ...(executionRole &&
            {
                role: executionRole
            })
        });

        this.stateMachineArn = stateMachine.stateMachineArn;
    }
}

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
import { LAMBDA_MEMORY, LAMBDA_TIMEOUT, OUTPUT_PATH, POLLING_TIMEOUT } from '../../models/state-machine/constants';
import { Vpc } from '../../networking/vpc';
import { getDefaultRuntime } from '../../api-base/utils';
import { LAMBDA_PATH } from '../../util';

type DeleteMcpServerStateMachineProps = BaseProps & {
    mcpServerTable: ITable,
    lambdaLayers: ILayerVersion[],
    vpc: Vpc,
    securityGroups: ISecurityGroup[];
    role?: IRole,
    executionRole?: IRole;
};


/**
 * State Machine for deleting MCP servers.
 */
export class DeleteMcpServerStateMachine extends Construct {
    readonly stateMachineArn: string;

    constructor (scope: Construct, id: string, props: DeleteMcpServerStateMachineProps) {
        super(scope, id);

        const { config, mcpServerTable, lambdaLayers, role, vpc, securityGroups, executionRole } = props;

        const environment = {  // Environment variables to set in all Lambda functions
            MCP_SERVERS_TABLE_NAME: mcpServerTable.tableName,
            DEPLOYMENT_PREFIX: config.deploymentPrefix ?? '',
        };
        const lambdaPath = config.lambdaPath || LAMBDA_PATH;

        // Needs to return if server has a stack to delete. Updates server state to DELETING.
        // Input payload to state machine contains the server ID that we want to delete.
        const setServerToDeleting = new LambdaInvoke(this, 'SetServerToDeleting', {
            lambdaFunction: new Function(this, 'SetServerToDeletingFunc', {
                runtime: getDefaultRuntime(),
                handler: 'mcp_server.state_machine.delete_mcp_server.handle_set_server_to_deleting',
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
                handler: 'mcp_server.state_machine.delete_mcp_server.handle_delete_stack',
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
                handler: 'mcp_server.state_machine.delete_mcp_server.handle_monitor_delete_stack',
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
                handler: 'mcp_server.state_machine.delete_mcp_server.handle_delete_from_ddb',
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
        setServerToDeleting.next(deleteStackChoice);

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

        const stateMachine = new StateMachine(this, 'DeleteMcpServerSM', {
            definitionBody: DefinitionBody.fromChainable(setServerToDeleting),
            ...(executionRole &&
            {
                role: executionRole
            })
        });

        this.stateMachineArn = stateMachine.stateMachineArn;
    }
}

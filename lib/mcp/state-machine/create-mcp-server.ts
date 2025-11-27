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

import {
    Choice,
    Condition,
    DefinitionBody,
    Fail,
    StateMachine,
    Succeed,
    Wait,
} from 'aws-cdk-lib/aws-stepfunctions';
import { Construct } from 'constructs';
import { Duration } from 'aws-cdk-lib';
import { BaseProps } from '../../schema';
import { ITable } from 'aws-cdk-lib/aws-dynamodb';
import { Code, Function, ILayerVersion } from 'aws-cdk-lib/aws-lambda';
import { IRole } from 'aws-cdk-lib/aws-iam';
import { LAMBDA_MEMORY, LAMBDA_TIMEOUT, OUTPUT_PATH, POLLING_TIMEOUT } from './constants';
import { ISecurityGroup } from 'aws-cdk-lib/aws-ec2';
import { LambdaInvoke } from 'aws-cdk-lib/aws-stepfunctions-tasks';
import { Vpc } from '../../networking/vpc';
import { getPythonRuntime } from '../../api-base/utils';
import { LAMBDA_PATH } from '../../util';

type CreateMcpServerStateMachineProps = BaseProps & {
    mcpServerTable: ITable,
    lambdaLayers: ILayerVersion[];
    mcpServerDeployerFnArn: string;
    vpc: Vpc,
    securityGroups: ISecurityGroup[];
    managementKeyName: string;
    role?: IRole,
    executionRole?: IRole;
};

/**
 * State Machine for creating MCP servers.
 */
export class CreateMcpServerStateMachine extends Construct {
    readonly stateMachineArn: string;

    constructor (scope: Construct, id: string, props: CreateMcpServerStateMachineProps) {
        super(scope, id);

        const { config, mcpServerTable, lambdaLayers, mcpServerDeployerFnArn, role, vpc, securityGroups, managementKeyName, executionRole } = props;
        const lambdaPath = config.lambdaPath || LAMBDA_PATH;
        const environment = {
            MCP_SERVER_DEPLOYER_FN_ARN: mcpServerDeployerFnArn,
            MCP_SERVERS_TABLE_NAME: mcpServerTable.tableName,
            MANAGEMENT_KEY_NAME: managementKeyName,
            RESTAPI_SSL_CERT_ARN: config.restApiConfig?.sslCertIamArn ?? '',
            DEPLOYMENT_PREFIX: config.deploymentPrefix ?? '',
        };

        const setServerToCreating = new LambdaInvoke(this, 'SetServerToCreating', {
            lambdaFunction: new Function(this, 'SetServerToCreatingFunc', {
                runtime: getPythonRuntime(),
                handler: 'mcp_server.state_machine.create_mcp_server.handle_set_server_to_creating',
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

        const deployServer = new LambdaInvoke(this, 'DeployServer', {
            lambdaFunction: new Function(this, 'DeployServerFunc', {
                runtime: getPythonRuntime(),
                handler: 'mcp_server.state_machine.create_mcp_server.handle_deploy_server',
                code: Code.fromAsset(lambdaPath),
                timeout: Duration.minutes(8),
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

        const pollDeployment = new LambdaInvoke(this, 'PollDeployment', {
            lambdaFunction: new Function(this, 'PollDeploymentFunc', {
                runtime: getPythonRuntime(),
                handler: 'mcp_server.state_machine.create_mcp_server.handle_poll_deployment',
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

        const pollDeploymentChoice = new Choice(this, 'PollDeploymentChoice');
        const waitBeforePolling = new Wait(this, 'WaitBeforePolling', {
            time: POLLING_TIMEOUT,
        });

        const addServerToActive = new LambdaInvoke(this, 'AddServerToActive', {
            lambdaFunction: new Function(this, 'AddServerToActiveFunc', {
                runtime: getPythonRuntime(),
                handler: 'mcp_server.state_machine.create_mcp_server.handle_add_server_to_active',
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

        const handleFailureState = new LambdaInvoke(this, 'HandleFailure', {
            lambdaFunction: new Function(this, 'HandleFailureFunc', {
                runtime: getPythonRuntime(),
                handler: 'mcp_server.state_machine.create_mcp_server.handle_failure',
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

        const successState = new Succeed(this, 'CreateSuccess');
        const failState = new Fail(this, 'CreateFailed');

        // State Machine definition
        setServerToCreating.next(deployServer);
        deployServer.addCatch(handleFailureState, {
            errors: ['States.TaskFailed'],
        });
        deployServer.next(pollDeployment);
        pollDeployment.addCatch(handleFailureState, {
            errors: ['States.TaskFailed'],
        });
        pollDeployment.next(pollDeploymentChoice);
        pollDeploymentChoice
            .when(Condition.booleanEquals('$.continue_polling', true), waitBeforePolling)
            .otherwise(addServerToActive);
        waitBeforePolling.next(pollDeployment);

        // terminal states
        handleFailureState.next(failState);
        addServerToActive.next(successState);

        const stateMachine = new StateMachine(this, 'CreateMcpServerSM', {
            definitionBody: DefinitionBody.fromChainable(setServerToCreating),
            ...(executionRole &&
            {
                role: executionRole
            })
        });

        this.stateMachineArn = stateMachine.stateMachineArn;
    }
}

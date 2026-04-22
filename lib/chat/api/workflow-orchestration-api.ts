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
import { LayerVersion } from 'aws-cdk-lib/aws-lambda';
import { AttributeType, BillingMode, Table } from 'aws-cdk-lib/aws-dynamodb';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { getPythonRuntime, PythonLambdaFunction, registerAPIEndpoint } from '../../api-base/utils';
import { createLambdaRole } from '../../core/utils';
import { getAuditLoggingEnv } from '../../api-base/auditEnv';
import { IRole } from 'aws-cdk-lib/aws-iam';
import { IAuthorizer, RestApi } from 'aws-cdk-lib/aws-apigateway';
import { Vpc } from '../../networking/vpc';
import { ISecurityGroup } from 'aws-cdk-lib/aws-ec2';
import { LAMBDA_PATH } from '../../util';
import { RemovalPolicy, Stack } from 'aws-cdk-lib';
import { Effect, PolicyStatement, Role, ServicePrincipal } from 'aws-cdk-lib/aws-iam';
import { IFunction } from 'aws-cdk-lib/aws-lambda';
import { WorkflowExecutionStateMachine } from '../../workflow/state-machine/workflow-execution';

type WorkflowOrchestrationApiProps = {
    authorizer: IAuthorizer;
    restApiId: string;
    rootResourceId: string;
    securityGroups: ISecurityGroup[];
    vpc: Vpc;
} & BaseProps;

export class WorkflowOrchestrationApi extends Construct {
    public readonly workflowsTable: Table;

    constructor (scope: Construct, id: string, props: WorkflowOrchestrationApiProps) {
        super(scope, id);

        const { authorizer, config, restApiId, rootResourceId, securityGroups, vpc } = props;
        const stack = Stack.of(this);

        const commonLambdaLayer = LayerVersion.fromLayerVersionArn(
            this,
            'workflow-orchestration-common-layer',
            StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/layerVersion/common`),
        );

        const fastapiLambdaLayer = LayerVersion.fromLayerVersionArn(
            this,
            'workflow-orchestration-fastapi-layer',
            StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/layerVersion/fastapi`),
        );

        this.workflowsTable = new Table(this, 'WorkflowOrchestrationTable', {
            partitionKey: {
                name: 'workflowId',
                type: AttributeType.STRING,
            },
            removalPolicy: config.removalPolicy,
            deletionProtection: config.removalPolicy !== RemovalPolicy.DESTROY,
            billingMode: BillingMode.PAY_PER_REQUEST,
        });

        const environment = {
            WORKFLOW_ORCHESTRATION_TABLE_NAME: this.workflowsTable.tableName,
            WORKFLOW_SCHEDULE_RULE_PREFIX: `${config.deploymentName}-workflow`,
            WORKFLOW_SCHEDULER_TARGET_ARN: '',
            WORKFLOW_SCHEDULER_TARGET_ROLE_ARN: '',
            WORKFLOW_EXECUTION_SFN_ARN: '',
            ADMIN_GROUP: config.authConfig?.adminGroup || '',
            ...getAuditLoggingEnv(config),
        };

        const apis: PythonLambdaFunction[] = [
            {
                name: 'list_workflows',
                resource: 'workflow_orchestration',
                description: 'List workflow definitions',
                path: 'workflows',
                method: 'GET',
                environment,
            },
            {
                name: 'create',
                resource: 'workflow_orchestration',
                description: 'Create workflow definition',
                path: 'workflows',
                method: 'POST',
                environment,
            },
            {
                name: 'execute_workflow_step',
                resource: 'workflow_orchestration',
                description: 'Execute workflow step',
                path: 'workflows/execute-step',
                method: 'POST',
                environment,
            },
            {
                name: 'approve_workflow_step',
                resource: 'workflow_orchestration',
                description: 'Approve workflow step',
                path: 'workflows/approve',
                method: 'POST',
                environment,
            },
            {
                name: 'get_workflow',
                resource: 'workflow_orchestration',
                description: 'Get workflow definition by id',
                path: 'workflows/{workflowId}',
                method: 'GET',
                environment,
            },
            {
                name: 'update',
                resource: 'workflow_orchestration',
                description: 'Update workflow definition',
                path: 'workflows/{workflowId}',
                method: 'PUT',
                environment,
            },
            {
                name: 'delete',
                resource: 'workflow_orchestration',
                description: 'Delete workflow definition',
                path: 'workflows/{workflowId}',
                method: 'DELETE',
                environment,
            },
        ];

        const lambdaRole: IRole = createLambdaRole(
            this,
            config.deploymentName,
            'WorkflowOrchestrationApi',
            this.workflowsTable.tableArn,
            config.roles?.LambdaExecutionRole,
        );

        lambdaRole.addToPrincipalPolicy(new PolicyStatement({
            effect: Effect.ALLOW,
            actions: [
                'events:PutRule',
                'events:DeleteRule',
                'events:PutTargets',
                'events:RemoveTargets',
            ],
            resources: [
                `arn:${config.partition}:events:${config.region}:${stack.account}:rule/${config.deploymentName}-workflow-*`
            ],
        }));

        const restApi = RestApi.fromRestApiAttributes(this, 'RestApi', {
            restApiId,
            rootResourceId,
        });

        const lambdaPath = config.lambdaPath || LAMBDA_PATH;
        const workflowLambdas: IFunction[] = [];
        let stepExecutorLambda: IFunction | undefined;
        apis.forEach((f) => {
            const lambdaFunction = registerAPIEndpoint(
                this,
                restApi,
                lambdaPath,
                [commonLambdaLayer, fastapiLambdaLayer],
                f,
                getPythonRuntime(),
                vpc,
                securityGroups,
                authorizer,
                lambdaRole,
            );
            workflowLambdas.push(lambdaFunction);
            if (f.name === 'execute_workflow_step') {
                stepExecutorLambda = lambdaFunction;
            }

            if (f.name === 'approve_workflow_step') {
                this.workflowsTable.grantReadWriteData(lambdaFunction);
            } else if (f.method === 'POST' || f.method === 'PUT') {
                this.workflowsTable.grantWriteData(lambdaFunction);
            } else if (f.method === 'GET') {
                this.workflowsTable.grantReadData(lambdaFunction);
            } else if (f.method === 'DELETE') {
                this.workflowsTable.grantReadWriteData(lambdaFunction);
            }
        });

        if (!stepExecutorLambda) {
            throw new Error('execute_workflow_step lambda must be registered for workflow execution state machine');
        }

        const workflowExecution = new WorkflowExecutionStateMachine(this, 'WorkflowExecution', {
            config,
            stepExecutorLambda,
        });

        const schedulerTargetArn = workflowExecution.stateMachine.stateMachineArn;
        const schedulerTargetInvokeRole = new Role(this, 'WorkflowSchedulerTargetInvokeRole', {
            assumedBy: new ServicePrincipal('events.amazonaws.com'),
        });
        schedulerTargetInvokeRole.addToPrincipalPolicy(new PolicyStatement({
            effect: Effect.ALLOW,
            actions: ['states:StartExecution'],
            resources: [schedulerTargetArn],
        }));
        lambdaRole.addToPrincipalPolicy(new PolicyStatement({
            effect: Effect.ALLOW,
            actions: ['iam:PassRole'],
            resources: [schedulerTargetInvokeRole.roleArn],
            conditions: {
                StringEquals: {
                    'iam:PassedToService': 'events.amazonaws.com',
                },
            },
        }));

        workflowLambdas.forEach((lambdaFn) => {
            const mutableLambda = lambdaFn as unknown as {
                addEnvironment?: (key: string, value: string) => void;
            };
            if (lambdaFn === stepExecutorLambda) {
                return;
            }
            mutableLambda.addEnvironment?.('WORKFLOW_EXECUTION_SFN_ARN', schedulerTargetArn);
            mutableLambda.addEnvironment?.('WORKFLOW_SCHEDULER_TARGET_ARN', schedulerTargetArn);
            mutableLambda.addEnvironment?.('WORKFLOW_SCHEDULER_TARGET_ROLE_ARN', schedulerTargetInvokeRole.roleArn);
        });

    }
}

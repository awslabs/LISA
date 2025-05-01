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
import { Stack, StackProps } from 'aws-cdk-lib';
import { Effect, IManagedPolicy, IRole, ManagedPolicy, PolicyStatement, Role, ServicePrincipal } from 'aws-cdk-lib/aws-iam';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';

import { createCdkId, getIamPolicyStatements } from '../core/utils';
import { BaseProps, Config } from '../schema';
import { getRoleId, ROLE, Roles } from '../core/iam/roles';

/**
 * Properties for the LisaServeIAMStack Construct.
 */
export type LisaIAMStackProps = BaseProps & StackProps;

/**
 * Properties for the ECS Role definitions
 */
export type ECSRole = {
    id: string;
    type: ECSTaskType;
};

/**
 * ECS Task types
 */
export enum ECSTaskType {
    API = 'API',
}

/**
 * LisaServe IAM.
 */
export class LisaServeIAMSConstruct extends Construct {

    private readonly scope: Stack;

    /**
     * @param {Stack} scope - The parent or owner of the construct.
     * @param {string} id - The unique identifier for the construct within its scope.
     * @param {LisaIAMStackProps} props - Properties for the Stack.
     */
    constructor (scope: Stack, id: string, props: LisaIAMStackProps) {
        super(scope, id);
        this.scope = scope;
        const { config } = props;

        /*
        * Create role for Lambda execution if deploying RAG
        */
        if (config.deployRag) {
            this.createRagLambdaRole(config);
        }

        /*
         * Create roles for ECS tasks. Currently, all deployed models and all API ECS tasks use
         * an identical role. In the future it's possible the models and API containers may need
         * specific roles
         */
        const taskPolicy = this.createTaskPolicy(config.deploymentName, config.deploymentPrefix);

        const ecsRoles: ECSRole[] = [
            {
                id: 'REST',
                type: ECSTaskType.API,
            },
        ];

        ecsRoles.forEach((role) => {
            const taskRoleOverride = getRoleId(`ECS_${role.id}_${role.type}_ROLE`.toUpperCase());
            const taskRoleId = createCdkId([role.id, ROLE]);
            const taskRoleName = createCdkId([config.deploymentName, role.id, ROLE]);
            const taskRole = config.roles ?
                // @ts-expect-error - dynamic key lookup of object
                Role.fromRoleName(scope, taskRoleId, config.roles[taskRoleOverride]) :
                this.createEcsTaskRole(role, taskRoleId, taskRoleName, taskPolicy);

            new StringParameter(scope, createCdkId([config.deploymentName, role.id, 'SP']), {
                parameterName: `${config.deploymentPrefix}/roles/${role.id}`,
                stringValue: taskRole.roleArn,
                description: `Role ARN for LISA ${role.type} ${role.id} ECS Task`,
            });

            if (config.roles) {
                const executionRoleOverride = getRoleId(`ECS_${role.id}_${role.type}_EX_ROLE`.toUpperCase());
                // @ts-expect-error - dynamic key lookup of object
                const executionRole = Role.fromRoleName(scope, createCdkId([role.id, 'ExRole']), config.roles[executionRoleOverride]);

                new StringParameter(scope, createCdkId([config.deploymentName, role.id, 'EX', 'SP']), {
                    parameterName: `${config.deploymentPrefix}/roles/${role.id}EX`,
                    stringValue: executionRole.roleArn,
                    description: `Role ARN for LISA ${role.type} ${role.id} ECS Execution`,
                });
            }
        });
    }

    private createTaskPolicy (deploymentName: string, deploymentPrefix?: string): IManagedPolicy {
        const statements = getIamPolicyStatements('ecs');
        const taskPolicyId = createCdkId([deploymentName, 'ECSPolicy']);
        const taskPolicy = new ManagedPolicy(this.scope, taskPolicyId, {
            managedPolicyName: createCdkId([deploymentName, 'ECSPolicy']),
            statements,
        });

        new StringParameter(this.scope, createCdkId(['ECSPolicy', 'SP']), {
            parameterName: `${deploymentPrefix}/policies/${taskPolicyId}`,
            stringValue: taskPolicy.managedPolicyArn,
            description: `Managed Policy ARN for LISA ${taskPolicyId}`,
        });

        return taskPolicy;
    }

    private createRagLambdaRole (config: Config): IRole {
        const ragLambdaRoleId = createCdkId([config.deploymentName, Roles.RAG_LAMBDA_EXECUTION_ROLE]);
        const ragLambdaRole = config.roles?.RagLambdaExecutionRole ?
            Role.fromRoleName(this.scope, ragLambdaRoleId, config.roles.RagLambdaExecutionRole) :
            this.createRagLambdaExecutionRole(config.deploymentName, ragLambdaRoleId);

        new StringParameter(this.scope, createCdkId(['LisaRagRole', 'StringParameter']), {
            parameterName: `${config.deploymentPrefix}/roles/${ragLambdaRoleId}`,
            stringValue: ragLambdaRole.roleArn,
            description: `Role ARN for LISA ${ragLambdaRoleId}`,
        });

        return ragLambdaRole;
    }

    private createRagLambdaExecutionRole (deploymentName: string, roleName: string) {
        const lambdaPolicyStatements = getIamPolicyStatements('rag');
        const lambdaRagPolicy = new ManagedPolicy(this.scope, createCdkId([deploymentName, 'RAGPolicy']), {
            managedPolicyName: createCdkId([deploymentName, 'RAGPolicy']),
            statements: lambdaPolicyStatements,
        });

        const ecsTaskExecutionRolePolicy = ManagedPolicy.fromAwsManagedPolicyName('service-role/AmazonECSTaskExecutionRolePolicy');
        const role = new Role(this.scope, Roles.RAG_LAMBDA_EXECUTION_ROLE, {
            roleName,
            assumedBy: new ServicePrincipal('lambda.amazonaws.com'),
            description: 'Role used by RAG API lambdas to access AWS resources',
            managedPolicies: [lambdaRagPolicy, ecsTaskExecutionRolePolicy],
        });

        role.assumeRolePolicy?.addStatements(
            new PolicyStatement({
                effect: Effect.ALLOW,
                actions: ['sts:AssumeRole'],
                principals: [new ServicePrincipal('ecs-tasks.amazonaws.com')],
            })
        );

        return role;
    }

    private createEcsTaskRole (role: ECSRole, roleId: string, roleName: string, taskPolicy: IManagedPolicy): IRole {
        return new Role(this.scope, roleId, {
            assumedBy: new ServicePrincipal('ecs-tasks.amazonaws.com'),
            roleName,
            description: `Allow ${role.id} ${role.type} task access to AWS resources`,
            managedPolicies: [taskPolicy],
        });
    }
}

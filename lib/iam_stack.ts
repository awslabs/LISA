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
import { IManagedPolicy, IRole, ManagedPolicy, Role, ServicePrincipal } from 'aws-cdk-lib/aws-iam';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { NagSuppressions } from 'cdk-nag';
import { Construct } from 'constructs';

import { createCdkId, getIamPolicyStatements } from './core/utils';
import { BaseProps, Config } from './schema';
import { of, ROLE, Roles } from './core/iam/roles';

/**
 * Properties for the LisaServeIAMStack Construct.
 */
type LisaIAMStackProps = {} & BaseProps & StackProps;

/**
 * Properties for the ECS Role definitions
 */
type ECSRole = {
    id: string;
    type: ECSTaskType;
};

/**
 * ECS Task types
 */
enum ECSTaskType {
    API = 'API',
}

/**
 * LisaServe IAM stack.
 */
export class LisaServeIAMStack extends Stack {

    /**
     * @param {Construct} scope - The parent or owner of the construct.
     * @param {string} id - The unique identifier for the construct within its scope.
     * @param {LisaIAMStackProps} props - Properties for the Stack.
     */
    constructor (scope: Construct, id: string, props: LisaIAMStackProps) {
        super(scope, id, props);
        const { config } = props;
        // Add suppression for IAM4 (use of managed policy)
        NagSuppressions.addStackSuppressions(this, [
            {
                id: 'AwsSolutions-IAM4',
                reason: 'Allow use of AmazonSSMManagedInstanceCore policy to allow EC2 to enable SSM core functionality.',
            },
        ]);

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
            const taskRoleOverride = of(`ECS_${role.id}_${role.type}_ROLE`.toUpperCase());
            const taskRoleId = createCdkId([role.id, ROLE]);
            const taskRoleName = createCdkId([config.deploymentName, role.id, ROLE]);
            const taskRole = config.roles ?
                // @ts-expect-error - dynamic key lookup of object
                Role.fromRoleName(this, taskRoleId, config.roles[taskRoleOverride]) :
                this.createEcsTaskRole(role, taskRoleId, taskRoleName, taskPolicy);

            new StringParameter(this, createCdkId([config.deploymentName, role.id, 'SP']), {
                parameterName: `${config.deploymentPrefix}/roles/${role.id}`,
                stringValue: taskRole.roleArn,
                description: `Role ARN for LISA ${role.type} ${role.id} ECS Task`,
            });

            if (config.roles) {
                const executionRoleOverride = of(`ECS_${role.id}_${role.type}_EX_ROLE`.toUpperCase());
                // @ts-expect-error - dynamic key lookup of object
                const executionRole = Role.fromRoleName(this, createCdkId([role.id, 'ExRole']), config.roles[executionRoleOverride]);

                new StringParameter(this, createCdkId([config.deploymentName, role.id, 'EX', 'SP']), {
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
        const taskPolicy = new ManagedPolicy(this, taskPolicyId, {
            managedPolicyName: createCdkId([deploymentName, 'ECSPolicy']),
            statements,
        });

        new StringParameter(this, createCdkId(['ECSPolicy', 'SP']), {
            parameterName: `${deploymentPrefix}/policies/${taskPolicyId}`,
            stringValue: taskPolicy.managedPolicyArn,
            description: `Managed Policy ARN for LISA ${taskPolicyId}`,
        });

        return taskPolicy;
    }

    private createRagLambdaRole (config: Config): IRole {
        const ragLambdaRoleId = createCdkId([config.deploymentName, Roles.RAG_LAMBDA_EXECUTION_ROLE]);
        const ragLambdaRole = config.roles?.RagLambdaExecutionRole ?
            Role.fromRoleName(this, ragLambdaRoleId, config.roles.RagLambdaExecutionRole) :
            this.createRagLambdaExecutionRole(config.deploymentName, ragLambdaRoleId);

        new StringParameter(this, createCdkId(['LisaRagRole', 'StringParameter']), {
            parameterName: `${config.deploymentPrefix}/roles/${ragLambdaRoleId}`,
            stringValue: ragLambdaRole.roleArn,
            description: `Role ARN for LISA ${ragLambdaRoleId}`,
        });

        return ragLambdaRole;
    }

    private createRagLambdaExecutionRole (deploymentName: string, roleName: string) {
        const lambdaPolicyStatements = getIamPolicyStatements('rag');
        const lambdaRagPolicy = new ManagedPolicy(this, createCdkId([deploymentName, 'RAGPolicy']), {
            managedPolicyName: createCdkId([deploymentName, 'RAGPolicy']),
            statements: lambdaPolicyStatements,
        });

        return new Role(this, Roles.RAG_LAMBDA_EXECUTION_ROLE, {
            roleName,
            assumedBy: new ServicePrincipal('lambda.amazonaws.com'),
            description: 'Role used by RAG API lambdas to access AWS resources',
            managedPolicies: [lambdaRagPolicy],
        });
    }

    private createEcsTaskRole (role: ECSRole, roleId: string, roleName: string, taskPolicy: IManagedPolicy): IRole {
        return new Role(this, roleId, {
            assumedBy: new ServicePrincipal('ecs-tasks.amazonaws.com'),
            roleName,
            description: `Allow ${role.id} ${role.type} task access to AWS resources`,
            managedPolicies: [taskPolicy],
        });
    }
}

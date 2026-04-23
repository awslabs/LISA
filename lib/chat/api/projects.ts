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

import { IAuthorizer, RestApi } from 'aws-cdk-lib/aws-apigateway';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import { Effect, IRole, PolicyStatement } from 'aws-cdk-lib/aws-iam';
import { ISecurityGroup } from 'aws-cdk-lib/aws-ec2';
import { RemovalPolicy } from 'aws-cdk-lib';
import { Construct } from 'constructs';

import { getPythonRuntime, PythonLambdaFunction, registerAPIEndpoint } from '../../api-base/utils';
import { BaseProps } from '../../schema';
import { createLambdaRole } from '../../core/utils';
import { getAuditLoggingEnv } from '../../api-base/auditEnv';
import { Vpc } from '../../networking/vpc';
import { getPythonLambdaLayers } from '../../util';

type ProjectsApiProps = {
    authorizer: IAuthorizer;
    restApiId: string;
    rootResourceId: string;
    securityGroups: ISecurityGroup[];
    vpc: Vpc;
    sessionTable: dynamodb.Table;
    configTable: dynamodb.Table;
    projectsTable?: dynamodb.Table;
} & BaseProps;

export class ProjectsApi extends Construct {
    public readonly projectsTable: dynamodb.Table;

    constructor (scope: Construct, id: string, props: ProjectsApiProps) {
        super(scope, id);

        const { authorizer, config, restApiId, rootResourceId, securityGroups, vpc, sessionTable, configTable } = props;

        const lambdaLayers = getPythonLambdaLayers(this, config, ['common', 'fastapi'], 'Projects');

        // Use pre-created table if provided (from chatConstruct), otherwise create one
        this.projectsTable = props.projectsTable ?? new dynamodb.Table(this, 'ProjectsTable', {
            partitionKey: { name: 'userId', type: dynamodb.AttributeType.STRING },
            sortKey: { name: 'projectId', type: dynamodb.AttributeType.STRING },
            billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption: dynamodb.TableEncryption.AWS_MANAGED,
            removalPolicy: config.removalPolicy,
            deletionProtection: config.removalPolicy !== RemovalPolicy.DESTROY,
        });

        const restApi = RestApi.fromRestApiAttributes(this, 'RestApi', {
            restApiId,
            rootResourceId,
        });

        const env = {
            PROJECTS_TABLE_NAME: this.projectsTable.tableName,
            SESSIONS_TABLE_NAME: sessionTable.tableName,
            SESSIONS_BY_USER_ID_INDEX_NAME: 'byUserId',
            CONFIG_TABLE_NAME: configTable.tableName,
            ...getAuditLoggingEnv(config),
        };

        const lambdaRole: IRole = createLambdaRole(
            this,
            config.deploymentName,
            'ProjectsApi',
            this.projectsTable.tableArn,
            config.roles?.LambdaExecutionRole,
        );

        // Projects Lambda needs read access to SessionsTable for ownership checks and cascade
        lambdaRole.addToPrincipalPolicy(
            new PolicyStatement({
                effect: Effect.ALLOW,
                actions: ['dynamodb:GetItem', 'dynamodb:Query'],
                resources: [sessionTable.tableArn, `${sessionTable.tableArn}/index/byUserId`],
            })
        );

        // Projects Lambda needs write access to SessionsTable for assign/unassign and cascade clear
        lambdaRole.addToPrincipalPolicy(
            new PolicyStatement({
                effect: Effect.ALLOW,
                actions: ['dynamodb:UpdateItem', 'dynamodb:DeleteItem'],
                resources: [sessionTable.tableArn],
            })
        );

        // Config table read for maxProjectsPerUser
        lambdaRole.addToPrincipalPolicy(
            new PolicyStatement({
                effect: Effect.ALLOW,
                actions: ['dynamodb:GetItem', 'dynamodb:Query'],
                resources: [configTable.tableArn],
            })
        );

        const apis: PythonLambdaFunction[] = [
            {
                name: 'list_projects',
                resource: 'projects',
                description: 'List all projects for the calling user',
                path: 'project',
                method: 'GET',
                environment: env,
            },
            {
                name: 'create_project',
                resource: 'projects',
                description: 'Create a new project',
                path: 'project',
                method: 'POST',
                environment: env,
            },
            {
                name: 'rename_project',
                resource: 'projects',
                description: 'Rename a project',
                path: 'project/{projectId}',
                method: 'PUT',
                environment: env,
            },
            {
                name: 'delete_project',
                resource: 'projects',
                description: 'Delete a project',
                path: 'project/{projectId}',
                method: 'DELETE',
                environment: env,
            },
            {
                name: 'assign_session_project',
                resource: 'projects',
                description: 'Assign or unassign a session to/from a project',
                path: 'project/{projectId}/session/{sessionId}',
                method: 'PUT',
                environment: env,
            },
        ];

        apis.forEach((f) => {
            const lambdaFunction = registerAPIEndpoint(
                this,
                restApi,
                config,
                lambdaLayers,
                f,
                getPythonRuntime(),
                vpc,
                securityGroups,
                authorizer,
                lambdaRole,
            );
            if (f.method === 'GET') {
                this.projectsTable.grantReadData(lambdaFunction);
            } else {
                this.projectsTable.grantReadWriteData(lambdaFunction);
            }
        });
    }
}

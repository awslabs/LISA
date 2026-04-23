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
import { IFunction } from 'aws-cdk-lib/aws-lambda';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';

import { getPythonRuntime, PythonLambdaFunction, registerAPIEndpoint } from '../../api-base/utils';
import { BaseProps } from '../../schema';
import { createLambdaRole } from '../../core/utils';
import { getAuditLoggingEnv } from '../../api-base/auditEnv';
import { Vpc } from '../../networking/vpc';
import { getPythonLambdaLayers } from '../../util';
import { RemovalPolicy } from 'aws-cdk-lib';

/**
 * Properties for McpApi Construct.
 *
 * @property {IVpc} vpc - Stack VPC
 * @property {Layer} commonLayer - Lambda layer for all Lambdas.
 * @property {IRestApi} restAPI - REST APIGW for UI and Lambdas
 * @property {IRole} lambdaExecutionRole - Execution role for lambdas
 * @property {IAuthorizer} authorizer - APIGW authorizer
 * @property {ISecurityGroup[]} securityGroups - Security groups for Lambdas
 * @property {Map<number, ISubnet> }importedSubnets for application.
 */
type McpApiProps = {
    authorizer: IAuthorizer;
    restApiId: string;
    rootResourceId: string;
    securityGroups: ISecurityGroup[];
    vpc: Vpc;
} & BaseProps;

/**
 * API which Maintains mcp state in DynamoDB
 */
export class McpApi extends Construct {
    readonly mcpServersTableNameParameter: StringParameter;

    constructor (scope: Construct, id: string, props: McpApiProps) {
        super(scope, id);

        const { authorizer, config, restApiId, rootResourceId, securityGroups, vpc } = props;

        const lambdaLayers = getPythonLambdaLayers(this, config, ['common', 'fastapi'], 'McpApi');

        // Create DynamoDB table to handle configured mcp servers
        const mcpServersTable = new dynamodb.Table(this, 'McpServersTable', {
            partitionKey: {
                name: 'id',
                type: dynamodb.AttributeType.STRING,
            },
            sortKey: {
                name: 'owner',
                type: dynamodb.AttributeType.STRING,
            },
            billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption: dynamodb.TableEncryption.AWS_MANAGED,
            removalPolicy: config.removalPolicy,
            deletionProtection: config.removalPolicy !== RemovalPolicy.DESTROY,
        });
        const byOwnerIndex = 'byOwner';
        mcpServersTable.addGlobalSecondaryIndex({
            indexName: byOwnerIndex,
            partitionKey: { name: 'owner', type: dynamodb.AttributeType.STRING },
        });

        const byOwnerSorted = 'byOwnerSorted';
        mcpServersTable.addGlobalSecondaryIndex({
            indexName: byOwnerSorted,
            partitionKey: { name: 'owner', type: dynamodb.AttributeType.STRING },
            sortKey: { name: 'created', type: dynamodb.AttributeType.STRING },
        });

        // Create SSM parameter for the MCP servers table name
        this.mcpServersTableNameParameter = new StringParameter(this, 'McpServersTableNameParameter', {
            parameterName: `${config.deploymentPrefix}/table/mcpServersTable`,
            stringValue: mcpServersTable.tableName,
            description: 'Name of the MCP servers DynamoDB table',
        });

        const bedrockAgentApprovalsTable = new dynamodb.Table(this, 'BedrockAgentApprovalsTable', {
            partitionKey: {
                name: 'agentId',
                type: dynamodb.AttributeType.STRING,
            },
            billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption: dynamodb.TableEncryption.AWS_MANAGED,
            removalPolicy: config.removalPolicy,
            deletionProtection: config.removalPolicy !== RemovalPolicy.DESTROY,
        });

        new StringParameter(this, 'BedrockAgentApprovalsTableNameParameter', {
            parameterName: `${config.deploymentPrefix}/table/bedrockAgentApprovalsTable`,
            stringValue: bedrockAgentApprovalsTable.tableName,
            description: 'DynamoDB table for admin-approved Bedrock agents (catalog)',
        });

        const restApi = RestApi.fromRestApiAttributes(this, 'RestApi', {
            restApiId: restApiId,
            rootResourceId: rootResourceId,
        });

        const env = {
            ADMIN_GROUP: config.authConfig?.adminGroup || '',
            MCP_SERVERS_TABLE_NAME: mcpServersTable.tableName,
            MCP_SERVERS_BY_OWNER_INDEX_NAME: byOwnerIndex,
            BEDROCK_AGENT_APPROVALS_TABLE_NAME: bedrockAgentApprovalsTable.tableName,
            ...getAuditLoggingEnv(config),
        };

        // Create API Lambda functions
        const apis: PythonLambdaFunction[] = [
            {
                name: 'list_mcp_servers',
                resource: 'mcp_server',
                description: 'Lists available mcp servers for user',
                path: 'mcp-server',
                method: 'GET',
                environment: env,
            },
            {
                name: 'get',
                resource: 'mcp_server',
                description: 'Returns the selected mcp server',
                path: 'mcp-server/{serverId}',
                method: 'GET',
                environment: env,
            },
            {
                name: 'create',
                resource: 'mcp_server',
                description: 'Creates the mcp server',
                path: 'mcp-server',
                method: 'POST',
                environment: env,
            },
            {
                name: 'delete',
                resource: 'mcp_server',
                description: 'Deletes selected mcp server',
                path: 'mcp-server/{serverId}',
                method: 'DELETE',
                environment: env,
            },
            {
                name: 'update',
                resource: 'mcp_server',
                description: 'Creates or updates selected mcp server',
                path: 'mcp-server/{serverId}',
                method: 'PUT',
                environment: env,
            },
            {
                name: 'put_bedrock_agent_approval',
                resource: 'mcp_server',
                description: 'Admin: upsert Bedrock agent catalog entry',
                path: 'bedrock-agents/approval/{agentId}',
                method: 'PUT',
                environment: env,
            },
            {
                name: 'delete_bedrock_agent_approval',
                resource: 'mcp_server',
                description: 'Admin: remove Bedrock agent from catalog',
                path: 'bedrock-agents/approval/{agentId}',
                method: 'DELETE',
                environment: env,
            },
            {
                name: 'list_bedrock_agent_approvals',
                resource: 'mcp_server',
                description: 'Admin: list all Bedrock agent catalog entries',
                path: 'bedrock-agents/approvals',
                method: 'GET',
                environment: env,
            },
            {
                name: 'list_bedrock_agents_discovery',
                resource: 'mcp_server',
                description: 'Admin: full Bedrock agent account scan',
                path: 'bedrock-agents/discovery',
                method: 'GET',
                environment: env,
            },
            {
                name: 'invoke_bedrock_agent',
                resource: 'mcp_server',
                description: 'Invoke a Bedrock Agent and return aggregated text',
                path: 'bedrock-agents/invoke',
                method: 'POST',
                environment: env,
            },
            {
                name: 'list_bedrock_agents',
                resource: 'mcp_server',
                description: 'List approved Bedrock agents for the current user',
                path: 'bedrock-agents',
                method: 'GET',
                environment: env,
            },
        ];

        const lambdaRole: IRole = createLambdaRole(this, config.deploymentName, 'McpServerApi', mcpServersTable.tableArn, config.roles?.LambdaExecutionRole);
        lambdaRole.addToPrincipalPolicy(
            new PolicyStatement({
                effect: Effect.ALLOW,
                actions: [
                    'bedrock:ListAgents',
                    'bedrock:GetAgent',
                    'bedrock:ListAgentAliases',
                    'bedrock:GetAgentAlias',
                    'bedrock:ListAgentActionGroups',
                    'bedrock:GetAgentActionGroup',
                    'bedrock:InvokeAgent',
                ],
                resources: ['*'],
            }),
        );
        const mcpLambdas: IFunction[] = [];
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
            mcpLambdas.push(lambdaFunction);
            if (f.method === 'POST' || f.method === 'PUT') {
                mcpServersTable.grantWriteData(lambdaFunction);
            } else if (f.method === 'GET') {
                mcpServersTable.grantReadData(lambdaFunction);
            } else if (f.method === 'DELETE') {
                mcpServersTable.grantReadWriteData(lambdaFunction);
            }
        });
        mcpLambdas.forEach((fn) => bedrockAgentApprovalsTable.grantReadWriteData(fn));
    }
}

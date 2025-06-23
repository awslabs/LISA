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
import { IRole } from 'aws-cdk-lib/aws-iam';
import { ISecurityGroup } from 'aws-cdk-lib/aws-ec2';
import { LayerVersion } from 'aws-cdk-lib/aws-lambda';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';

import { getDefaultRuntime, PythonLambdaFunction, registerAPIEndpoint } from '../../api-base/utils';
import { BaseProps } from '../../schema';
import { createLambdaRole } from '../../core/utils';
import { Vpc } from '../../networking/vpc';
import { LAMBDA_PATH } from '../../util';

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
    constructor (scope: Construct, id: string, props: McpApiProps) {
        super(scope, id);

        const { authorizer, config, restApiId, rootResourceId, securityGroups, vpc } = props;

        // Get common layer based on arn from SSM due to issues with cross stack references
        const commonLambdaLayer = LayerVersion.fromLayerVersionArn(
            this,
            'mcp-common-lambda-layer',
            StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/layerVersion/common`),
        );

        const fastapiLambdaLayer = LayerVersion.fromLayerVersionArn(
            this,
            'mcp-fastapi-lambda-layer',
            StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/layerVersion/fastapi`),
        );

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

        const restApi = RestApi.fromRestApiAttributes(this, 'RestApi', {
            restApiId: restApiId,
            rootResourceId: rootResourceId,
        });

        const env = {
            MCP_SERVERS_TABLE_NAME: mcpServersTable.tableName,
            MCP_SERVERS_BY_OWNER_INDEX_NAME: byOwnerIndex,
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
                name: 'get_mcp_server',
                resource: 'mcp_server',
                description: 'Returns the selected mcp server',
                path: 'mcp-server/{serverId}',
                method: 'GET',
                environment: env,
            },
            {
                name: 'create_mcp_server',
                resource: 'mcp_server',
                description: 'Creates the mcp server',
                path: 'mcp-server',
                method: 'POST',
                environment: env,
            },
            {
                name: 'delete_mcp_server',
                resource: 'mcp_server',
                description: 'Deletes selected mcp server',
                path: 'mcp-server/{serverId}',
                method: 'DELETE',
                environment: env,
            },
            {
                name: 'put_mcp_server',
                resource: 'mcp_server',
                description: 'Creates or updates selected mcp server',
                path: 'mcp-server/{serverId}',
                method: 'PUT',
                environment: env,
            },
        ];

        const lambdaRole: IRole = createLambdaRole(this, config.deploymentName, 'McpServerApi', mcpServersTable.tableArn, config.roles?.LambdaExecutionRole);
        const lambdaPath = config.lambdaPath || LAMBDA_PATH;
        apis.forEach((f) => {
            const lambdaFunction = registerAPIEndpoint(
                this,
                restApi,
                lambdaPath,
                [commonLambdaLayer, fastapiLambdaLayer],
                f,
                getDefaultRuntime(),
                vpc,
                securityGroups,
                authorizer,
                lambdaRole,
            );
            if (f.method === 'POST' || f.method === 'PUT') {
                mcpServersTable.grantWriteData(lambdaFunction);
            } else if (f.method === 'GET') {
                mcpServersTable.grantReadData(lambdaFunction);
            } else if (f.method === 'DELETE') {
                mcpServersTable.grantReadWriteData(lambdaFunction);
            }
        });
    }
}

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
import { IRole } from 'aws-cdk-lib/aws-iam';
import { IAuthorizer, RestApi } from 'aws-cdk-lib/aws-apigateway';
import { Vpc } from '../../networking/vpc';
import { ISecurityGroup } from 'aws-cdk-lib/aws-ec2';
import { LAMBDA_PATH } from '../../util';
import { RemovalPolicy } from 'aws-cdk-lib';

/**
 * Properties required to initialize the ChatAssistantStacksApi construct.
 */
type ChatAssistantStacksApiProps = {
    authorizer: IAuthorizer;
    restApiId: string;
    rootResourceId: string;
    securityGroups: ISecurityGroup[];
    vpc: Vpc;
} & BaseProps;

/**
 * Constructs and manages API endpoints for Chat Assistant Stacks (list, get, create, update, delete, update status).
 */
export class ChatAssistantStacksApi extends Construct {
    public readonly stacksTable: Table;

    constructor (scope: Construct, id: string, props: ChatAssistantStacksApiProps) {
        super(scope, id);

        const { authorizer, config, restApiId, rootResourceId, securityGroups, vpc } = props;

        const commonLambdaLayer = LayerVersion.fromLayerVersionArn(
            this,
            'chat-assistant-stacks-common-layer',
            StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/layerVersion/common`),
        );

        const fastapiLambdaLayer = LayerVersion.fromLayerVersionArn(
            this,
            'chat-assistant-stacks-fastapi-layer',
            StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/layerVersion/fastapi`),
        );

        this.stacksTable = new Table(this, 'ChatAssistantStacksTable', {
            partitionKey: {
                name: 'stackId',
                type: AttributeType.STRING,
            },
            removalPolicy: config.removalPolicy,
            deletionProtection: config.removalPolicy !== RemovalPolicy.DESTROY,
            billingMode: BillingMode.PAY_PER_REQUEST,
        });

        const environment = {
            CHAT_ASSISTANT_STACKS_TABLE_NAME: this.stacksTable.tableName,
            ADMIN_GROUP: config.authConfig?.adminGroup || '',
        };

        const apis: PythonLambdaFunction[] = [
            {
                name: 'list_stacks',
                resource: 'chat_assistant_stacks',
                description: 'List Chat Assistant Stacks',
                path: 'chat-assistant-stacks',
                method: 'GET',
                environment,
            },
            {
                name: 'create',
                resource: 'chat_assistant_stacks',
                description: 'Create Chat Assistant Stack',
                path: 'chat-assistant-stacks',
                method: 'POST',
                environment,
            },
            {
                name: 'get_stack',
                resource: 'chat_assistant_stacks',
                description: 'Get Chat Assistant Stack by id',
                path: 'chat-assistant-stacks/{stackId}',
                method: 'GET',
                environment,
            },
            {
                name: 'update',
                resource: 'chat_assistant_stacks',
                description: 'Update Chat Assistant Stack',
                path: 'chat-assistant-stacks/{stackId}',
                method: 'PUT',
                environment,
            },
            {
                name: 'delete',
                resource: 'chat_assistant_stacks',
                description: 'Delete Chat Assistant Stack',
                path: 'chat-assistant-stacks/{stackId}',
                method: 'DELETE',
                environment,
            },
            {
                name: 'update_status',
                resource: 'chat_assistant_stacks',
                description: 'Update stack active status',
                path: 'chat-assistant-stacks/{stackId}/status',
                method: 'PUT',
                environment,
            },
        ];

        const lambdaRole: IRole = createLambdaRole(
            this,
            config.deploymentName,
            'ChatAssistantStacksApi',
            this.stacksTable.tableArn,
            config.roles?.LambdaExecutionRole,
        );

        const restApi = RestApi.fromRestApiAttributes(this, 'RestApi', {
            restApiId,
            rootResourceId,
        });

        const lambdaPath = config.lambdaPath || LAMBDA_PATH;
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

            if (f.method === 'POST' || f.method === 'PUT') {
                this.stacksTable.grantWriteData(lambdaFunction);
            } else if (f.method === 'GET') {
                this.stacksTable.grantReadData(lambdaFunction);
            } else if (f.method === 'DELETE') {
                this.stacksTable.grantReadWriteData(lambdaFunction);
            }
        });
    }
}

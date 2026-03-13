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

// LisaChat Stack.
import { Stack, StackProps } from 'aws-cdk-lib';
import { IAuthorizer } from 'aws-cdk-lib/aws-apigateway';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import { ISecurityGroup } from 'aws-cdk-lib/aws-ec2';
import { RemovalPolicy } from 'aws-cdk-lib';
import { Construct } from 'constructs';

import { SessionApi } from './api/session';
import { BaseProps } from '../schema';
import { Vpc } from '../networking/vpc';
import { ConfigurationApi } from './api/configuration';
import { PromptTemplateApi } from './api/prompt-template-api';
import { McpApi } from './api/mcp';
import { UserPreferencesApi } from './api/user-preferences';
import { ChatAssistantStacksApi } from './api/chat-assistant-stacks-api';
import { ProjectsApi } from './api/projects';

export type LisaChatProps = {
    authorizer: IAuthorizer;
    restApiId: string;
    rootResourceId: string;
    securityGroups: ISecurityGroup[];
    vpc: Vpc;
} & BaseProps & StackProps;

/**
 * LisaChat Application Construct.
 */
export class LisaChatApplicationConstruct extends Construct {
    /**
   * @param {Stack} scope - The parent or owner of the construct.
   * @param {string} id - The unique identifier for the construct within its scope.
   * @param {LisaChatProps} props - Properties for the Stack.
   */
    constructor (scope: Stack, id: string, props: LisaChatProps) {
        super(scope, id);

        const { authorizer, config, restApiId, rootResourceId, securityGroups, vpc } = props;


        const mcpApi = new McpApi(scope, 'McpApi', {
            authorizer,
            config,
            restApiId,
            rootResourceId,
            securityGroups,
            vpc,
        });

        // Create Configuration API first to get the configuration table
        const configurationApi = new ConfigurationApi(scope, 'ConfigurationApi', {
            authorizer,
            config,
            restApiId,
            rootResourceId,
            securityGroups,
            vpc,
            ...(config.deployMcpWorkbench ? { mcpApi } : {})
        });

        // Create ProjectsTable early so its name can be passed to SessionApi for BatchGetItem
        const projectsTable = new dynamodb.Table(scope, 'ProjectsTable', {
            partitionKey: { name: 'userId', type: dynamodb.AttributeType.STRING },
            sortKey: { name: 'projectId', type: dynamodb.AttributeType.STRING },
            billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption: dynamodb.TableEncryption.AWS_MANAGED,
            removalPolicy: config.removalPolicy,
            deletionProtection: config.removalPolicy !== RemovalPolicy.DESTROY,
        });

        // Add REST API Lambdas to APIGW
        const sessionApi = new SessionApi(scope, 'SessionApi', {
            authorizer,
            config,
            restApiId,
            rootResourceId,
            securityGroups,
            vpc,
            configTable: configurationApi.configTable,
            projectsTableName: projectsTable.tableName,
        });

        // ProjectsApi receives the pre-created table so it doesn't create a duplicate
        new ProjectsApi(scope, 'ProjectsApi', {
            authorizer,
            config,
            restApiId,
            rootResourceId,
            securityGroups,
            vpc,
            sessionTable: sessionApi.sessionTable,
            configTable: configurationApi.configTable,
            projectsTable,
        });

        new PromptTemplateApi(scope, 'PromptTemplateApi', {
            authorizer,
            config,
            restApiId,
            rootResourceId,
            securityGroups,
            vpc
        });

        new UserPreferencesApi(scope, 'UserPreferencesApi', {
            authorizer,
            config,
            restApiId,
            rootResourceId,
            securityGroups,
            vpc,
        });

        new ChatAssistantStacksApi(scope, 'ChatAssistantStacksApi', {
            authorizer,
            config,
            restApiId,
            rootResourceId,
            securityGroups,
            vpc,
        });
    }
}

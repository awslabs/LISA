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
import { AttributeType, BillingMode, ProjectionType, Table } from 'aws-cdk-lib/aws-dynamodb';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { getDefaultRuntime, PythonLambdaFunction, registerAPIEndpoint } from '../../api-base/utils';
import { createLambdaRole } from '../../core/utils';
import { IRole } from 'aws-cdk-lib/aws-iam';
import { IAuthorizer, RestApi } from 'aws-cdk-lib/aws-apigateway';
import { Vpc } from '../../networking/vpc';
import { ISecurityGroup } from 'aws-cdk-lib/aws-ec2';
import { LAMBDA_PATH } from '../../util';

/**
 * Properties required to initialize the PromptTemplateApi construct,
 * including AWS resources like API Gateway, VPC, and security configurations.
 */
type PromptTemplateApiProps = {
    authorizer: IAuthorizer;
    restApiId: string;
    rootResourceId: string;
    securityGroups: ISecurityGroup[];
    vpc: Vpc;
} & BaseProps;

/**
 * Constructs and manages API endpoints for handling prompt templates in the application.
 */
export class PromptTemplateApi extends Construct {
    constructor (scope: Construct, id: string, props: PromptTemplateApiProps) {
        super(scope, id);

        const { authorizer, config, restApiId, rootResourceId, securityGroups, vpc } = props;

        const commonLambdaLayer = LayerVersion.fromLayerVersionArn(
            this,
            'session-common-lambda-layer',
            StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/layerVersion/common`),
        );

        const fastapiLambdaLayer = LayerVersion.fromLayerVersionArn(
            this,
            'models-fastapi-lambda-layer',
            StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/layerVersion/fastapi`),
        );

        const promptTemplatesTable = new Table(this, 'PromptTemplatesTable', {
            partitionKey: {
                name: 'id',
                type: AttributeType.STRING
            },
            sortKey: {
                name: 'created',
                type: AttributeType.STRING
            },
            removalPolicy: config.removalPolicy,
            billingMode: BillingMode.PAY_PER_REQUEST,
            pointInTimeRecovery: true
        });

        const byOwnerIndexName = 'byOwner';
        promptTemplatesTable.addGlobalSecondaryIndex({
            indexName: byOwnerIndexName,
            projectionType: ProjectionType.ALL,
            partitionKey: {
                name: 'owner',
                type: AttributeType.STRING
            },
            sortKey: {
                name: 'created',
                type: AttributeType.STRING
            }
        });

        const byLatestIndexName = 'byLatest';
        promptTemplatesTable.addGlobalSecondaryIndex({
            indexName: byLatestIndexName,
            projectionType: ProjectionType.ALL,
            partitionKey: {
                name: 'id',
                type: AttributeType.STRING
            },
            sortKey: {
                name: 'created',
                type: AttributeType.STRING
            }
        });

        const environment = {
            ADMIN_GROUP: config.authConfig?.adminGroup || '',
            PROMPT_TEMPLATES_TABLE_NAME: promptTemplatesTable.tableName,
            PROMPT_TEMPLATES_BY_LATEST_INDEX_NAME: byOwnerIndexName,
        };

        const apis: PythonLambdaFunction[] = [
            {
                name: 'create',
                resource: 'prompt_templates',
                description: 'Creates prompt template',
                path: 'prompt-templates',
                method: 'POST',
                environment,
            },
            {
                name: 'get',
                resource: 'prompt_templates',
                description: 'Retrieves specific prompt template by ID',
                path: 'prompt-templates/{promptTemplateId}',
                method: 'GET',
                environment,
            },
            {
                name: 'list',
                resource: 'prompt_templates',
                description: 'Lists all available prompt templates',
                path: 'prompt-templates',
                method: 'GET',
                environment,
            },
            {
                name: 'update',
                resource: 'prompt_templates',
                description: 'Updates an existing prompt template',
                path: 'prompt-templates/{promptTemplateId}',
                method: 'PUT',
                environment,
            },
            {
                name: 'delete',
                resource: 'prompt_templates',
                description: 'Deletes a specific prompt template by ID',
                path: 'prompt-templates/{promptTemplateId}',
                method: 'DELETE',
                environment,
            },
        ];

        const lambdaRole: IRole = createLambdaRole(this, config.deploymentName, 'PromptTemplatesApi', promptTemplatesTable.tableArn, config.roles?.LambdaExecutionRole);

        const restApi = RestApi.fromRestApiAttributes(this, 'RestApi', {
            restApiId: restApiId,
            rootResourceId: rootResourceId,
        });

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
                promptTemplatesTable.grantWriteData(lambdaFunction);
            } else if (f.method === 'GET') {
                promptTemplatesTable.grantReadData(lambdaFunction);
            } else if (f.method === 'DELETE') {
                promptTemplatesTable.grantReadWriteData(lambdaFunction);
            }
        });
    }
}

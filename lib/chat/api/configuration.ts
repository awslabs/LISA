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
import { ISecurityGroup } from 'aws-cdk-lib/aws-ec2';
import { LayerVersion } from 'aws-cdk-lib/aws-lambda';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';

import { getDefaultRuntime, PythonLambdaFunction, registerAPIEndpoint } from '../../api-base/utils';
import { BaseProps } from '../../schema';
import { createLambdaRole } from '../../core/utils';
import { Vpc } from '../../networking/vpc';
import { AwsCustomResource, PhysicalResourceId } from 'aws-cdk-lib/custom-resources';
import { IRole } from 'aws-cdk-lib/aws-iam';
import { LAMBDA_PATH } from '../../util';

/**
 * Props for the ConfigurationApi construct
 * Extends BaseProps to include authorizer, restApiId, rootResourceId, securityGroups, and vpc
 * @extends BaseProps
 * @property {IAuthorizer} authorizer - The authorizer for the API
 * @property {string} restApiId - The ID of the API Gateway RestApi
 * @property {string} rootResourceId - The root resource ID of the API Gateway RestApi
 * @property {ISecurityGroup[]} securityGroups - The security groups to use for the API
 * @property {Vpc} vpc - The VPC to use for the API
 */
type ConfigurationApiProps = {
    authorizer: IAuthorizer;
    restApiId: string;
    rootResourceId: string;
    securityGroups: ISecurityGroup[];
    vpc: Vpc;
} & BaseProps;

/**
 * API which Maintains config state in DynamoDB
 */
export class ConfigurationApi extends Construct {
    constructor (scope: Construct, id: string, props: ConfigurationApiProps) {
        super(scope, id);

        const { authorizer, config, restApiId, rootResourceId, securityGroups, vpc } = props;

        // Get common layer based on arn from SSM due to issues with cross stack references
        const commonLambdaLayer = LayerVersion.fromLayerVersionArn(
            this,
            'configuration-common-lambda-layer',
            StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/layerVersion/common`),
        );

        // Create DynamoDB table to handle config data
        const configTable = new dynamodb.Table(this, 'ConfigurationTable', {
            partitionKey: {
                name: 'configScope',
                type: dynamodb.AttributeType.STRING,
            },
            sortKey: {
                name: 'versionId',
                type: dynamodb.AttributeType.NUMBER,
            },
            billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption: dynamodb.TableEncryption.AWS_MANAGED,
            removalPolicy: config.removalPolicy,
        });

        const lambdaRole: IRole = createLambdaRole(this, config.deploymentName, 'ConfigurationApi', configTable.tableArn, config.roles?.LambdaConfigurationApiExecutionRole);

        // Populate the App Config table with default config
        const date = new Date();
        new AwsCustomResource(this, 'lisa-init-ddb-config', {
            onCreate: {
                service: 'DynamoDB',
                action: 'putItem',
                physicalResourceId: PhysicalResourceId.of('initConfigData'),
                parameters: {
                    TableName: configTable.tableName,
                    Item: {
                        'versionId': {'N': '0'},
                        'changedBy': {'S': 'System'},
                        'configScope': {'S': 'global'},
                        'changeReason': {'S': 'Initial deployment default config'},
                        'createdAt': {'S': Math.round(date.getTime() / 1000).toString()},
                        'configuration': {'M': {
                            'enabledComponents': {'M': {
                                'deleteSessionHistory': {'BOOL': 'True'},
                                'viewMetaData': {'BOOL': 'True'},
                                'editKwargs': {'BOOL': 'True'},
                                'editPromptTemplate': {'BOOL': 'True'},
                                'editChatHistoryBuffer': {'BOOL': 'True'},
                                'editNumOfRagDocument': {'BOOL': 'True'},
                                'uploadRagDocs': {'BOOL': 'True'},
                                'uploadContextDocs': {'BOOL': 'True'},
                                'documentSummarization': {'BOOL': 'True'},
                                'showRagLibrary': {'BOOL': 'True'},
                                'showPromptTemplateLibrary': {'BOOL': 'True'},
                                'mcpConnections': {'BOOL': 'True'},
                                'modelLibrary': {'BOOL': 'True'},
                            }},
                            'systemBanner': {'M': {
                                'isEnabled': {'BOOL': 'False'},
                                'text': {'S': ''},
                                'textColor': {'S': ''},
                                'backgroundColor': {'S': ''}
                            }}
                        }}
                    },
                },
            },
            role: lambdaRole
        });

        const restApi = RestApi.fromRestApiAttributes(this, 'RestApi', {
            restApiId: restApiId,
            rootResourceId: rootResourceId,
        });

        // Create API Lambda functions
        const apis: PythonLambdaFunction[] = [
            {
                name: 'get_configuration',
                resource: 'configuration',
                description: 'Get configuration',
                path: 'configuration',
                method: 'GET',
                environment: {
                    CONFIG_TABLE_NAME: configTable.tableName
                },
            },
            {
                name: 'update_configuration',
                resource: 'configuration',
                description: 'Updates config data',
                path: 'configuration/{configScope}',
                method: 'PUT',
                environment: {
                    CONFIG_TABLE_NAME: configTable.tableName,
                },
            },
        ];

        const lambdaPath = config.lambdaPath || LAMBDA_PATH;
        apis.forEach((f) => {
            const lambdaFunction = registerAPIEndpoint(
                this,
                restApi,
                lambdaPath,
                [commonLambdaLayer],
                f,
                getDefaultRuntime(),
                vpc,
                securityGroups,
                authorizer,
                lambdaRole,
            );
            if (f.method === 'POST' || f.method === 'PUT') {
                configTable.grantWriteData(lambdaFunction);
            } else if (f.method === 'GET') {
                configTable.grantReadData(lambdaFunction);
            } else if (f.method === 'DELETE') {
                configTable.grantReadWriteData(lambdaFunction);
            }
        });
    }
}

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
import { LayerVersion, Runtime } from 'aws-cdk-lib/aws-lambda';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';

import { PythonLambdaFunction, registerAPIEndpoint } from '../../api-base/utils';
import { BaseProps } from '../../schema';
import { createLambdaRole } from '../../core/utils';
import { Vpc } from '../../networking/vpc';

/**
 * Properties for SessionApi Construct.
 *
 * @property {IVpc} vpc - Stack VPC
 * @property {Layer} commonLayer - Lambda layer for all Lambdas.
 * @property {IRestApi} restAPI - REST APIGW for UI and Lambdas
 * @property {IRole} lambdaExecutionRole - Execution role for lambdas
 * @property {IAuthorizer} authorizer - APIGW authorizer
 * @property {ISecurityGroup[]} securityGroups - Security groups for Lambdas
 * @property {Map<number, ISubnet> }importedSubnets for application.
 */
type SessionApiProps = {
    authorizer: IAuthorizer;
    restApiId: string;
    rootResourceId: string;
    securityGroups: ISecurityGroup[];
    vpc: Vpc;
} & BaseProps;

/**
 * API which Maintains sessions state in DynamoDB
 */
export class SessionApi extends Construct {
    constructor (scope: Construct, id: string, props: SessionApiProps) {
        super(scope, id);

        const { authorizer, config, restApiId, rootResourceId, securityGroups, vpc } = props;

        // Get common layer based on arn from SSM due to issues with cross stack references
        const commonLambdaLayer = LayerVersion.fromLayerVersionArn(
            this,
            'session-common-lambda-layer',
            StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/layerVersion/common`),
        );

        // Create DynamoDB table to handle chat sessions
        const sessionTable = new dynamodb.Table(this, 'SessionsTable', {
            partitionKey: {
                name: 'sessionId',
                type: dynamodb.AttributeType.STRING,
            },
            sortKey: {
                name: 'userId',
                type: dynamodb.AttributeType.STRING,
            },
            billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption: dynamodb.TableEncryption.AWS_MANAGED,
            removalPolicy: config.removalPolicy,
        });
        const byUserIdIndex = 'byUserId';
        sessionTable.addGlobalSecondaryIndex({
            indexName: byUserIdIndex,
            partitionKey: { name: 'userId', type: dynamodb.AttributeType.STRING },
        });

        const restApi = RestApi.fromRestApiAttributes(this, 'RestApi', {
            restApiId: restApiId,
            rootResourceId: rootResourceId,
        });

        // Create API Lambda functions
        const apis: PythonLambdaFunction[] = [
            {
                name: 'list_sessions',
                resource: 'session',
                description: 'Lists available sessions for user',
                path: 'session',
                method: 'GET',
                environment: {
                    SESSIONS_TABLE_NAME: sessionTable.tableName,
                    SESSIONS_BY_USER_ID_INDEX_NAME: byUserIdIndex,
                },
            },
            {
                name: 'get_session',
                resource: 'session',
                description: 'Returns the selected session',
                path: 'session/{sessionId}',
                method: 'GET',
                environment: {
                    SESSIONS_TABLE_NAME: sessionTable.tableName,
                    SESSIONS_BY_USER_ID_INDEX_NAME: byUserIdIndex,
                },
            },
            {
                name: 'delete_session',
                resource: 'session',
                description: 'Deletes selected session',
                path: 'session/{sessionId}',
                method: 'DELETE',
                environment: {
                    SESSIONS_TABLE_NAME: sessionTable.tableName,
                    SESSIONS_BY_USER_ID_INDEX_NAME: byUserIdIndex,
                },
            },
            {
                name: 'delete_user_sessions',
                resource: 'session',
                description: 'Deletes all sessions for selected user',
                path: 'session',
                method: 'DELETE',
                environment: {
                    SESSIONS_TABLE_NAME: sessionTable.tableName,
                    SESSIONS_BY_USER_ID_INDEX_NAME: byUserIdIndex,
                },
            },
            {
                name: 'put_session',
                resource: 'session',
                description: 'Creates or updates selected session',
                path: 'session/{sessionId}',
                method: 'PUT',
                environment: {
                    SESSIONS_TABLE_NAME: sessionTable.tableName,
                    SESSIONS_BY_USER_ID_INDEX_NAME: byUserIdIndex,
                },
            },
        ];

        const lambdaRole: IRole = createLambdaRole(this, config.deploymentName, 'SessionApi', sessionTable.tableArn, config.roles?.LambdaExecutionRole);

        apis.forEach((f) => {
            const lambdaFunction = registerAPIEndpoint(
                this,
                restApi,
                authorizer,
                './lambda',
                [commonLambdaLayer],
                f,
                Runtime.PYTHON_3_10,
                vpc,
                securityGroups,
                lambdaRole,
            );
            if (f.method === 'POST' || f.method === 'PUT') {
                sessionTable.grantWriteData(lambdaFunction);
            } else if (f.method === 'GET') {
                sessionTable.grantReadData(lambdaFunction);
            } else if (f.method === 'DELETE') {
                sessionTable.grantReadWriteData(lambdaFunction);
            }
        });
    }
}

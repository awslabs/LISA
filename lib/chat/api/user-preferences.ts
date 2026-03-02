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

import { getPythonRuntime, PythonLambdaFunction, registerAPIEndpoint } from '../../api-base/utils';
import { BaseProps } from '../../schema';
import { createLambdaRole } from '../../core/utils';
import { Vpc } from '../../networking/vpc';
import { LAMBDA_PATH } from '../../util';
import { RemovalPolicy } from 'aws-cdk-lib';

/**
 * Properties for UserPreferencesApi Construct.
 *
 * @property {IVpc} vpc - Stack VPC
 * @property {Layer} commonLayer - Lambda layer for all Lambdas.
 * @property {IRestApi} restAPI - REST APIGW for UI and Lambdas
 * @property {IRole} lambdaExecutionRole - Execution role for lambdas
 * @property {IAuthorizer} authorizer - APIGW authorizer
 * @property {ISecurityGroup[]} securityGroups - Security groups for Lambdas
 * @property {Map<number, ISubnet> }importedSubnets for application.
 */
type UserPreferencesProps = {
    authorizer: IAuthorizer;
    restApiId: string;
    rootResourceId: string;
    securityGroups: ISecurityGroup[];
    vpc: Vpc;
} & BaseProps;

/**
 * API which Maintains user preferences state in DynamoDB
 */
export class UserPreferencesApi extends Construct {
    constructor (scope: Construct, id: string, props: UserPreferencesProps) {
        super(scope, id);

        const { authorizer, config, restApiId, rootResourceId, securityGroups, vpc } = props;

        // Get common layer based on arn from SSM due to issues with cross stack references
        const commonLambdaLayer = LayerVersion.fromLayerVersionArn(
            this,
            'user-preferences-common-lambda-layer',
            StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/layerVersion/common`),
        );

        const fastapiLambdaLayer = LayerVersion.fromLayerVersionArn(
            this,
            'user-preferences-fastapi-lambda-layer',
            StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/layerVersion/fastapi`),
        );

        // Create DynamoDB table to handle user preferences
        const userPreferencesTable = new dynamodb.Table(this, 'UserPreferencesTable', {
            partitionKey: {
                name: 'user',
                type: dynamodb.AttributeType.STRING,
            },
            billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption: dynamodb.TableEncryption.AWS_MANAGED,
            removalPolicy: config.removalPolicy,
            deletionProtection: config.removalPolicy !== RemovalPolicy.DESTROY,
        });

        const restApi = RestApi.fromRestApiAttributes(this, 'RestApi', {
            restApiId: restApiId,
            rootResourceId: rootResourceId,
        });

        const env = {
            USER_PREFERENCES_TABLE_NAME: userPreferencesTable.tableName
        };

        // Create API Lambda functions
        const apis: PythonLambdaFunction[] = [
            {
                name: 'get',
                resource: 'user_preferences',
                description: 'Returns the preferences for the calling user',
                path: 'user-preferences',
                method: 'GET',
                environment: env,
            },
            {
                name: 'update',
                resource: 'user_preferences',
                description: 'Creates or updates user preferences for user',
                path: 'user-preferences',
                method: 'PUT',
                environment: env,
            },
        ];

        const lambdaRole: IRole = createLambdaRole(this, config.deploymentName, 'UserPreferencesApi', userPreferencesTable.tableArn, config.roles?.LambdaExecutionRole);
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
                userPreferencesTable.grantWriteData(lambdaFunction);
            } else if (f.method === 'GET') {
                userPreferencesTable.grantReadData(lambdaFunction);
            }
        });
    }
}

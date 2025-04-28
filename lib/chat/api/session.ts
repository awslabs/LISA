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
import { BlockPublicAccess, Bucket, BucketEncryption, HttpMethods } from 'aws-cdk-lib/aws-s3';
import { RemovalPolicy } from 'aws-cdk-lib';

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

        const byUserIdIndexSorted = 'byUserIdSorted';
        sessionTable.addGlobalSecondaryIndex({
            indexName: byUserIdIndexSorted,
            partitionKey: { name: 'userId', type: dynamodb.AttributeType.STRING },
            sortKey: { name: 'startTime', type: dynamodb.AttributeType.STRING },
        });

        // Create Images S3 bucket
        const imagesBucket = new Bucket(scope, 'GeneratedImagesBucket', {
            removalPolicy: config.removalPolicy,
            autoDeleteObjects: config.removalPolicy === RemovalPolicy.DESTROY,
            enforceSSL: true,
            cors: [
                {
                    allowedMethods: [HttpMethods.GET, HttpMethods.POST],
                    allowedHeaders: ['*'],
                    allowedOrigins: ['*'],
                    exposedHeaders: ['Access-Control-Allow-Origin'],
                },
            ],
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
                    SESSIONS_BY_USER_ID_INDEX_NAME: byUserIdIndexSorted,
                    GENERATED_IMAGES_S3_BUCKET_NAME: imagesBucket.bucketName
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
                    GENERATED_IMAGES_S3_BUCKET_NAME: imagesBucket.bucketName
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
                    GENERATED_IMAGES_S3_BUCKET_NAME: imagesBucket.bucketName
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
                    GENERATED_IMAGES_S3_BUCKET_NAME: imagesBucket.bucketName
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
                    GENERATED_IMAGES_S3_BUCKET_NAME: imagesBucket.bucketName
                },
            },
            {
                name: 'attach_image_to_session',
                resource: 'session',
                description: 'Attaches image to session',
                path: 'session/{sessionId}/attachImage',
                method: 'PUT',
                environment: {
                    SESSIONS_TABLE_NAME: sessionTable.tableName,
                    SESSIONS_BY_USER_ID_INDEX_NAME: byUserIdIndex,
                    GENERATED_IMAGES_S3_BUCKET_NAME: imagesBucket.bucketName
                },
            },
        ];

        const lambdaRole: IRole = createLambdaRole(this, config.deploymentName, 'SessionApi', sessionTable.tableArn, config.roles?.LambdaExecutionRole);
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
                sessionTable.grantWriteData(lambdaFunction);
                imagesBucket.grantReadWrite(lambdaFunction);
            } else if (f.method === 'GET') {
                sessionTable.grantReadData(lambdaFunction);
                imagesBucket.grantRead(lambdaFunction);
            } else if (f.method === 'DELETE') {
                sessionTable.grantReadWriteData(lambdaFunction);
                imagesBucket.grantDelete(lambdaFunction);
            }
        });
    }
}

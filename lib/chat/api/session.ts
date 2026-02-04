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
import { LayerVersion } from 'aws-cdk-lib/aws-lambda';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { Key } from 'aws-cdk-lib/aws-kms';
import { Construct } from 'constructs';

import { getPythonRuntime, PythonLambdaFunction, registerAPIEndpoint } from '../../api-base/utils';
import { BaseProps } from '../../schema';
import { createLambdaRole } from '../../core/utils';
import { Vpc } from '../../networking/vpc';
import { LAMBDA_PATH } from '../../util';

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
 * @property {dynamodb.Table} configTable - Configuration DynamoDB table
 */
type SessionApiProps = {
    authorizer: IAuthorizer;
    restApiId: string;
    rootResourceId: string;
    securityGroups: ISecurityGroup[];
    vpc: Vpc;
    configTable: dynamodb.Table;
} & BaseProps;

/**
 * API which Maintains sessions state in DynamoDB
 */
export class SessionApi extends Construct {
    constructor (scope: Construct, id: string, props: SessionApiProps) {
        super(scope, id);

        const { authorizer, config, restApiId, rootResourceId, securityGroups, vpc, configTable } = props;

        // Get common layer based on arn from SSM due to issues with cross stack references
        const commonLambdaLayer = LayerVersion.fromLayerVersionArn(
            this,
            'session-common-lambda-layer',
            StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/layerVersion/common`),
        );

        // Get FastAPI layer for cryptography support
        const fastapiLambdaLayer = LayerVersion.fromLayerVersionArn(
            this,
            'session-fastapi-lambda-layer',
            StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/layerVersion/fastapi`),
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
            deletionProtection: config.removalPolicy !== RemovalPolicy.DESTROY,
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

        // Create KMS key for session data encryption
        const sessionEncryptionKey = new Key(this, 'SessionEncryptionKey', {
            description: 'KMS key for encrypting session data at rest',
            enableKeyRotation: true,
            removalPolicy: config.removalPolicy,
        });

        // Store KMS key ARN in SSM parameter for cross-stack access
        new StringParameter(this, 'SessionEncryptionKeyArnParameter', {
            parameterName: `${config.deploymentPrefix}/sessionEncryptionKeyArn`,
            stringValue: sessionEncryptionKey.keyArn,
        });

        // Get Images S3 bucket name from API Base stack (created there for cross-stack access)
        const imagesBucketName = StringParameter.valueForStringParameter(
            this,
            `${config.deploymentPrefix}/generatedImagesBucketName`
        );

        const restApi = RestApi.fromRestApiAttributes(this, 'RestApi', {
            restApiId: restApiId,
            rootResourceId: rootResourceId,
        });

        // Get model table name from SSM parameter
        const modelTableName = StringParameter.valueForStringParameter(
            this,
            `${config.deploymentPrefix}/modelTableName`
        );

        const env = {
            SESSIONS_TABLE_NAME: sessionTable.tableName,
            SESSIONS_BY_USER_ID_INDEX_NAME: byUserIdIndex,
            GENERATED_IMAGES_S3_BUCKET_NAME: imagesBucketName,
            MODEL_TABLE_NAME: modelTableName,
            CONFIG_TABLE_NAME: configTable.tableName,
            SESSION_ENCRYPTION_KEY_ARN: sessionEncryptionKey.keyArn,
        };

        const lambdaRole: IRole = createLambdaRole(
            this,
            config.deploymentName,
            'SessionApi',
            sessionTable.tableArn,
            config.roles?.LambdaExecutionRole,
        );

        // Add permissions to read from model table
        lambdaRole.addToPrincipalPolicy(
            new PolicyStatement({
                effect: Effect.ALLOW,
                actions: ['dynamodb:GetItem'],
                resources: [`arn:${config.partition}:dynamodb:${config.region}:${config.accountNumber}:table/${modelTableName}`]
            })
        );

        // Add permissions to read from configuration table
        lambdaRole.addToPrincipalPolicy(
            new PolicyStatement({
                effect: Effect.ALLOW,
                actions: ['dynamodb:GetItem', 'dynamodb:Query'],
                resources: [configTable.tableArn]
            })
        );

        // If metrics stack deployment is enabled
        if (config.deployMetrics) {
            // Get metrics queue name from SSM
            const usageMetricsQueueName = StringParameter.valueForStringParameter(
                this,
                `${config.deploymentPrefix}/queue-name/usage-metrics`,
            );
            // Add SQS permissions to the role
            lambdaRole.addToPrincipalPolicy(
                new PolicyStatement({
                    effect: Effect.ALLOW,
                    actions: ['sqs:SendMessage'],
                    resources: [`arn:${config.partition}:sqs:${config.region}:${config.accountNumber}:${usageMetricsQueueName}`]
                })
            );
            Object.assign(env, { USAGE_METRICS_QUEUE_NAME: usageMetricsQueueName });
        }

        // Add KMS permissions for session encryption
        lambdaRole.addToPrincipalPolicy(
            new PolicyStatement({
                effect: Effect.ALLOW,
                actions: [
                    'kms:GenerateDataKey',
                    'kms:Decrypt',
                    'kms:DescribeKey'
                ],
                resources: [sessionEncryptionKey.keyArn]
            })
        );

        // Create API Lambda functions
        const apis: PythonLambdaFunction[] = [
            {
                name: 'list_sessions',
                resource: 'session',
                description: 'Lists available sessions for user',
                path: 'session',
                method: 'GET',
                environment: env,
            },
            {
                name: 'get_session',
                resource: 'session',
                description: 'Returns the selected session',
                path: 'session/{sessionId}',
                method: 'GET',
                environment: env,
            },
            {
                name: 'delete_session',
                resource: 'session',
                description: 'Deletes selected session',
                path: 'session/{sessionId}',
                method: 'DELETE',
                environment: env,
            },
            {
                name: 'delete_user_sessions',
                resource: 'session',
                description: 'Deletes all sessions for selected user',
                path: 'session',
                method: 'DELETE',
                environment: env,
            },
            {
                name: 'put_session',
                resource: 'session',
                description: 'Creates or updates selected session',
                path: 'session/{sessionId}',
                method: 'PUT',
                environment: env,
            },{
                name: 'rename_session',
                resource: 'session',
                description: 'Updates session name',
                path: 'session/{sessionId}/name',
                method: 'PUT',
                environment: env,
            },
            {
                name: 'attach_image_to_session',
                resource: 'session',
                description: 'Attaches image to session',
                path: 'session/{sessionId}/attachImage',
                method: 'PUT',
                environment: env,
            },
        ];

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
                sessionTable.grantWriteData(lambdaFunction);
                // Grant S3 read/write permissions for image/video operations
                lambdaRole.addToPrincipalPolicy(
                    new PolicyStatement({
                        effect: Effect.ALLOW,
                        actions: ['s3:PutObject', 's3:GetObject'],
                        resources: [`arn:${config.partition}:s3:::${imagesBucketName}/*`]
                    })
                );
            } else if (f.method === 'GET') {
                sessionTable.grantReadData(lambdaFunction);
                // Grant S3 read permissions
                lambdaRole.addToPrincipalPolicy(
                    new PolicyStatement({
                        effect: Effect.ALLOW,
                        actions: ['s3:GetObject'],
                        resources: [`arn:${config.partition}:s3:::${imagesBucketName}/*`]
                    })
                );
            } else if (f.method === 'DELETE') {
                sessionTable.grantReadWriteData(lambdaFunction);
                // Grant S3 list permission on bucket for prefix-based listing
                lambdaRole.addToPrincipalPolicy(
                    new PolicyStatement({
                        effect: Effect.ALLOW,
                        actions: ['s3:ListBucket'],
                        resources: [`arn:${config.partition}:s3:::${imagesBucketName}`]
                    })
                );
                // Grant S3 delete permissions on objects
                lambdaRole.addToPrincipalPolicy(
                    new PolicyStatement({
                        effect: Effect.ALLOW,
                        actions: ['s3:DeleteObject'],
                        resources: [`arn:${config.partition}:s3:::${imagesBucketName}/*`]
                    })
                );
            }
        });
    }
}

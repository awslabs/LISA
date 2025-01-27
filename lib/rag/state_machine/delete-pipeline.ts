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

 import * as s3 from 'aws-cdk-lib/aws-s3';
 import * as lambda from 'aws-cdk-lib/aws-lambda';
 import { Code, Function, ILayerVersion } from 'aws-cdk-lib/aws-lambda';
 import * as sfn from 'aws-cdk-lib/aws-stepfunctions';
 import { DefinitionBody } from 'aws-cdk-lib/aws-stepfunctions';
 import * as tasks from 'aws-cdk-lib/aws-stepfunctions-tasks';
 import * as events from 'aws-cdk-lib/aws-events';
 import * as targets from 'aws-cdk-lib/aws-events-targets';
 import { Construct } from 'constructs';
 import { BaseProps, RagRepositoryType, PipelineConfig } from '../../schema';
 import { Vpc } from '../../networking/vpc';
 import { Table } from 'aws-cdk-lib/aws-dynamodb';
 import { getDefaultRuntime } from '../../api-base/utils';
 import { LAMBDA_MEMORY, LAMBDA_TIMEOUT } from './constants';
 import { Effect, PolicyStatement } from 'aws-cdk-lib/aws-iam';
 import * as cdk from 'aws-cdk-lib';

 import * as kms from 'aws-cdk-lib/aws-kms';
import { EventField, EventPattern, Rule, RuleTargetInput } from 'aws-cdk-lib/aws-events';
import { SfnStateMachine } from 'aws-cdk-lib/aws-events-targets';

 type DeletePipelineStateMachineProps = BaseProps & {
     vpc?: Vpc;
     pipelineConfig: PipelineConfig;
     repositoryId: string;
     type: RagRepositoryType;
     layers?: ILayerVersion[];
     registeredRepositoriesParamName: string;
     s3Bucket: s3.Bucket;
     ragDocumentTable: Table;
     ragSubDocumentTable: Table;
 };


 export class DeletePipelineStateMachine extends Construct {
     constructor (scope: Construct, id: string, props: DeletePipelineStateMachineProps) {
         super(scope, id);

         const {config, vpc, pipelineConfig, repositoryId, type, layers, registeredRepositoriesParamName, ragDocumentTable, ragSubDocumentTable} = props;

         const environment = {
            EMBEDDING_MODEL: pipelineConfig.embeddingModel,
            S3_BUCKET: pipelineConfig.s3Bucket,
            S3_PREFIX: pipelineConfig.s3Prefix,
            REPOSITORY_ID: repositoryId,
            MANAGEMENT_KEY_SECRET_NAME_PS: `${config.deploymentPrefix}/managementKeySecretName`,
            RDS_CONNECTION_INFO_PS_NAME: `${config.deploymentPrefix}/LisaServeRagPGVectorConnectionInfo`,
            OPENSEARCH_ENDPOINT_PS_NAME: `${config.deploymentPrefix}/lisaServeRagRepositoryEndpoint`,
            RAG_DOCUMENT_TABLE: ragDocumentTable.tableName,
            RAG_SUB_DOCUMENT_TABLE: ragSubDocumentTable.tableName,
            LOG_LEVEL: config.logLevel,
            REGISTERED_REPOSITORIES_PS_NAME: registeredRepositoriesParamName,
            REGISTERED_REPOSITORIES_PS_PREFIX: `${config.deploymentPrefix}/LisaServeRagConnectionInfo/`,
            RESTAPI_SSL_CERT_ARN: config.restApiConfig.sslCertIamArn || '',
        };

        // Create KMS key for environment variable encryption
        const kmsKey = new kms.Key(this, 'EnvironmentEncryptionKey', {
            enableKeyRotation: true,
            description: 'Key for encrypting Lambda environment variables'
        });

        const policyStatements = this.createPolicy(pipelineConfig.s3Bucket, ragDocumentTable, ragSubDocumentTable, config.deploymentPrefix);

         // Create the ingest documents function with S3 permissions
         const deleteDocumentsFunction = new Function(this, 'pipelineDeleteDocumentsFunc', {
             runtime: getDefaultRuntime(),
             handler: 'repository.pipeline_delete_document.lambda_handler',
             code: Code.fromAsset('./lambda'),
             timeout: LAMBDA_TIMEOUT,
             memorySize: LAMBDA_MEMORY,
             vpc: vpc!.vpc,
             environment: environment,
             environmentEncryption: kmsKey,
             layers: layers,
             initialPolicy: policyStatements
         });

         // Create a Step Function task to invoke the Lambda
         const invokeTask = new tasks.LambdaInvoke(this, 'InvokeDeleteDocumentLambda', {
             lambdaFunction: deleteDocumentsFunction,
             outputPath: '$.Payload',
         });

         // Create the state machine
         const stateMachine = new sfn.StateMachine(this, 'DeleteProcessingStateMachine', {
             definitionBody: DefinitionBody.fromChainable(
                 invokeTask
                     .addCatch(new sfn.Fail(this, 'FailState', {
                         cause: 'Lambda function failed to process delete event',
                         error: 'DeleteProcessingError',
                     }))
                     .next(
                         new sfn.Succeed(this, 'SuccessState', {
                             comment: 'Delete processing completed successfully',
                         }),
                     ),
             ),
             // timeout: Duration.minutes(5),
             tracingEnabled: true,
         });

         // Create EventBridge rule for S3 delete events
         const eventPattern: EventPattern = {
             source: ['aws.s3'],
             detail: this.getBucketDetails(pipelineConfig.s3Bucket, pipelineConfig.s3Prefix)
         };

         // Create the rule to trigger the state machine
         new Rule(this, 'S3DeleteRule', {
             eventPattern,
             targets: [new SfnStateMachine(stateMachine, {
                 input: RuleTargetInput.fromObject({
                     'detail-type': EventField.detailType,
                     detail: EventField.fromPath('$.detail'),
                     bucket: pipelineConfig.s3Bucket,
                     prefix: pipelineConfig.s3Prefix,
                     object: EventField.fromPath('$.detail.object.key'),
                     time: EventField.time,
                     source: EventField.source,
                     region: EventField.region,
                     trigger: 'event',
                 }),
             })],
         });
     }

     getBucketDetails(s3Bucket:string, s3Prefix: string): [key: string] {
        // Create S3 event trigger with complete event pattern and transform input
        const detail: any = {
            eventName: ['DeleteObject'],
            eventSource: ['s3.amazonaws.com'],
            bucket: {
                name: [s3Bucket]
            }
        };

        // Add prefix filter if specified and not root
        if (s3Prefix && s3Prefix !== '/') {
            detail.object = {
                key: [{
                    prefix: s3Prefix
                }]
            };
        }

        return detail;
     }

     createPolicy(s3Bucket:string, ragDocumentTable: any, ragSubDocumentTable: any, deploymentPrefix?: string){
        // Create S3 policy statement for both functions
        const s3PolicyStatement = new PolicyStatement({
            effect: Effect.ALLOW,
            actions: ['s3:GetObject', 's3:ListBucket'],
            resources: [
                `arn:${cdk.Aws.PARTITION}:s3:::${s3Bucket}`,
                `arn:${cdk.Aws.PARTITION}:s3:::${s3Bucket}/*`
            ]
        });
        // Allow DynamoDB Read/Write to RAG Document Table
        const dynamoPolicyStatement = new PolicyStatement({
            effect: Effect.ALLOW,
            actions: [
                'dynamodb:BatchGetItem',
                'dynamodb:GetItem',
                'dynamodb:Query',
                'dynamodb:Scan',
                'dynamodb:BatchWriteItem',
                'dynamodb:PutItem',
                'dynamodb:UpdateItem',
            ],
            resources: [
                ragDocumentTable.tableArn,
                `${ragDocumentTable.tableArn}/index/*`,
                ragSubDocumentTable.tableArn,
                `${ragSubDocumentTable.tableArn}/index/*`
            ]
        });

        const ssmPolicy = new PolicyStatement({
            effect: Effect.ALLOW,
            actions: ['ssm:GetParameter'],
            resources: [
                `arn:${cdk.Aws.PARTITION}:ssm:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:parameter${deploymentPrefix}/LisaServeRagPGVectorConnectionInfo`,
                `arn:${cdk.Aws.PARTITION}:ssm:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:parameter${deploymentPrefix}/lisaServeRagRepositoryEndpoint`,
                `arn:${cdk.Aws.PARTITION}:ssm:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:parameter${deploymentPrefix}/lisaServeRestApiUri`,
                `arn:${cdk.Aws.PARTITION}:ssm:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:parameter${deploymentPrefix}/managementKeySecretName`,
                `arn:${cdk.Aws.PARTITION}:ssm:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:parameter${deploymentPrefix}/registeredRepositories`,
                `arn:${cdk.Aws.PARTITION}:ssm:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:parameter${deploymentPrefix}/LisaServeRagConnectionInfo/*`,
            ],
        })

        const secretsManagerPolicy = new PolicyStatement({
            effect: Effect.ALLOW,
            actions: ['secretsmanager:GetSecretValue'],
            resources: ['*']
        })

        // Create array of policy statements
        const policyStatements = [s3PolicyStatement, dynamoPolicyStatement, ssmPolicy, secretsManagerPolicy];

        return policyStatements;
     }
 }

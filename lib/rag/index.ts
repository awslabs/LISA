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

import path from 'path';

import { PythonLayerVersion } from '@aws-cdk/aws-lambda-python-alpha';
import { CfnOutput, RemovalPolicy, Stack, StackProps } from 'aws-cdk-lib';
import { IAuthorizer } from 'aws-cdk-lib/aws-apigateway';
import { ISecurityGroup } from 'aws-cdk-lib/aws-ec2';
import { Code, ILayerVersion, LayerVersion } from 'aws-cdk-lib/aws-lambda';
import { Bucket, HttpMethods } from 'aws-cdk-lib/aws-s3';
import { AttributeType, BillingMode, StreamViewType, Table, TableEncryption } from 'aws-cdk-lib/aws-dynamodb';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';

import { RepositoryApi } from './api/repository';
import { ARCHITECTURE } from '../core';
import { Layer } from '../core/layers';
import { createCdkId } from '../core/utils';
import { Vpc } from '../networking/vpc';
import { BaseProps } from '../schema';
import { SecurityGroupEnum } from '../core/iam/SecurityGroups';
import { SecurityGroupFactory } from '../networking/vpc/security-group-factory';
import { Roles } from '../core/iam/roles';
import { getDefaultRuntime } from '../api-base/utils';
import { VectorStoreCreatorStack as VectorStoreCreator } from './vector-store/vector-store-creator';
import { IngestPipelineStateMachine } from './state_machine/ingest-pipeline';
import { DeletePipelineStateMachine } from './state_machine/delete-pipeline';
import { Role } from 'aws-cdk-lib/aws-iam';

const HERE = path.resolve(__dirname);
const RAG_LAYER_PATH = path.join(HERE, 'layer');
const SDK_PATH: string = path.resolve(HERE, '..', '..', 'lisa-sdk');

type CustomLisaRagStackProps = {
    authorizer: IAuthorizer;
    endpointUrl: StringParameter;
    modelsPs: StringParameter;
    restApiId: string;
    rootResourceId: string;
    securityGroups: ISecurityGroup[];
    vpc: Vpc;
} & BaseProps;

type LisaRagStackProps = CustomLisaRagStackProps & StackProps;

/**
 * LisaChat RAG stack.
 */
export class LisaRagStack extends Stack {
    /**
   * @param {Construct} scope - The parent or owner of the construct.
   * @param {string} id - The unique identifier for the construct within its scope.
   * @param {LisaChatStackProps} props - Properties for the Stack.
   */
    constructor (scope: Construct, id: string, props: LisaRagStackProps) {
        super(scope, id, props);

        const { authorizer, config, endpointUrl, modelsPs, restApiId, rootResourceId, securityGroups, vpc } = props;

        // Get common layer based on arn from SSM due to issues with cross stack references
        const commonLambdaLayer = LayerVersion.fromLayerVersionArn(
            this,
            'rag-common-lambda-layer',
            StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/layerVersion/common`),
        );

        const bucket = new Bucket(this, createCdkId(['LISA', 'RAG', config.deploymentName, config.deploymentStage]), {
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

        const ragTableName = createCdkId([config.deploymentName, 'RagDocumentTable']);
        const docMetaTable = new Table(this, ragTableName, {
            partitionKey: {
                name: 'pk', // Composite of repo/collection ids
                type: AttributeType.STRING,
            },
            sortKey: {
                name: 'document_id',
                type: AttributeType.STRING
            },
            billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption: dynamodb.TableEncryption.AWS_MANAGED,
            removalPolicy: config.removalPolicy,
        });
        docMetaTable.addGlobalSecondaryIndex({
            indexName: 'document_index',
            partitionKey: {
                name: 'document_id',
                type: AttributeType.STRING,
            }
        });
        docMetaTable.addGlobalSecondaryIndex({
            indexName: 'repository_index',
            partitionKey: {
                name: 'repository_id',
                type: AttributeType.STRING,
            }
        });
        const subDocTable = new Table(this, createCdkId([config.deploymentName, 'RagSubDocumentTable']), {
            partitionKey: {
                name: 'document_id',
                type: AttributeType.STRING,
            },
            sortKey: {
                name: 'sk',
                type: AttributeType.STRING
            },
            billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption: dynamodb.TableEncryption.AWS_MANAGED,
            removalPolicy: config.removalPolicy,
        });

        const connectionParamName = 'LisaServeRagConnectionInfo';
        const baseEnvironment: Record<string, string> = {
            REGISTERED_MODELS_PS_NAME: modelsPs.parameterName,
            BUCKET_NAME: bucket.bucketName,
            CHUNK_SIZE: config.ragFileProcessingConfig!.chunkSize.toString(),
            CHUNK_OVERLAP: config.ragFileProcessingConfig!.chunkOverlap.toString(),
            LISA_API_URL_PS_NAME: endpointUrl.parameterName,
            REST_API_VERSION: 'v2',
            RAG_DOCUMENT_TABLE: docMetaTable.tableName,
            RAG_SUB_DOCUMENT_TABLE: subDocTable.tableName,
            ADMIN_GROUP: config.authConfig!.adminGroup,
            REGISTERED_REPOSITORIES_PS_NAME: `${config.deploymentPrefix}/registeredRepositories`,
            MANAGEMENT_KEY_SECRET_NAME_PS: `${config.deploymentPrefix}/managementKeySecretName`,
            RDS_CONNECTION_INFO_PS_NAME: `${config.deploymentPrefix}/${connectionParamName}`,
            OPENSEARCH_ENDPOINT_PS_NAME: `${config.deploymentPrefix}/lisaServeRagRepositoryEndpoint`,
            REGISTERED_REPOSITORIES_PS_PREFIX: `${config.deploymentPrefix}/LisaServeRagConnectionInfo/`,
            LOG_LEVEL: config.logLevel,
        };

        // Add REST API SSL Cert ARN if it exists to be used to verify SSL calls to REST API
        if (config.restApiConfig?.sslCertIamArn) {
            baseEnvironment['RESTAPI_SSL_CERT_ARN'] = config.restApiConfig?.sslCertIamArn;
        }

        const lambdaRole = Role.fromRoleArn(
            this,
            Roles.RAG_LAMBDA_EXECUTION_ROLE,
            StringParameter.valueForStringParameter(
                this,
                `${config.deploymentPrefix}/roles/${createCdkId([config.deploymentName, Roles.RAG_LAMBDA_EXECUTION_ROLE])}`,
            ),
        );

        bucket.grantRead(lambdaRole);
        bucket.grantPut(lambdaRole);
        bucket.grantDelete(lambdaRole);

        // Build RAG Lambda layer
        const ragLambdaLayer = new Layer(this, 'RagLayer', {
            config: config,
            path: RAG_LAYER_PATH,
            description: 'Lambad dependencies for RAG API',
            architecture: ARCHITECTURE,
            autoUpgrade: true,
            assetPath: config.lambdaLayerAssets?.ragLayerPath,
        });
        new StringParameter(this, createCdkId([config.deploymentName, config.deploymentStage, 'RagLayer']), {
            parameterName: `${config.deploymentPrefix}/layerVersion/rag`,
            stringValue: ragLambdaLayer.layer.layerVersionArn
        });

        // Build SDK Layer
        let sdkLambdaLayer: ILayerVersion;
        if (config.lambdaLayerAssets?.sdkLayerPath) {
            sdkLambdaLayer = new LayerVersion(this, 'SdkLayer', {
                code: Code.fromAsset(config.lambdaLayerAssets?.sdkLayerPath),
                compatibleRuntimes: [getDefaultRuntime()],
                removalPolicy: config.removalPolicy,
                description: 'LISA SDK common layer',
            });
        } else {
            sdkLambdaLayer = new PythonLayerVersion(this, 'SdkLayer', {
                entry: SDK_PATH,
                compatibleRuntimes: [getDefaultRuntime()],
                removalPolicy: config.removalPolicy,
                description: 'LISA SDK common layer',
            });
        }
        const sdkSsm = new StringParameter(this, createCdkId([config.deploymentName, config.deploymentStage, 'SdkLayer']), {
            parameterName: `${config.deploymentPrefix}/layerVersion/sdk`,
            stringValue: sdkLambdaLayer.layerVersionArn
        });

        // create a security group for opensearch
        const openSearchSg = SecurityGroupFactory.createSecurityGroup(
            this,
            config.securityGroupConfig?.openSearchSecurityGroupId,
            SecurityGroupEnum.OPEN_SEARCH_SG,
            config.deploymentName,
            vpc.vpc,
            'RAG OpenSearch domain',
        );

        if (!config.securityGroupConfig?.openSearchSecurityGroupId) {
            SecurityGroupFactory.addIngress(openSearchSg, SecurityGroupEnum.OPEN_SEARCH_SG, vpc.vpc, 80, vpc.subnetSelection?.subnets);
            SecurityGroupFactory.addIngress(openSearchSg, SecurityGroupEnum.OPEN_SEARCH_SG, vpc.vpc, 443, vpc.subnetSelection?.subnets);
        }

        new StringParameter(this, createCdkId(['openSearchSecurityGroupId', 'StringParameter']), {
            parameterName: `${config.deploymentPrefix}/openSearchSecurityGroupId`,
            stringValue: openSearchSg.securityGroupId,
            description: 'Security Group ID for OpenSearch domain',
        });

        // Create new DB and SG
        const pgvectorSg = SecurityGroupFactory.createSecurityGroup(
            this,
            config.securityGroupConfig?.pgVectorSecurityGroupId,
            SecurityGroupEnum.PG_VECTOR_SG,
            undefined,
            vpc.vpc,
            'RAG PGVector database',
        );

        // Add default ingress port to SG
        if (!config.securityGroupConfig?.pgVectorSecurityGroupId) {
            SecurityGroupFactory.addIngress(pgvectorSg, SecurityGroupEnum.PG_VECTOR_SG, vpc.vpc, 5432, vpc.subnetSelection?.subnets);
        }

        new StringParameter(this, createCdkId(['pgvectorSecurityGroupId', 'StringParameter']), {
            parameterName: `${config.deploymentPrefix}/pgvectorSecurityGroupId`,
            stringValue: pgvectorSg.securityGroupId,
            description: 'Security Group ID for PGVector database',
        });

        const ragRepositoryConfigTable = new Table(this, createCdkId(['RagRepositoryConfig', 'Table']), {
            tableName: `${config.deploymentName}-${config.deploymentStage}-rag-repository-config`,
            partitionKey: {
                name: 'repositoryId',
                type: AttributeType.STRING
            },
            removalPolicy: RemovalPolicy.RETAIN_ON_UPDATE_OR_DELETE,
            billingMode: BillingMode.PAY_PER_REQUEST,
            pointInTimeRecovery: true,
            timeToLiveAttribute: 'ttl',
            stream: StreamViewType.NEW_AND_OLD_IMAGES,
            encryption: TableEncryption.AWS_MANAGED,
        });
        ragRepositoryConfigTable.grantReadWriteData(lambdaRole);
        const ragVectorStoreTable = new CfnOutput(this, createCdkId([config.deploymentPrefix, 'RagVectorStoreTable']), {
            key: 'ragVectorStoreTable',
            value: ragRepositoryConfigTable.tableArn
        });

        baseEnvironment['LISA_RAG_VECTOR_STORE_TABLE'] = ragRepositoryConfigTable.tableName;
        baseEnvironment['LISA_RAG_CREATE_STATE_MACHINE_ARN_PARAMETER'] = `${config.deploymentPrefix}/vectorstorecreator/statemachine/create`;
        baseEnvironment['LISA_RAG_DELETE_STATE_MACHINE_ARN_PARAMETER'] = `${config.deploymentPrefix}/vectorstorecreator/statemachine/delete`;

        const ingestPipeline = new IngestPipelineStateMachine(this, 'IngestPipelineStateMachine', {
            config,
            baseEnvironment,
            ragDocumentTable: docMetaTable,
            ragSubDocumentTable: subDocTable,
            layers: [commonLambdaLayer, ragLambdaLayer.layer, sdkLambdaLayer],
            vpc
        });
        ingestPipeline.node.addDependency(sdkSsm);

        const deletePipeline = new DeletePipelineStateMachine(this, 'DeletePipelineStateMachine', {
            baseEnvironment,
            config,
            vpc,
            layers: [commonLambdaLayer, ragLambdaLayer.layer, sdkLambdaLayer],
            ragDocumentTable: docMetaTable,
            ragSubDocumentTable: subDocTable,
        });
        deletePipeline.node.addDependency(sdkSsm);

        const vectorStoreCreator = new VectorStoreCreator(this, 'VectorStoreCreatorStack', {
            config,
            vpc,
            ragVectorStoreTable,
            stackName: createCdkId([config.appName, config.deploymentName, config.deploymentStage, 'vectorstore-creator']),
            baseEnvironment,
        });
        vectorStoreCreator.node.addDependency(sdkSsm);


        // Add REST API Lambdas to APIGW
        new RepositoryApi(this, 'RepositoryApi', {
            authorizer,
            baseEnvironment,
            config,
            vpc: vpc,
            commonLayers: [commonLambdaLayer, ragLambdaLayer.layer, sdkLambdaLayer],
            restApiId,
            rootResourceId,
            securityGroups,
            lambdaExecutionRole: lambdaRole,
        });

        modelsPs.grantRead(lambdaRole);
        endpointUrl.grantRead(lambdaRole);
        docMetaTable.grantReadWriteData(lambdaRole);
        subDocTable.grantReadWriteData(lambdaRole);
    }
}

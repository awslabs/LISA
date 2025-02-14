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

import { CfnOutput, RemovalPolicy, Stack, StackProps } from 'aws-cdk-lib';
import { IAuthorizer } from 'aws-cdk-lib/aws-apigateway';
import { ISecurityGroup } from 'aws-cdk-lib/aws-ec2';
import { ILayerVersion, LayerVersion } from 'aws-cdk-lib/aws-lambda';
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
import { BaseProps, Config } from '../schema';
import { SecurityGroupEnum } from '../core/iam/SecurityGroups';
import { SecurityGroupFactory } from '../networking/vpc/security-group-factory';
import { Roles } from '../core/iam/roles';
import { VectorStoreCreatorStack as VectorStoreCreator } from './vector-store/vector-store-creator';
import { IngestPipelineStateMachine } from './state_machine/ingest-pipeline';
import { DeletePipelineStateMachine } from './state_machine/delete-pipeline';
import { AnyPrincipal, CfnServiceLinkedRole, Effect, IRole, PolicyStatement, Role } from 'aws-cdk-lib/aws-iam';
import { IAMClient, ListRolesCommand } from '@aws-sdk/client-iam';
import { RagRepositoryType } from '../configSchema';
import { Domain, EngineVersion, IDomain } from 'aws-cdk-lib/aws-opensearchservice';
import { ISecret, Secret } from 'aws-cdk-lib/aws-secretsmanager';
import { Credentials, DatabaseInstance, DatabaseInstanceEngine } from 'aws-cdk-lib/aws-rds';
import { LegacyIngestPipelineStateMachine } from './state_machine/legacy-ingest-pipeline';

const HERE = path.resolve(__dirname);
const RAG_LAYER_PATH = path.join(HERE, 'layer');

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

    // Used to link service role if OpenSeach is used
    openSearchRegion?: string;

    /**
   * @param {Construct} scope - The parent or owner of the construct.
   * @param {string} id - The unique identifier for the construct within its scope.
   * @param {LisaChatStackProps} props - Properties for the Stack.
   */
    constructor (scope: Construct, id: string, props: LisaRagStackProps) {
        super(scope, id, props);

        const { authorizer, config, endpointUrl, modelsPs, restApiId, rootResourceId, securityGroups, vpc } = props;


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

        const baseEnvironment: Record<string, string> = {
            REGISTERED_MODELS_PS_NAME: modelsPs.parameterName,
            BUCKET_NAME: bucket.bucketName,
            CHUNK_SIZE: config.ragFileProcessingConfig!.chunkSize.toString(),
            CHUNK_OVERLAP: config.ragFileProcessingConfig!.chunkOverlap.toString(),
            LISA_API_URL_PS_NAME: endpointUrl.parameterName,
            REST_API_VERSION: 'v2',
            RAG_DOCUMENT_TABLE: docMetaTable.tableName,
            RAG_SUB_DOCUMENT_TABLE: subDocTable.tableName,
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

        // Get common layer based on arn from SSM due to issues with cross stack references
        const commonLambdaLayer = LayerVersion.fromLayerVersionArn(
            this,
            'rag-common-lambda-layer',
            StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/layerVersion/common`),
        );

        const sdkLayer = LayerVersion.fromLayerVersionArn(
            this,
            'rag-sdk-lambda-layer',
            StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/layerVersion/sdk`),
        );
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
        const layers = [commonLambdaLayer, ragLambdaLayer.layer, sdkLayer];


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
        new IngestPipelineStateMachine(this, 'IngestPipelineStateMachine', {
            config,
            baseEnvironment,
            ragDocumentTable: docMetaTable,
            ragSubDocumentTable: subDocTable,
            layers,
            vpc
        });

        new DeletePipelineStateMachine(this, 'DeletePipelineStateMachine', {
            baseEnvironment,
            config,
            vpc,
            layers,
            ragDocumentTable: docMetaTable,
            ragSubDocumentTable: subDocTable,
        });

        new VectorStoreCreator(this, 'VectorStoreCreatorStack', {
            config,
            vpc,
            ragVectorStoreTable,
            stackName: createCdkId([config.appName, config.deploymentName, config.deploymentStage, 'vectorstore-creator']),
            baseEnvironment,
            layers
        });

        this.legacyRepositories(
            config,
            vpc,
            baseEnvironment,
            { common: commonLambdaLayer, rag: ragLambdaLayer.layer, sdk: sdkLayer},
            lambdaRole,
            docMetaTable,
            subDocTable
        );

        // Add REST API Lambdas to APIGW
        new RepositoryApi(this, 'RepositoryApi', {
            authorizer,
            baseEnvironment,
            config,
            vpc: vpc,
            commonLayers: layers,
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

    legacyRepositories (
        config: Config,
        vpc: Vpc,
        baseEnvironment: Record<string, string>,
        layers: {[key in 'common' | 'sdk' | 'rag']: ILayerVersion},
        lambdaRole: IRole,
        docMetaTable: dynamodb.ITable,
        subDocTable: dynamodb.ITable
    ) {
        const registeredRepositories = [];
        let pgvectorSg = undefined;
        let openSearchSg = undefined;
        const connectionParamName = 'LisaServeRagConnectionInfo';
        baseEnvironment['REGISTERED_REPOSITORIES_PS_PREFIX'] = `${config.deploymentPrefix}/${connectionParamName}/`;
        const registeredRepositoriesParamName = `${config.deploymentPrefix}/registeredRepositories`;

        for (const ragConfig of config.ragRepositories) {
            registeredRepositories.push({ repositoryId: ragConfig.repositoryId, repositoryName: ragConfig.repositoryName, type: ragConfig.type, allowedGroups: ragConfig.allowedGroups });

            // Create opensearch cluster for RAG
            if (ragConfig.type === RagRepositoryType.OPENSEARCH && ragConfig.opensearchConfig) {
                if (!openSearchSg) {

                    openSearchSg = SecurityGroupFactory.createSecurityGroup(
                        this,
                        config.securityGroupConfig?.openSearchSecurityGroupId,
                        SecurityGroupEnum.OPEN_SEARCH_SG,
                        config.deploymentName,
                        vpc.vpc,
                        'RAG OpenSearch domain',
                    );

                    if (!config.securityGroupConfig?.openSearchSecurityGroupId) {
                        SecurityGroupFactory.legacyAddIngress(openSearchSg, SecurityGroupEnum.OPEN_SEARCH_SG, vpc, config, 80);
                        SecurityGroupFactory.legacyAddIngress(openSearchSg, SecurityGroupEnum.OPEN_SEARCH_SG, vpc, config, 443);
                    }
                }

                let openSearchDomain: IDomain;

                if ('endpoint' in ragConfig.opensearchConfig) {
                    openSearchDomain = Domain.fromDomainEndpoint(
                        this,
                        'ExistingOpenSearchDomain',
                        ragConfig.opensearchConfig.endpoint,
                    );
                } else {
                    // Service-linked role that Amazon OpenSearch Service will use
                    this.openSearchRegion = config.region;

                    openSearchDomain = new Domain(this, createCdkId(['LisaServeRagRepository', ragConfig.repositoryId]), {
                        domainName: ['lisa-rag', ragConfig.repositoryId].join('-'),
                        // 2.9 is the latest available in ADC regions as of 1/11/24
                        version: EngineVersion.OPENSEARCH_2_9,
                        enableVersionUpgrade: true,
                        vpc: vpc.vpc,
                        ...(vpc.subnetSelection && {vpcSubnets: [vpc.subnetSelection]}),
                        ebs: {
                            enabled: true,
                            volumeSize: ragConfig.opensearchConfig.volumeSize,
                            volumeType: ragConfig.opensearchConfig.volumeType,
                        },
                        zoneAwareness: {
                            availabilityZoneCount: vpc.vpc.privateSubnets.length,
                            enabled: true,
                        },
                        capacity: {
                            dataNodes: ragConfig.opensearchConfig.dataNodes,
                            dataNodeInstanceType: ragConfig.opensearchConfig.dataNodeInstanceType,
                            masterNodes: ragConfig.opensearchConfig.masterNodes,
                            masterNodeInstanceType: ragConfig.opensearchConfig.masterNodeInstanceType,
                            multiAzWithStandbyEnabled: ragConfig.opensearchConfig.multiAzWithStandby,
                        },
                        accessPolicies: [
                            new PolicyStatement({
                                actions: ['es:*'],
                                resources: ['*'],
                                effect: Effect.ALLOW,
                                principals: [new AnyPrincipal()],
                            }),
                        ],
                        removalPolicy: RemovalPolicy.DESTROY,
                        securityGroups: [openSearchSg],
                    });
                }

                // Rag API task execution role will read and write
                openSearchDomain.grantIndexReadWrite('*', lambdaRole);
                openSearchDomain.grantPathReadWrite('*', lambdaRole);
                openSearchDomain.grantReadWrite(lambdaRole);

                new CfnOutput(this, createCdkId(['opensearchRagRepositoryEndpoint', ragConfig.repositoryId]), {
                    value: openSearchDomain.domainEndpoint,
                });

                const openSearchEndpointPs = new StringParameter(
                    this,
                    createCdkId([connectionParamName, ragConfig.repositoryId, 'StringParameter']),
                    {
                        parameterName: `${config.deploymentPrefix}/${connectionParamName}/${ragConfig.repositoryId}`,
                        stringValue: openSearchDomain.domainEndpoint,
                        description: 'Endpoint for LISA Serve OpenSearch Rag Repository',
                    },
                );

                // Add explicit dependency on OpenSearch Domain being created
                openSearchEndpointPs.node.addDependency(openSearchDomain);
                openSearchEndpointPs.grantRead(lambdaRole);
            } else if (ragConfig.type === RagRepositoryType.PGVECTOR && ragConfig.rdsConfig) {
                let rdsPasswordSecret: ISecret;
                let rdsConnectionInfoPs: StringParameter;
                // if dbHost and passwordSecretId are defined, then connect to DB with existing params
                if (!!ragConfig.rdsConfig.dbHost && !!ragConfig.rdsConfig.passwordSecretId) {
                    rdsConnectionInfoPs = new StringParameter(this, createCdkId([connectionParamName, ragConfig.repositoryId, 'StringParameter']), {
                        parameterName: `${config.deploymentPrefix}/${connectionParamName}/${ragConfig.repositoryId}`,
                        stringValue: JSON.stringify(ragConfig.rdsConfig),
                        description: 'Connection info for LISA Serve PGVector database',
                    });
                    rdsPasswordSecret = Secret.fromSecretNameV2(
                        this,
                        createCdkId([config.deploymentName, ragConfig.repositoryId, 'RagRDSPwdSecret']),
                        ragConfig.rdsConfig.passwordSecretId,
                    );
                } else {
                    // only create one security group
                    if (!pgvectorSg) {
                        // Create new DB and SG
                        pgvectorSg = SecurityGroupFactory.createSecurityGroup(
                            this,
                            config.securityGroupConfig?.pgVectorSecurityGroupId,
                            SecurityGroupEnum.PG_VECTOR_SG,
                            undefined,
                            vpc.vpc,
                            'RAG PGVector database',
                        );

                        if (!config.securityGroupConfig?.pgVectorSecurityGroupId) {
                            SecurityGroupFactory.legacyAddIngress(pgvectorSg, SecurityGroupEnum.PG_VECTOR_SG, vpc, config, ragConfig.rdsConfig.dbPort);
                        }
                    }

                    const username = ragConfig.rdsConfig.username;
                    const dbCreds = Credentials.fromGeneratedSecret(username);
                    const pgvector_db = new DatabaseInstance(this, createCdkId([ragConfig.repositoryId, 'PGVectorDB']), {
                        engine: DatabaseInstanceEngine.POSTGRES,
                        vpc: vpc.vpc,
                        subnetGroup: vpc.subnetGroup,
                        credentials: dbCreds,
                        securityGroups: [pgvectorSg],
                        removalPolicy: RemovalPolicy.DESTROY,
                    });
                    rdsPasswordSecret = pgvector_db.secret!;
                    rdsConnectionInfoPs = new StringParameter(this, createCdkId([connectionParamName, ragConfig.repositoryId, 'StringParameter']), {
                        parameterName: `${config.deploymentPrefix}/${connectionParamName}/${ragConfig.repositoryId}`,
                        stringValue: JSON.stringify({
                            username: username,
                            passwordSecretId: rdsPasswordSecret.secretName,
                            dbHost: pgvector_db.dbInstanceEndpointAddress,
                            dbName: ragConfig.rdsConfig.dbName,
                            dbPort: ragConfig.rdsConfig.dbPort,
                        }),
                        description: 'Connection info for LISA Serve PGVector database',
                    });
                }
                rdsPasswordSecret.grantRead(lambdaRole);
                rdsConnectionInfoPs.grantRead(lambdaRole);
            }

            // Create ingest pipeline state machines for each pipeline config
            console.log('[DEBUG] Checking pipelines configuration:', {
                hasPipelines: !!ragConfig.pipelines,
                pipelinesLength: ragConfig.pipelines?.length || 0
            });

            if (ragConfig.pipelines) {
                ragConfig.pipelines.forEach((pipelineConfig, index) => {
                    console.log(`[DEBUG] Creating pipeline ${index}:`, {
                        pipelineConfig: JSON.stringify(pipelineConfig, null, 2)
                    });

                    try {
                        // Create a unique ID for each pipeline using repository ID and index
                        const pipelineId = `IngestPipeline-${ragConfig.repositoryId}-${index}`;
                        new LegacyIngestPipelineStateMachine(this, pipelineId, {
                            config,
                            vpc,
                            pipelineConfig,
                            rdsConfig: ragConfig.rdsConfig,
                            repositoryId: ragConfig.repositoryId,
                            type: ragConfig.type,
                            layers: [layers.common, layers.rag, layers.sdk],
                            registeredRepositoriesParamName,
                            ragDocumentTable: docMetaTable,
                            ragSubDocumentTable: subDocTable,
                        });
                        console.log(`[DEBUG] Successfully created pipeline ${index}`);
                    } catch (error) {
                        console.error(`[ERROR] Failed to create pipeline ${index}:`, error);
                        throw error; // Re-throw to ensure CDK deployment fails
                    }
                });
            }
        }

        // not needed because things will be stored in the database now
        // // Create Parameter Store entry with RAG repositories
        // const ragRepositoriesParam = new StringParameter(this, createCdkId([config.deploymentName, 'RagReposSP']), {
        //     parameterName: registeredRepositoriesParamName,
        //     stringValue: JSON.stringify(registeredRepositories),
        //     description: 'Serialized JSON of registered RAG repositories',
        // });
    }

    /**
     * This method links the OpenSearch Service role to the service-linked role if it exists.
     * If the role doesn't exist, it will be created.
     */
    async linkServiceRole () {
        // Only link open search role if being used
        if (!this.openSearchRegion) {
            return;
        }

        const iam = new IAMClient({
            region: this.openSearchRegion
        });
        const response = await iam.send(
            new ListRolesCommand({
                PathPrefix: '/aws-service-role/opensearchservice.amazonaws.com/',
            }),
        );

        // Only if the role for OpenSearch Service doesn't exist, it will be created.
        if (response.Roles && response.Roles?.length === 0) {
            new CfnServiceLinkedRole(this, 'OpensearchServiceLinkedRole', {
                awsServiceName: 'opensearchservice.amazonaws.com',
            });
        }
    }
}

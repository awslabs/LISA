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
import { CfnOutput, RemovalPolicy, Stack, StackProps } from 'aws-cdk-lib';
import { IAuthorizer } from 'aws-cdk-lib/aws-apigateway';
import { ISecurityGroup } from 'aws-cdk-lib/aws-ec2';
import { ILayerVersion, LayerVersion } from 'aws-cdk-lib/aws-lambda';
import { BlockPublicAccess, Bucket, BucketEncryption, HttpMethods } from 'aws-cdk-lib/aws-s3';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import { AttributeType, BillingMode, StreamViewType, Table, TableEncryption } from 'aws-cdk-lib/aws-dynamodb';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';

import { RepositoryApi } from './api/repository';
import { ARCHITECTURE } from '../core';
import { Layer } from '../core/layers';
import { createCdkId } from '../core/utils';
import { Vpc } from '../networking/vpc';
import { APP_MANAGEMENT_KEY, BaseProps, Config } from '../schema';
import { SecurityGroupEnum } from '../core/iam/SecurityGroups';
import { SecurityGroupFactory } from '../networking/vpc/security-group-factory';
import { Roles } from '../core/iam/roles';
import { VectorStoreCreatorStack as VectorStoreCreator } from './vector-store/vector-store-creator';
import { AnyPrincipal, CfnServiceLinkedRole, Effect, IRole, PolicyStatement, Role } from 'aws-cdk-lib/aws-iam';
import { IAMClient, ListRolesCommand } from '@aws-sdk/client-iam';
import { RagRepositoryConfig, RagRepositoryType } from '../schema';
import { Domain, EngineVersion, IDomain } from 'aws-cdk-lib/aws-opensearchservice';
import { ISecret, Secret } from 'aws-cdk-lib/aws-secretsmanager';
import { Credentials, DatabaseInstance, DatabaseInstanceEngine } from 'aws-cdk-lib/aws-rds';
import { LegacyIngestPipelineStateMachine } from './state_machine/legacy-ingest-pipeline';
import * as customResources from 'aws-cdk-lib/custom-resources';
import { marshall } from '@aws-sdk/util-dynamodb';
import * as readlineSync from 'readline-sync';
import { RAG_LAYER_PATH } from '../util';
import { IngestionStack } from './ingestion/ingestion-stack';
import { AwsCustomResource, PhysicalResourceId } from 'aws-cdk-lib/custom-resources';

export type LisaRagProps = {
    authorizer: IAuthorizer;
    endpointUrl?: StringParameter;
    modelsPs?: StringParameter;
    restApiId: string;
    rootResourceId: string;
    securityGroups: ISecurityGroup[];
    vpc: Vpc;
} & BaseProps & StackProps;

/**
 * Lisa RAG stack.
 */
export class LisaRagConstruct extends Construct {
    private readonly scope: Stack;
    // Used to link service role if OpenSeach is used
    openSearchRegion?: string;

    /**
   * @param {Stack} scope - The parent or owner of the construct.
   * @param {string} id - The unique identifier for the construct within its scope.
   * @param {LisaChatStackProps} props - Properties for the Stack.
   */
    constructor (scope: Stack, id: string, props: LisaRagProps) {
        super(scope, id);
        this.scope = scope;
        const { authorizer, config, restApiId, rootResourceId, securityGroups, vpc } = props;

        const endpointUrl = props.endpointUrl ?? StringParameter.fromStringParameterName(
            scope,
            createCdkId(['LisaRestApiUri', 'StringParameter']),
            `${config.deploymentPrefix}/lisaServeRestApiUri`,
        );

        const modelsPs = props.modelsPs ?? StringParameter.fromStringParameterName(
            scope,
            createCdkId(['RegisteredModels', 'StringParameter']),
            `${config.deploymentPrefix}/registeredModels`,
        );

        const bucketAccessLogsBucket = Bucket.fromBucketArn(scope, 'BucketAccessLogsBucket',
            StringParameter.valueForStringParameter(scope, `${config.deploymentPrefix}/bucket/bucket-access-logs`)
        );

        const bucket = new Bucket(scope, createCdkId(['LISA', 'RAG', config.deploymentName, config.deploymentStage]), {
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
            serverAccessLogsBucket: bucketAccessLogsBucket,
            serverAccessLogsPrefix: 'logs/rag-bucket/',
            blockPublicAccess: BlockPublicAccess.BLOCK_ALL,
            encryption: BucketEncryption.S3_MANAGED
        });

        const ragTableName = createCdkId([config.deploymentName, 'RagDocumentTable']);
        const docMetaTable = new Table(scope, ragTableName, {
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
            deletionProtection: config.removalPolicy !== RemovalPolicy.DESTROY,
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
        const subDocTable = new Table(scope, createCdkId([config.deploymentName, 'RagSubDocumentTable']), {
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
            deletionProtection: config.removalPolicy !== RemovalPolicy.DESTROY,
        });

        // Create Collections table
        const collectionsTableName = createCdkId([config.deploymentName, 'RagCollectionsTable']);
        const collectionsTable = new Table(scope, collectionsTableName, {
            partitionKey: {
                name: 'collectionId',
                type: AttributeType.STRING,
            },
            sortKey: {
                name: 'repositoryId',
                type: AttributeType.STRING
            },
            billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption: dynamodb.TableEncryption.AWS_MANAGED,
            removalPolicy: config.removalPolicy,
            deletionProtection: config.removalPolicy !== RemovalPolicy.DESTROY,
            timeToLiveAttribute: 'ttl',
        });

        // Add GSI for querying collections by repository
        collectionsTable.addGlobalSecondaryIndex({
            indexName: 'RepositoryIndex',
            partitionKey: {
                name: 'repositoryId',
                type: AttributeType.STRING,
            },
            sortKey: {
                name: 'createdAt',
                type: AttributeType.STRING,
            }
        });

        // Add GSI for filtering collections by status
        collectionsTable.addGlobalSecondaryIndex({
            indexName: 'StatusIndex',
            partitionKey: {
                name: 'repositoryId',
                type: AttributeType.STRING,
            },
            sortKey: {
                name: 'status',
                type: AttributeType.STRING,
            }
        });

        // Add GSI to document table for querying documents by collection
        docMetaTable.addGlobalSecondaryIndex({
            indexName: 'CollectionIndex',
            partitionKey: {
                name: 'collectionId',
                type: AttributeType.STRING,
            },
            sortKey: {
                name: 'createdAt',
                type: AttributeType.STRING,
            }
        });

        const modelTableNameStringParameter = StringParameter.fromStringParameterName(this, 'ModelTableNameStringParameter', `${config.deploymentPrefix}/modelTableName`);

        const baseEnvironment: Record<string, string> = {
            ADMIN_GROUP: config.authConfig!.adminGroup,
            BUCKET_NAME: bucket.bucketName,
            CHUNK_OVERLAP: config.ragFileProcessingConfig!.chunkOverlap.toString(),
            CHUNK_SIZE: config.ragFileProcessingConfig!.chunkSize.toString(),
            LISA_API_URL_PS_NAME: endpointUrl.parameterName,
            LISA_RAG_COLLECTIONS_TABLE: collectionsTable.tableName,
            LOG_LEVEL: config.logLevel,
            MANAGEMENT_KEY_SECRET_NAME_PS: `${config.deploymentPrefix}/${APP_MANAGEMENT_KEY}`,
            MODEL_TABLE_NAME: modelTableNameStringParameter.stringValue,
            RAG_DOCUMENT_TABLE: docMetaTable.tableName,
            RAG_SUB_DOCUMENT_TABLE: subDocTable.tableName,
            REGISTERED_MODELS_PS_NAME: modelsPs.parameterName,
            REGISTERED_REPOSITORIES_PS_PREFIX: `${config.deploymentPrefix}/LisaServeRagConnectionInfo/`,
            REGISTERED_REPOSITORIES_PS: `${config.deploymentPrefix}/registeredRepositories`,
            REST_API_VERSION: 'v2',
            TIKTOKEN_CACHE_DIR: '/tmp',
        };

        // Add REST API SSL Cert ARN if it exists to be used to verify SSL calls to REST API
        if (config.restApiConfig?.sslCertIamArn) {
            baseEnvironment['RESTAPI_SSL_CERT_ARN'] = config.restApiConfig?.sslCertIamArn;
        }

        const lambdaRole = Role.fromRoleArn(
            this,
            Roles.RAG_LAMBDA_EXECUTION_ROLE,
            StringParameter.valueForStringParameter(
                scope,
                `${config.deploymentPrefix}/roles/${createCdkId([config.deploymentName, Roles.RAG_LAMBDA_EXECUTION_ROLE])}`,
            ),
        );

        bucket.grantRead(lambdaRole);
        bucket.grantPut(lambdaRole);
        bucket.grantDelete(lambdaRole);

        // Get common layer based on arn from SSM due to issues with cross stack references
        const commonLambdaLayer = LayerVersion.fromLayerVersionArn(
            scope,
            'rag-common-lambda-layer',
            StringParameter.valueForStringParameter(scope, `${config.deploymentPrefix}/layerVersion/common`),
        );

        // Build RAG Lambda layer
        // Note: tiktoken and document processing deps moved to container-based batch ingestion
        const ragLambdaLayer = new Layer(scope, 'RagLayer', {
            config: config,
            path: RAG_LAYER_PATH,
            description: 'Lambda dependencies for RAG API',
            architecture: ARCHITECTURE,
            autoUpgrade: true,
            assetPath: config.lambdaLayerAssets?.ragLayerPath,
        });

        new StringParameter(scope, createCdkId([config.deploymentName, config.deploymentStage, 'RagLayer']), {
            parameterName: `${config.deploymentPrefix}/layerVersion/rag`,
            stringValue: ragLambdaLayer.layer.layerVersionArn
        });

        const layers = [commonLambdaLayer, ragLambdaLayer.layer];

        // create a security group for opensearch
        const openSearchSg = SecurityGroupFactory.createSecurityGroup(
            scope,
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

        new StringParameter(scope, createCdkId(['openSearchSecurityGroupId', 'StringParameter']), {
            parameterName: `${config.deploymentPrefix}/openSearchSecurityGroupId`,
            stringValue: openSearchSg.securityGroupId,
            description: 'Security Group ID for OpenSearch domain',
        });

        // Create new DB and SG
        const pgvectorSg = SecurityGroupFactory.createSecurityGroup(
            scope,
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

        new StringParameter(scope, createCdkId(['pgvectorSecurityGroupId', 'StringParameter']), {
            parameterName: `${config.deploymentPrefix}/pgvectorSecurityGroupId`,
            stringValue: pgvectorSg.securityGroupId,
            description: 'Security Group ID for PGVector database',
        });

        const ragRepositoryConfigTable = new Table(scope, createCdkId(['RagRepositoryConfig', 'Table']), {
            tableName: `${config.deploymentName}-${config.deploymentStage}-rag-repository-config`,
            partitionKey: {
                name: 'repositoryId',
                type: AttributeType.STRING
            },
            removalPolicy: config.removalPolicy,
            deletionProtection: config.removalPolicy !== RemovalPolicy.DESTROY,
            billingMode: BillingMode.PAY_PER_REQUEST,
            timeToLiveAttribute: 'ttl',
            stream: StreamViewType.NEW_AND_OLD_IMAGES,
            encryption: TableEncryption.AWS_MANAGED,
        });
        ragRepositoryConfigTable.grantReadWriteData(lambdaRole);
        const ragVectorStoreTable = new CfnOutput(scope, createCdkId([config.deploymentPrefix, 'RagVectorStoreTable']), {
            key: 'ragVectorStoreTable',
            value: ragRepositoryConfigTable.tableArn
        });

        // Create SSM parameter for vector store table name so other stacks can optionally reference it.
        new StringParameter(scope, createCdkId(['RagVectorStoreTableName', 'Parameter']), {
            parameterName: `${config.deploymentPrefix}/ragVectorStoreTableName`,
            stringValue: ragRepositoryConfigTable.tableName,
            description: 'RAG Vector Store (Repository Config) DynamoDB table name',
        });

        // Create SSM parameter for collections table name so other stacks can optionally reference it.
        new StringParameter(scope, createCdkId(['RagCollectionsTableName', 'Parameter']), {
            parameterName: `${config.deploymentPrefix}/ragCollectionsTableName`,
            stringValue: collectionsTable.tableName,
            description: 'RAG Collections DynamoDB table name',
        });

        baseEnvironment['LISA_RAG_VECTOR_STORE_TABLE'] = ragRepositoryConfigTable.tableName;
        baseEnvironment['LISA_RAG_CREATE_STATE_MACHINE_ARN_PARAMETER'] = `${config.deploymentPrefix}/vectorstorecreator/statemachine/create`;
        baseEnvironment['LISA_RAG_DELETE_STATE_MACHINE_ARN_PARAMETER'] = `${config.deploymentPrefix}/vectorstorecreator/statemachine/delete`;
        baseEnvironment['TIKTOKEN_CACHE_DIR'] = '/opt/python/TIKTOKEN_CACHE';

        // this modifies baseEnvironment and adds necessary environment variables
        new IngestionStack(scope, 'IngestionStack', {
            baseEnvironment,
            config,
            vpc,
            lambdaRole,
            layers,
        });

        this.legacyRepositories(
            config,
            vpc,
            baseEnvironment,
            { common: commonLambdaLayer, rag: ragLambdaLayer.layer },
            lambdaRole,
            docMetaTable,
            subDocTable,
            { pgvector: pgvectorSg, opensearch: openSearchSg },
            ragRepositoryConfigTable
        );

        // Add REST API Lambdas to APIGW
        new RepositoryApi(scope, 'RepositoryApi', {
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

        new VectorStoreCreator(scope, 'VectorStoreCreatorStack', {
            config,
            vpc,
            ragVectorStoreTable,
            stackName: createCdkId([config.appName, config.deploymentName, config.deploymentStage, 'vectorstore-creator']),
            baseEnvironment,
            layers
        });

        modelsPs.grantRead(lambdaRole);
        endpointUrl.grantRead(lambdaRole);
        docMetaTable.grantReadWriteData(lambdaRole);
        subDocTable.grantReadWriteData(lambdaRole);
        collectionsTable.grantReadWriteData(lambdaRole);
    }

    legacyRepositories (
        config: Config,
        vpc: Vpc,
        baseEnvironment: Record<string, string>,
        layers: { [key in 'common' | 'rag']: ILayerVersion },
        lambdaRole: IRole,
        docMetaTable: dynamodb.ITable,
        subDocTable: dynamodb.ITable,
        securityGroups: { [key in 'pgvector' | 'opensearch']: ISecurityGroup },
        ragRepositoryConfigTable: dynamodb.ITable
    ) {
        const registeredRepositories = [];
        const connectionParamName = 'LisaServeRagConnectionInfo';
        const registeredRepositoriesParamName = `${config.deploymentPrefix}/registeredRepositories`;

        const repositoryIds = (JSON.parse(process.env.RAG_REPOSITORIES || '[]') as RagRepositoryConfig[]).map((ragRepository: RagRepositoryConfig) => ragRepository.repositoryId);

        for (const ragConfig of config.ragRepositories) {
            if (!repositoryIds.includes(ragConfig.repositoryId)) {
                const warning = `\n\n[WARNING] ${ragConfig.repositoryId} ignored.\n\tAs of LISA 4.0 rag repositories can no longer be added via YAML.`;
                if (process.stdout.isTTY) {
                    readlineSync.keyInPause(warning);
                    console.log('\n\tContinuing deployment...');
                } else {
                    console.warn(warning);
                }
                continue;
            }

            registeredRepositories.push(ragConfig);

            // Create opensearch cluster for RAG
            if (ragConfig.type === RagRepositoryType.OPENSEARCH && ragConfig.opensearchConfig) {
                let openSearchDomain: IDomain;

                if ('endpoint' in ragConfig.opensearchConfig) {
                    openSearchDomain = Domain.fromDomainEndpoint(
                        this.scope,
                        'ExistingOpenSearchDomain',
                        ragConfig.opensearchConfig.endpoint,
                    );
                } else {
                    // Service-linked role that Amazon OpenSearch Service will use
                    this.openSearchRegion = config.region;

                    openSearchDomain = new Domain(this.scope, createCdkId(['LisaServeRagRepository', ragConfig.repositoryId]), {
                        domainName: ['lisa-rag', ragConfig.repositoryId].join('-'),
                        // 2.9 is the latest available in ADC regions as of 1/11/24
                        version: EngineVersion.OPENSEARCH_2_9,
                        enableVersionUpgrade: true,
                        vpc: vpc.vpc,
                        ...(vpc.subnetSelection && { vpcSubnets: [vpc.subnetSelection] }),
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
                        removalPolicy: config.removalPolicy,
                        securityGroups: [securityGroups.opensearch],
                    });
                }

                // Rag API task execution role will read and write
                openSearchDomain.grantIndexReadWrite('*', lambdaRole);
                openSearchDomain.grantPathReadWrite('*', lambdaRole);
                openSearchDomain.grantReadWrite(lambdaRole);

                new CfnOutput(this.scope, createCdkId(['opensearchRagRepositoryEndpoint', ragConfig.repositoryId]), {
                    value: openSearchDomain.domainEndpoint,
                });

                const configParam = { type: RagRepositoryType.OPENSEARCH, endpoint: openSearchDomain.domainEndpoint };
                const openSearchEndpointPs = new StringParameter(
                    this.scope,
                    createCdkId([connectionParamName, ragConfig.repositoryId, 'StringParameter']),
                    {
                        parameterName: `${config.deploymentPrefix}/${connectionParamName}/${ragConfig.repositoryId}`,
                        stringValue: JSON.stringify(configParam),
                        description: 'Endpoint for LISA Serve OpenSearch Rag Repository',
                    },
                );

                // Add explicit dependency on OpenSearch Domain being created
                openSearchEndpointPs.node.addDependency(openSearchDomain);
                openSearchEndpointPs.grantRead(lambdaRole);
            } else if (ragConfig.type === RagRepositoryType.PGVECTOR && ragConfig.rdsConfig) {
                // Determine authentication method - default to IAM auth (iamRdsAuth = false)
                const useIamAuth = config.iamRdsAuth ?? false;

                let rdsSecret: ISecret;
                let rdsConnectionInfoPs: StringParameter;
                let pgvector_db: DatabaseInstance | undefined;

                // if dbHost and passwordSecretId are defined, connect to existing DB
                if (ragConfig.rdsConfig.dbHost && ragConfig.rdsConfig.passwordSecretId) {
                    rdsConnectionInfoPs = new StringParameter(this.scope, createCdkId([connectionParamName, ragConfig.repositoryId, 'StringParameter']), {
                        parameterName: `${config.deploymentPrefix}/${connectionParamName}/${ragConfig.repositoryId}`,
                        stringValue: JSON.stringify({
                            username: ragConfig.rdsConfig?.username,
                            dbHost: ragConfig.rdsConfig?.dbHost,
                            dbName: ragConfig.rdsConfig?.dbName,
                            dbPort: ragConfig.rdsConfig?.dbPort,
                            type: RagRepositoryType.PGVECTOR,
                            // Include passwordSecretId only when using password auth
                            ...(!useIamAuth ? { passwordSecretId: ragConfig.rdsConfig?.passwordSecretId } : {})
                        }),
                        description: 'Connection info for LISA Serve PGVector database',
                    });
                    rdsSecret = Secret.fromSecretNameV2(
                        this.scope,
                        createCdkId([config.deploymentName, ragConfig.repositoryId, 'RagRDSSecret']),
                        ragConfig.rdsConfig.passwordSecretId,
                    );
                } else {
                    const username = ragConfig.rdsConfig.username;
                    const dbCreds = Credentials.fromGeneratedSecret(username);
                    pgvector_db = new DatabaseInstance(this.scope, createCdkId([ragConfig.repositoryId, 'PGVectorDB']), {
                        engine: DatabaseInstanceEngine.POSTGRES,
                        vpc: vpc.vpc,
                        subnetGroup: vpc.subnetGroup,
                        credentials: dbCreds,
                        iamAuthentication: useIamAuth, // Enable IAM auth when iamRdsAuth is false
                        securityGroups: [securityGroups.pgvector],
                        removalPolicy: config.removalPolicy,
                        deletionProtection: config.removalPolicy !== RemovalPolicy.DESTROY,
                    });
                    rdsSecret = pgvector_db.secret!;
                    rdsConnectionInfoPs = new StringParameter(this.scope, createCdkId([connectionParamName, ragConfig.repositoryId, 'StringParameter']), {
                        parameterName: `${config.deploymentPrefix}/${connectionParamName}/${ragConfig.repositoryId}`,
                        stringValue: JSON.stringify({
                            dbHost: pgvector_db.dbInstanceEndpointAddress,
                            dbName: ragConfig.rdsConfig.dbName,
                            dbPort: ragConfig.rdsConfig.dbPort,
                            type: RagRepositoryType.PGVECTOR,
                            username: username,
                            // Include passwordSecretId only when using password auth
                            ...(!useIamAuth ? { passwordSecretId: rdsSecret.secretName } : {})
                        }),
                        description: 'Connection info for LISA Serve PGVector database',
                    });

                    if (!useIamAuth) {
                        // Password auth: secret read access granted below (grantConnect requires IAM auth)
                    } else {
                        // IAM auth: manually grant rds-db:connect permission
                        // Note: We do NOT use pgvector_db.grantConnect() due to CDK bug #11851
                        // The grantConnect method generates incorrect ARN format (uses rds: instead of rds-db:)
                        // Per AWS docs: https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.IAMDBAuth.html
                        // The correct format is: arn:aws:rds-db:region:account-id:dbuser:DbiResourceId/db-user-name
                        lambdaRole.addToPrincipalPolicy(new PolicyStatement({
                            effect: Effect.ALLOW,
                            actions: ['rds-db:connect'],
                            resources: [
                                // Use wildcard for DbiResourceId since it's not available in CloudFormation
                                // Format: arn:aws:rds-db:region:account:dbuser:*/username
                                `arn:${config.partition}:rds-db:${config.region}:${config.accountNumber}:dbuser:*/${lambdaRole.roleName}`
                            ]
                        }));
                    }

                    // Update ragConfig with the endpoint address for use in AwsCustomResource
                    ragConfig.rdsConfig.dbHost = pgvector_db.dbInstanceEndpointAddress;
                }

                if (!useIamAuth) {
                    // Password auth: grant secret read access
                    rdsSecret.grantRead(lambdaRole);
                } else {
                    // Use the shared IAM auth setup Lambda from API Base stack
                    const iamAuthSetupFnArn = StringParameter.valueForStringParameter(
                        this.scope,
                        `${config.deploymentPrefix}/iamAuthSetupFnArn`
                    );

                    // Get the IAM auth setup Lambda role ARN from SSM to grant it permissions
                    const iamAuthSetupRoleArn = StringParameter.valueForStringParameter(
                        this.scope,
                        `${config.deploymentPrefix}/iamAuthSetupRoleArn`
                    );

                    // Import the IAM auth setup role to grant it secret permissions
                    const iamAuthSetupRole = Role.fromRoleArn(
                        this.scope,
                        createCdkId([ragConfig.repositoryId, 'IamAuthSetupRoleRef']),
                        iamAuthSetupRoleArn
                    );

                    // Grant the IAM auth setup Lambda role permission to read the bootstrap secret
                    rdsSecret.grantRead(iamAuthSetupRole);

                    // Run the shared IAM auth setup Lambda on create and update
                    // Pass parameters via payload since the Lambda is shared
                    // Use Stack.of(this.scope).toJsonString() to properly resolve CDK tokens in the payload
                    const lambdaInvokeParams = {
                        service: 'Lambda',
                        action: 'invoke',
                        physicalResourceId: PhysicalResourceId.of(createCdkId([ragConfig.repositoryId, 'CreateDbUserCustomResource'])),
                        parameters: {
                            FunctionName: iamAuthSetupFnArn,
                            Payload: Stack.of(this.scope).toJsonString({
                                secretArn: rdsSecret.secretArn,
                                dbHost: ragConfig.rdsConfig!.dbHost,
                                dbPort: ragConfig.rdsConfig!.dbPort,
                                dbName: ragConfig.rdsConfig!.dbName,
                                dbUser: ragConfig.rdsConfig!.username,
                                iamName: lambdaRole.roleName,
                            })
                        },
                    };

                    const createDbUserResource = new AwsCustomResource(this.scope, createCdkId([ragConfig.repositoryId, 'CreateDbUserCustomResource']), {
                        onCreate: lambdaInvokeParams,
                        onUpdate: lambdaInvokeParams,  // Also run on updates to ensure IAM user is created
                        policy: customResources.AwsCustomResourcePolicy.fromStatements([
                            new PolicyStatement({
                                effect: Effect.ALLOW,
                                actions: ['lambda:InvokeFunction'],
                                resources: [iamAuthSetupFnArn],
                            })
                        ]),
                    });

                    // Ensure the RDS instance is fully available before running IAM auth setup
                    // (only when we created a new RDS instance)
                    if (pgvector_db) {
                        createDbUserResource.node.addDependency(pgvector_db);
                    }
                }

                rdsConnectionInfoPs.grantRead(lambdaRole);
            } else {
                const error = `[ERROR] Invalid RAG configuratio for ${ragConfig.repositoryId}`;
                console.error(error);
                throw error;
            }

            const createOrUpdateParameters = {
                TableName: ragRepositoryConfigTable.tableName,
                Item: marshall({
                    repositoryId: ragConfig.repositoryId,
                    status: 'CREATE_COMPLETE',
                    config: ragConfig,
                    legacy: true
                }),
            };

            // ensure the entry gets updated in the database
            new customResources.AwsCustomResource(this.scope, createCdkId(['InsertRAGConfig', ragConfig.repositoryId]), {
                onCreate: {
                    service: 'DynamoDB',
                    action: 'putItem',
                    parameters: createOrUpdateParameters,
                    physicalResourceId: customResources.PhysicalResourceId.of(`RAGConfigEntry-${ragConfig.repositoryId}`),
                },
                onUpdate: {
                    service: 'DynamoDB',
                    action: 'putItem',
                    parameters: createOrUpdateParameters,
                },
                onDelete: {
                    service: 'DynamoDB',
                    action: 'deleteItem',
                    parameters: {
                        TableName: ragRepositoryConfigTable.tableName,
                        Key: marshall({ repositoryId: ragConfig.repositoryId }),
                    },
                },
                policy: customResources.AwsCustomResourcePolicy.fromSdkCalls({
                    resources: [ragRepositoryConfigTable.tableArn],
                }),
            });

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
                        new LegacyIngestPipelineStateMachine(this.scope, pipelineId, {
                            config,
                            vpc,
                            pipelineConfig,
                            rdsConfig: ragConfig.rdsConfig,
                            repositoryId: ragConfig.repositoryId,
                            type: ragConfig.type,
                            layers: [layers.common, layers.rag],
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

        if (registeredRepositories.length) {
            // Create Parameter Store entry with RAG repositories
            const repositoriesParameter = new StringParameter(this.scope, createCdkId([config.deploymentName, 'RagReposSP']), {
                parameterName: registeredRepositoriesParamName,
                stringValue: JSON.stringify(registeredRepositories),
                description: 'Serialized JSON of registered RAG repositories',
            });
            repositoriesParameter.grantRead(lambdaRole);
            repositoriesParameter.grantWrite(lambdaRole);
        }
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
            new CfnServiceLinkedRole(this.scope, 'OpensearchServiceLinkedRole', {
                awsServiceName: 'opensearchservice.amazonaws.com',
            });
        }
    }
}

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
import { IAMClient, ListRolesCommand } from '@aws-sdk/client-iam';
import { CfnOutput, RemovalPolicy, Stack, StackProps } from 'aws-cdk-lib';
import { IAuthorizer } from 'aws-cdk-lib/aws-apigateway';
import { ISecurityGroup, Peer, Port, SecurityGroup } from 'aws-cdk-lib/aws-ec2';
import { AnyPrincipal, CfnServiceLinkedRole, Effect, PolicyStatement, Role } from 'aws-cdk-lib/aws-iam';
import { Code, LayerVersion, Runtime, ILayerVersion } from 'aws-cdk-lib/aws-lambda';
import { Domain, EngineVersion, IDomain } from 'aws-cdk-lib/aws-opensearchservice';
import { Credentials, DatabaseInstance, DatabaseInstanceEngine } from 'aws-cdk-lib/aws-rds';
import { Bucket, HttpMethods } from 'aws-cdk-lib/aws-s3';
import { ISecret, Secret } from 'aws-cdk-lib/aws-secretsmanager';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';

import { RepositoryApi } from './api/repository';
import { ARCHITECTURE } from '../core';
import { Layer } from '../core/layers';
import { createCdkId } from '../core/utils';
import { Vpc } from '../networking/vpc';
import { BaseProps, RagRepositoryType } from '../schema';
import { SecurityGroups } from '../core/iam/SecurityGroups';

import { IngestPipelineStateMachine } from './state_machine/ingest-pipeline';

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
            cors: [
                {
                    allowedMethods: [HttpMethods.GET, HttpMethods.POST],
                    allowedHeaders: ['*'],
                    allowedOrigins: ['*'],
                    exposedHeaders: ['Access-Control-Allow-Origin'],
                },
            ],
        });

        const baseEnvironment: Record<string, string> = {
            REGISTERED_MODELS_PS_NAME: modelsPs.parameterName,
            BUCKET_NAME: bucket.bucketName,
            CHUNK_SIZE: config.ragFileProcessingConfig!.chunkSize.toString(),
            CHUNK_OVERLAP: config.ragFileProcessingConfig!.chunkOverlap.toString(),
            LISA_API_URL_PS_NAME: endpointUrl.parameterName,
            REST_API_VERSION: 'v2',
        };

        // Add REST API SSL Cert ARN if it exists to be used to verify SSL calls to REST API
        if (config.restApiConfig?.sslCertIamArn) {
            baseEnvironment['RESTAPI_SSL_CERT_ARN'] = config.restApiConfig?.sslCertIamArn;
        }

        const lambdaRole = Role.fromRoleArn(
            this,
            'LISARagAPILambdaExecutionRole',
            StringParameter.valueForStringParameter(
                this,
                `${config.deploymentPrefix}/roles/${createCdkId([config.deploymentName, 'RAGRole'])}`,
            ),
        );
        bucket.grantRead(lambdaRole);
        bucket.grantPut(lambdaRole);

        // Build RAG Lambda layer
        const ragLambdaLayer = new Layer(this, 'RagLayer', {
            config: config,
            path: RAG_LAYER_PATH,
            description: 'Lambad dependencies for RAG API',
            architecture: ARCHITECTURE,
            autoUpgrade: true,
            assetPath: config.lambdaLayerAssets?.ragLayerPath,
        });

        // Build SDK Layer
        let sdkLayer: ILayerVersion;
        if (config.lambdaLayerAssets?.sdkLayerPath) {
            sdkLayer = new LayerVersion(this, 'SdkLayer', {
                code: Code.fromAsset(config.lambdaLayerAssets?.sdkLayerPath),
                compatibleRuntimes: [Runtime.PYTHON_3_10],
                removalPolicy: config.removalPolicy,
                description: 'LISA SDK common layer',
            });
        } else {
            sdkLayer = new PythonLayerVersion(this, 'SdkLayer', {
                entry: SDK_PATH,
                compatibleRuntimes: [Runtime.PYTHON_3_10],
                removalPolicy: config.removalPolicy,
                description: 'LISA SDK common layer',
            });
        }

        const registeredRepositories = [];

        for (const ragConfig of config.ragRepositories) {
            // Create opensearch cluster for RAG
            if (ragConfig.type === RagRepositoryType.OPENSEARCH && ragConfig.opensearchConfig) {
                const openSearchSg = this.createSecurityGroup(vpc.securityGroups.openSearchSg, SecurityGroups.OPEN_SEARCH_SG, config.deploymentName, vpc, 'Security group for RAG OpenSearch domain');

                // Allow communication from private subnets to ECS cluster
                const subNets = config.subnets && config.vpcId ? config.subnets : vpc.vpc.isolatedSubnets.concat(vpc.vpc.privateSubnets);
                subNets?.forEach((subnet) => {
                    openSearchSg.connections.allowFrom(
                        Peer.ipv4(subnet.ipv4CidrBlock),
                        Port.tcp(config.restApiConfig.rdsConfig.dbPort),
                        'Allow REST API private subnets to communicate with LiteLLM database',
                    );
                });
                new CfnOutput(this, 'openSearchSg', { value: openSearchSg.securityGroupId });

                registeredRepositories.push({ repositoryId: ragConfig.repositoryId, type: ragConfig.type });
                let openSearchDomain: IDomain;

                if ('endpoint' in ragConfig.opensearchConfig) {
                    openSearchDomain = Domain.fromDomainEndpoint(
                        this,
                        'ExistingOpenSearchDomain',
                        ragConfig.opensearchConfig.endpoint,
                    );
                } else {
                    // Service-linked role that Amazon OpenSearch Service will use
                    (async () => {
                        const iam = new IAMClient({
                            region: config.region,
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
                    })();

                    openSearchDomain = new Domain(this, 'LisaServeRagRepository', {
                        domainName: 'lisa-rag',
                        // 2.9 is the latest available in ADC regions as of 1/11/24
                        version: EngineVersion.OPENSEARCH_2_9,
                        enableVersionUpgrade: true,
                        vpc: vpc.vpc,
                        ...(vpc.subnetSelection && {vpcSubnets: [vpc.subnetSelection]}),
                        ebs: {
                            enabled: true,
                            volumeSize: ragConfig.opensearchConfig.volumeSize,
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
                        securityGroups: [openSearchSg!],
                    });
                }

                // Rag API task execution role will read and write
                openSearchDomain.grantIndexReadWrite('*', lambdaRole);
                openSearchDomain.grantPathReadWrite('*', lambdaRole);
                openSearchDomain.grantReadWrite(lambdaRole);

                new CfnOutput(this, 'opensearchRagRepositoryEndpoint', {
                    value: openSearchDomain.domainEndpoint,
                });

                const openSearchEndpointPs = new StringParameter(
                    this,
                    createCdkId(['LisaServeRagRepositoryEndpoint', 'StringParameter']),
                    {
                        parameterName: `${config.deploymentPrefix}/lisaServeRagRepositoryEndpoint`,
                        stringValue: openSearchDomain.domainEndpoint,
                        description: 'Endpoint for LISA Serve OpenSearch Rag Repository',
                    },
                );

                // Add explicit dependency on OpenSearch Domain being created
                openSearchEndpointPs.node.addDependency(openSearchDomain);
                openSearchEndpointPs.grantRead(lambdaRole);
                // Add parameter as lambda environment variable for RagAPI
                baseEnvironment['OPENSEARCH_ENDPOINT_PS_NAME'] = openSearchEndpointPs.parameterName;
            } else if (ragConfig.type === RagRepositoryType.PGVECTOR && ragConfig.rdsConfig) {
                registeredRepositories.push({ repositoryId: ragConfig.repositoryId, type: ragConfig.type });
                const connectionParamName = 'LisaServeRagPGVectorConnectionInfo';
                let rdsPasswordSecret: ISecret;
                let rdsConnectionInfoPs: StringParameter;
                // if dbHost and passwordSecretId are defined, then connect to DB with existing params
                if (!!ragConfig.rdsConfig.dbHost && !!ragConfig.rdsConfig.passwordSecretId) {
                    rdsConnectionInfoPs = new StringParameter(this, createCdkId([connectionParamName, 'StringParameter']), {
                        parameterName: `${config.deploymentPrefix}/${connectionParamName}`,
                        stringValue: JSON.stringify(ragConfig.rdsConfig),
                        description: 'Connection info for LISA Serve PGVector database',
                    });
                    rdsPasswordSecret = Secret.fromSecretNameV2(
                        this,
                        createCdkId([config.deploymentName, 'RagRDSPwdSecret']),
                        ragConfig.rdsConfig.passwordSecretId,
                    );
                } else {
                    // Create new DB and SG
                    const pgvectorSg = this.createSecurityGroup(vpc.securityGroups.pgVectorSg, SecurityGroups.PG_VECTOR_SG, config.deploymentName, vpc, 'RAG PGVector database');

                    const subNets = config.subnets && config.vpcId ? config.subnets : vpc.vpc.isolatedSubnets.concat(vpc.vpc.privateSubnets);
                    subNets?.forEach((subnet) => {
                        pgvectorSg.connections.allowFrom(
                            Peer.ipv4(subnet.ipv4CidrBlock),
                            Port.tcp(config.restApiConfig.rdsConfig.dbPort),
                            'Allow REST API private subnets to communicate with LiteLLM database',
                        );
                    });

                    const username = ragConfig.rdsConfig.username;
                    const dbCreds = Credentials.fromGeneratedSecret(username);
                    const pgvector_db = new DatabaseInstance(this, 'PGVectorDB', {
                        engine: DatabaseInstanceEngine.POSTGRES,
                        vpc: vpc.vpc,
                        subnetGroup: vpc.subnetGroup,
                        credentials: dbCreds,
                        securityGroups: [pgvectorSg],
                        removalPolicy: RemovalPolicy.DESTROY,
                    });
                    rdsPasswordSecret = pgvector_db.secret!;
                    rdsConnectionInfoPs = new StringParameter(this, createCdkId([connectionParamName, 'StringParameter']), {
                        parameterName: `${config.deploymentPrefix}/${connectionParamName}`,
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
                baseEnvironment['RDS_CONNECTION_INFO_PS_NAME'] = rdsConnectionInfoPs.parameterName;
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
                        new IngestPipelineStateMachine(this, pipelineId, {
                            config,
                            vpc,
                            pipelineConfig,
                            rdsConfig: ragConfig.rdsConfig,
                            repositoryId: ragConfig.repositoryId,
                            type: ragConfig.type,
                            layers: [commonLambdaLayer, ragLambdaLayer.layer, sdkLayer]
                        });
                        console.log(`[DEBUG] Successfully created pipeline ${index}`);
                    } catch (error) {
                        console.error(`[ERROR] Failed to create pipeline ${index}:`, error);
                        throw error; // Re-throw to ensure CDK deployment fails
                    }
                });
            }
        }

        // Create Parameter Store entry with RAG repositories
        const ragRepositoriesParam = new StringParameter(this, createCdkId([config.deploymentName, 'RagReposSP']), {
            parameterName: `${config.deploymentPrefix}/registeredRepositories`,
            stringValue: JSON.stringify(registeredRepositories),
            description: 'Serialized JSON of registered RAG repositories',
        });

        baseEnvironment['REGISTERED_REPOSITORIES_PS_NAME'] = ragRepositoriesParam.parameterName;

        // Add REST API Lambdas to APIGW
        new RepositoryApi(this, 'RepositoryApi', {
            authorizer,
            baseEnvironment,
            config,
            vpc: vpc,
            commonLayers: [commonLambdaLayer, ragLambdaLayer.layer, sdkLayer],
            restApiId,
            rootResourceId,
            securityGroups,
            lambdaExecutionRole: lambdaRole,
        });

        ragRepositoriesParam.grantRead(lambdaRole);
        modelsPs.grantRead(lambdaRole);
        endpointUrl.grantRead(lambdaRole);
    }

    /**
     * Creates a security group for the VPC.
     *
     * @param securityGroupOverride - security group override
     * @param {string} securityGroupName - The name of the security group.
     * @param {string} deploymentName - The deployment name.
     * @param {Vpc} vpc - The virtual private cloud.
     * @param {string} description - The description of the security group.
     * @returns {ISecurityGroup} The security group.
     */
    createSecurityGroup (
        securityGroupOverride: ISecurityGroup | undefined,
        securityGroupName: string,
        deploymentName: string,
        vpc: Vpc,
        description: string,
    ): ISecurityGroup {
        if (securityGroupOverride) {
            return SecurityGroup.fromSecurityGroupId(this, securityGroupName, securityGroupOverride.securityGroupId);
        } else {
            return new SecurityGroup(this, securityGroupName, {
                securityGroupName: createCdkId([deploymentName, securityGroupName]),
                vpc: vpc.vpc,
                description: `Security group for ${description}`,
            });
        }
    }
}

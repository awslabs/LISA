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
import { Duration, RemovalPolicy, StackProps } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { RagRepositoryDeploymentConfig, RagRepositoryType, PartialConfig, RDSConfig } from '../../../lib/schema';
import { createCdkId } from '../../../lib/core/utils';
import { ISecurityGroup, IVpc, SecurityGroup, Subnet, SubnetSelection, Vpc } from 'aws-cdk-lib/aws-ec2';
import { Code, Function, IFunction, ILayerVersion, LayerVersion } from 'aws-cdk-lib/aws-lambda';
import { Effect, PolicyDocument, PolicyStatement, Role, ServicePrincipal } from 'aws-cdk-lib/aws-iam';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { ISecret, Secret } from 'aws-cdk-lib/aws-secretsmanager';
import { Credentials, DatabaseInstance, DatabaseInstanceEngine } from 'aws-cdk-lib/aws-rds';
import { Roles } from '../../../lib/core/iam/roles';
import { PipelineStack } from './pipeline-stack';
import { SecurityGroupFactory } from '../../../lib/networking/vpc/security-group-factory';
import { SecurityGroupEnum } from '../../../lib/core/iam/SecurityGroups';
import { getPythonRuntime } from '../../../lib/api-base/utils';
import { LAMBDA_PATH } from '../../../lib/util';
import { AwsCustomResource, PhysicalResourceId } from 'aws-cdk-lib/custom-resources';

// Type definition for PGVectorStoreStack properties
type PGVectorStoreStackProps = StackProps & {
    config: PartialConfig,
    ragConfig: RagRepositoryDeploymentConfig,
};

// PGVectorStoreStack class, extending PipelineStack
export class PGVectorStoreStack extends PipelineStack {
    constructor (scope: Construct, id: string, props: PGVectorStoreStackProps) {
        super(scope, id, props);

        // Destructure the configuration properties
        const { config, ragConfig } = props;
        const { vpcId, deploymentName, deploymentPrefix, subnets } = config;
        const { repositoryId, type, rdsConfig } = ragConfig;

        // Retrieve Lambda execution role using Role ARN
        const lambdaRole = Role.fromRoleArn(
            this,
            `${Roles.RAG_LAMBDA_EXECUTION_ROLE}-${repositoryId}`,
            StringParameter.valueForStringParameter(
                this,
                `${deploymentPrefix}/roles/${createCdkId([deploymentName!, Roles.RAG_LAMBDA_EXECUTION_ROLE])}`,
            ),
        );

        // Lookup VPC with given vpcId
        const vpc = Vpc.fromLookup(this, 'Vpc', {
            vpcId,
            returnVpnGateways: false,
        });

        // Optional subnet selection based on provided subnets
        let subnetSelection: SubnetSelection | undefined;

        if (subnets && subnets.length > 0) {
            subnetSelection = {
                subnets: subnets?.map((subnet, index) => Subnet.fromSubnetId(this, `subnet-${index}`, subnet.subnetId))
            };
        }

        // Check if PGVector type and RDS configuration are provided in ragConfig
        if (type === RagRepositoryType.PGVECTOR && rdsConfig) {
            // Determine authentication method - default to IAM auth (iamRdsAuth = true)
            const useIamAuth = config.iamRdsAuth ?? true;

            let rdsSecret: ISecret;
            let rdsConnectionInfo: StringParameter;

            // Get Security Group ID for PGVector
            const securityGroupId = StringParameter.valueFromLookup(this, `${config.deploymentPrefix}/pgvectorSecurityGroupId`);
            const pgSecurityGroup = SecurityGroup.fromSecurityGroupId(this, 'PGVectorSecurityGroup', securityGroupId);

            // Add non-default ingress port for SG
            if (!config.securityGroupConfig?.pgVectorSecurityGroupId && rdsConfig.dbPort !== 5432) {
                SecurityGroupFactory.addIngress(pgSecurityGroup, SecurityGroupEnum.PG_VECTOR_SG, vpc, rdsConfig.dbPort, subnetSelection?.subnets);
            }

            // Check if existing DB connection details are available (dbHost and passwordSecretId provided)
            if (rdsConfig && rdsConfig.dbHost && rdsConfig.passwordSecretId) {
                // Use existing DB connection details
                rdsConnectionInfo = new StringParameter(this, createCdkId([repositoryId, 'StringParameter']), {
                    parameterName: `${config.deploymentPrefix}/LisaServeRagConnectionInfo/${repositoryId}`,
                    stringValue: JSON.stringify({
                        username: rdsConfig.username,
                        dbHost: rdsConfig.dbHost,
                        dbName: rdsConfig.dbName,
                        dbPort: rdsConfig.dbPort,
                        type: RagRepositoryType.PGVECTOR,
                        // Include passwordSecretId only when using password auth
                        ...(!useIamAuth ? { passwordSecretId: rdsConfig.passwordSecretId } : {})
                    }),
                    description: 'Connection info for LISA Serve PGVector database',
                });
                rdsSecret = Secret.fromSecretNameV2(
                    this,
                    createCdkId([deploymentName!, repositoryId, 'RagRDSSecret']),
                    rdsConfig.passwordSecretId!,
                );
            } else {
                // Create a new RDS instance with generated credentials
                const username = rdsConfig.username;
                const dbCreds = Credentials.fromGeneratedSecret(username);
                const pgvectorDb = new DatabaseInstance(this, createCdkId([repositoryId, 'PGVectorDB']), {
                    engine: DatabaseInstanceEngine.POSTGRES,
                    vpc: vpc,
                    vpcSubnets: subnetSelection,
                    credentials: dbCreds,
                    iamAuthentication: useIamAuth, // Enable IAM auth when iamRdsAuth is true
                    securityGroups: [pgSecurityGroup],
                    removalPolicy: RemovalPolicy.DESTROY,
                    databaseName: rdsConfig.dbName,
                    port: rdsConfig.dbPort
                });

                rdsSecret = pgvectorDb.secret!;

                if (!useIamAuth) {
                    // Password auth: grant connect as postgres user
                    pgvectorDb.grantConnect(lambdaRole);
                    rdsConfig.passwordSecretId = rdsSecret.secretName;
                } else {
                    // IAM auth: grant connect with role name
                    pgvectorDb.grantConnect(lambdaRole, lambdaRole.roleName);
                }

                // Store DB connection details
                rdsConfig.dbHost = pgvectorDb.dbInstanceEndpointAddress;
                rdsConfig.dbPort = Number(pgvectorDb.dbInstanceEndpointPort);

                // Save new DB connection details as a parameter
                rdsConnectionInfo = new StringParameter(this, createCdkId([repositoryId, 'StringParameter']), {
                    parameterName: `${config.deploymentPrefix}/LisaServeRagConnectionInfo/${repositoryId}`,
                    stringValue: JSON.stringify({
                        username: username,
                        dbHost: pgvectorDb.dbInstanceEndpointAddress,
                        dbName: rdsConfig.dbName,
                        dbPort: pgvectorDb.dbInstanceEndpointPort,
                        type: RagRepositoryType.PGVECTOR,
                        // Include passwordSecretId only when using password auth
                        ...(!useIamAuth ? { passwordSecretId: rdsSecret.secretName } : {})
                    }),
                    description: 'Connection info for LISA Serve PGVector database',
                });
            }

            if (!useIamAuth) {
                // Password auth: grant secret read access
                rdsSecret.grantRead(lambdaRole);
            } else {
                // IAM auth: create the lambda for generating DB users
                const createDbUserLambda = this.getIAMAuthLambda(config, repositoryId, rdsConfig, rdsSecret, lambdaRole.roleName, vpc, [pgSecurityGroup], subnetSelection);

                const customResourceRole = new Role(this, createCdkId(['CustomResourceRole', ragConfig.repositoryId]), {
                    assumedBy: new ServicePrincipal('lambda.amazonaws.com'),
                    inlinePolicies: {
                        'EC2NetworkInterfaces': new PolicyDocument({
                            statements: [
                                new PolicyStatement({
                                    effect: Effect.ALLOW,
                                    actions: ['ec2:CreateNetworkInterface', 'ec2:DescribeNetworkInterfaces', 'ec2:DeleteNetworkInterface'],
                                    resources: ['*'],
                                }),
                            ],
                        }),
                    },
                });
                createDbUserLambda.grantInvoke(customResourceRole);

                // Run the IAM user bootstrap Lambda on every deploy
                new AwsCustomResource(this, createCdkId([repositoryId, 'CreateDbUserCustomResource']), {
                    onCreate: {
                        service: 'Lambda',
                        action: 'invoke',
                        physicalResourceId: PhysicalResourceId.of(createCdkId([repositoryId, 'CreateDbUserCustomResource'])),
                        parameters: {
                            FunctionName: createDbUserLambda.functionName,
                            Payload: '{}'
                        },
                    },
                    role: customResourceRole
                });
            }

            // Grant read permissions for connection info to Lambda role
            rdsConnectionInfo.grantRead(lambdaRole);

            this.createPipelineRules(config, ragConfig);
        }
    }

    getIAMAuthLambda (config: PartialConfig, repositoryId: string, rdsConfig: NonNullable<RDSConfig>, secret: ISecret, user: string, vpc: IVpc, securityGroups: ISecurityGroup[], vpcSubnets?: SubnetSelection): IFunction {
        // Create the IAM role for updating the database to allow IAM authentication
        const iamAuthLambdaRole = new Role(this, createCdkId([repositoryId, 'IAMAuthLambdaRole']), {
            assumedBy: new ServicePrincipal('lambda.amazonaws.com'),
        });

        secret.grantRead(iamAuthLambdaRole);
        // Grant permission to delete the bootstrap secret after IAM user creation
        secret.grantWrite(iamAuthLambdaRole);

        const commonLayer = this.getLambdaLayer(repositoryId, config);
        const lambdaPath = config.lambdaPath || LAMBDA_PATH;

        return new Function(this, createCdkId([repositoryId, 'CreateDbUserLambda']), {
            runtime: getPythonRuntime(),
            handler: 'utilities.db_setup_iam_auth.handler',
            code: Code.fromAsset(lambdaPath),
            timeout: Duration.minutes(2),
            environment: {
                SECRET_ARN: secret.secretArn,
                DB_HOST: rdsConfig.dbHost!,
                DB_PORT: String(rdsConfig.dbPort),
                DB_NAME: rdsConfig.dbName,
                DB_USER: rdsConfig.username,
                IAM_NAME: user,
            },
            role: iamAuthLambdaRole,
            layers: [commonLayer],
            vpc,
            securityGroups,
            vpcSubnets
        });
    }

    getLambdaLayer (repositoryId: string, config: PartialConfig): ILayerVersion {
        return LayerVersion.fromLayerVersionArn(
            this,
            createCdkId([repositoryId, 'CommonLayerVersion']),
            StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/layerVersion/common`),
        );
    }
}

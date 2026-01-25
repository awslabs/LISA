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
import { RemovalPolicy, Stack, StackProps } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { RagRepositoryDeploymentConfig, RagRepositoryType, PartialConfig } from '../../../lib/schema';
import { createCdkId } from '../../../lib/core/utils';
import { SecurityGroup, Subnet, SubnetSelection, Vpc } from 'aws-cdk-lib/aws-ec2';
import { Effect, PolicyStatement, Role } from 'aws-cdk-lib/aws-iam';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { ISecret, Secret } from 'aws-cdk-lib/aws-secretsmanager';
import { Credentials, DatabaseInstance, DatabaseInstanceEngine } from 'aws-cdk-lib/aws-rds';
import { Roles } from '../../../lib/core/iam/roles';
import { PipelineStack } from './pipeline-stack';
import { SecurityGroupFactory } from '../../../lib/networking/vpc/security-group-factory';
import { SecurityGroupEnum } from '../../../lib/core/iam/SecurityGroups';
import { AwsCustomResource, AwsCustomResourcePolicy, PhysicalResourceId } from 'aws-cdk-lib/custom-resources';

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
            let pgvectorDb: DatabaseInstance | undefined;

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
                pgvectorDb = new DatabaseInstance(this, createCdkId([repositoryId, 'PGVectorDB']), {
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
                    // Password auth: only need secret access (grantConnect requires IAM auth)
                    rdsConfig.passwordSecretId = rdsSecret.secretName;
                } else {
                    // IAM auth: manually grant rds-db:connect permission
                    // Note: We do NOT use pgvectorDb.grantConnect() due to CDK bug #11851
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

                // Store DB connection details
                // Note: dbHost is a CDK token that resolves at deploy time
                // dbPort is already set from rdsConfig input, no need to override with token
                rdsConfig.dbHost = pgvectorDb.dbInstanceEndpointAddress;

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
                // IAM auth: use the shared IAM auth setup Lambda deployed in the main stack
                const iamAuthSetupFnArn = StringParameter.valueForStringParameter(
                    this,
                    `${config.deploymentPrefix}/iamAuthSetupFnArn`
                );

                // Get the IAM auth setup Lambda role ARN from SSM to grant it permissions
                const iamAuthSetupRoleArn = StringParameter.valueForStringParameter(
                    this,
                    `${config.deploymentPrefix}/iamAuthSetupRoleArn`
                );

                // Import the IAM auth setup role to grant it secret permissions
                const iamAuthSetupRole = Role.fromRoleArn(
                    this,
                    createCdkId([repositoryId, 'IamAuthSetupRoleRef']),
                    iamAuthSetupRoleArn
                );

                // Grant the IAM auth setup Lambda role permission to read the bootstrap secret
                rdsSecret.grantRead(iamAuthSetupRole);

                // Run the shared IAM auth setup Lambda on create and update
                // Pass parameters via payload since the Lambda is shared across repositories
                // Use Stack.of(this).toJsonString() to properly resolve CDK tokens in the payload
                const lambdaInvokeParams = {
                    service: 'Lambda',
                    action: 'invoke',
                    physicalResourceId: PhysicalResourceId.of(createCdkId([repositoryId, 'CreateDbUserCustomResource'])),
                    parameters: {
                        FunctionName: iamAuthSetupFnArn,
                        Payload: Stack.of(this).toJsonString({
                            secretArn: rdsSecret.secretArn,
                            dbHost: rdsConfig.dbHost,
                            dbPort: rdsConfig.dbPort,
                            dbName: rdsConfig.dbName,
                            dbUser: rdsConfig.username,
                            iamName: lambdaRole.roleName,
                        })
                    },
                };

                const createDbUserResource = new AwsCustomResource(this, createCdkId([repositoryId, 'CreateDbUserCustomResource']), {
                    onCreate: lambdaInvokeParams,
                    onUpdate: lambdaInvokeParams,  // Also run on updates to ensure IAM user is created
                    policy: AwsCustomResourcePolicy.fromStatements([
                        new PolicyStatement({
                            effect: Effect.ALLOW,
                            actions: ['lambda:InvokeFunction'],
                            resources: [iamAuthSetupFnArn],
                        })
                    ]),
                });

                // Ensure the RDS instance is fully available before running IAM auth setup
                // (only when we created a new RDS instance)
                if (pgvectorDb) {
                    createDbUserResource.node.addDependency(pgvectorDb);
                }
            }

            // Grant read permissions for connection info to Lambda role
            rdsConnectionInfo.grantRead(lambdaRole);

            this.createPipelineRules(config, ragConfig);
        }
    }
}

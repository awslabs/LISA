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
import { RemovalPolicy, StackProps } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { RagRepositoryConfigSchema, RagRepositoryType, PartialConfigSchema } from '../../../lib/schema';
import { createCdkId } from '../../../lib/core/utils';
import { z } from 'zod';
import { SecurityGroup, Subnet, SubnetSelection, Vpc } from 'aws-cdk-lib/aws-ec2';
import { Role } from 'aws-cdk-lib/aws-iam';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { ISecret, Secret } from 'aws-cdk-lib/aws-secretsmanager';
import { Credentials, DatabaseInstance, DatabaseInstanceEngine } from 'aws-cdk-lib/aws-rds';
import { Roles } from '../../../lib/core/iam/roles';
import { PipelineStack } from './pipeline-stack';

// Type definition for PGVectorStoreStack properties
type PGVectorStoreStackProps = StackProps & {
    config: z.infer<typeof PartialConfigSchema>,
    ragConfig: z.infer<typeof RagRepositoryConfigSchema>,
};

// PGVectorStoreStack class, extending PipelineStack
export class PGVectorStoreStack extends PipelineStack {
    constructor (scope: Construct, id: string, props: PGVectorStoreStackProps) {
        super(scope, id, props);

        // Destructure the configuration properties
        const { config, ragConfig } = props;
        const { vpcId, deploymentName, deploymentPrefix, subnets } = config;

        // Retrieve Lambda execution role using Role ARN
        const lambdaRole = Role.fromRoleArn(
            this,
            Roles.RAG_LAMBDA_EXECUTION_ROLE,
            StringParameter.valueForStringParameter(
                this,
                `${deploymentPrefix}/roles/${createCdkId([deploymentName!, Roles.RAG_LAMBDA_EXECUTION_ROLE])}`,
            ),
        );

        // Lookup VPC with given vpcId
        const vpc = Vpc.fromLookup(this, 'Vpc', {
            vpcId
        });

        // Optional subnet selection based on provided subnets
        let subnetSelection: SubnetSelection | undefined;

        if (subnets && subnets.length > 0) {
            subnetSelection = {
                subnets: subnets?.map((subnet, index) => Subnet.fromSubnetId(this, `subnet-${index}`, subnet.subnetId))
            };
        }

        // Check if PGVector type and RDS configuration are provided in ragConfig
        if (ragConfig?.type === RagRepositoryType.PGVECTOR && ragConfig.rdsConfig) {
            let rdsPasswordSecret: ISecret;
            let rdsConnectionInfo: StringParameter;

            // Get Security Group ID for PGVector
            const securityGroupId = StringParameter.valueFromLookup(this, `${config.deploymentPrefix}/pgvectorSecurityGroupId`);
            const pgSecurityGroup = SecurityGroup.fromSecurityGroupId(this, 'PGVectorSecurityGroup', securityGroupId);
            // if dbHost and passwordSecretId are defined, then connect to DB with existing params
            // Check if existing DB connection details are available
            if (ragConfig.rdsConfig && ragConfig.rdsConfig.passwordSecretId) {
                // Use existing DB connection details
                rdsConnectionInfo = new StringParameter(this, createCdkId([ragConfig.repositoryId, 'StringParameter']), {
                    parameterName: `${config.deploymentPrefix}/LisaServeRagConnectionInfo/${ragConfig.repositoryId}`,
                    stringValue: JSON.stringify(ragConfig.rdsConfig),
                    description: 'Connection info for LISA Serve PGVector database',
                });
                rdsPasswordSecret = Secret.fromSecretNameV2(
                    this,
                    createCdkId([deploymentName!, ragConfig.repositoryId, 'RagRDSPwdSecret']),
                    ragConfig.rdsConfig.passwordSecretId!,
                );
            } else {
                // Create a new RDS instance with generated credentials
                const username = ragConfig.rdsConfig.username;
                const dbCreds = Credentials.fromGeneratedSecret(username);
                const pgvectorDb = new DatabaseInstance(this, createCdkId([ragConfig.repositoryId, 'PGVectorDB']), {
                    engine: DatabaseInstanceEngine.POSTGRES,
                    vpc: vpc,
                    vpcSubnets: subnetSelection,
                    // TODO add instance type?
                    // TODO: Specify the RDS instance type
                    credentials: dbCreds,
                    securityGroups: [pgSecurityGroup],
                    removalPolicy: RemovalPolicy.DESTROY,
                    databaseName: ragConfig.rdsConfig.dbName,
                    port: ragConfig.rdsConfig.dbPort
                });
                rdsPasswordSecret = pgvectorDb.secret!;

                // Store password secret ID in ragConfig
                ragConfig.rdsConfig.passwordSecretId = rdsPasswordSecret.secretName;

                // Save new DB connection details as a parameter
                rdsConnectionInfo = new StringParameter(this, createCdkId([ragConfig.repositoryId, 'StringParameter']), {
                    parameterName: `${config.deploymentPrefix}/LisaServeRagConnectionInfo/${ragConfig.repositoryId}`,
                    stringValue: JSON.stringify({
                        username: username,
                        passwordSecretId: rdsPasswordSecret.secretName,
                        dbHost: pgvectorDb.dbInstanceEndpointAddress,
                        dbName: ragConfig.rdsConfig.dbName,
                        dbPort: pgvectorDb.dbInstanceEndpointPort,
                    }),
                    description: 'Connection info for LISA Serve PGVector database',
                });
            }

            // Grant read permissions for secrets to Lambda role
            rdsPasswordSecret.grantRead(lambdaRole);
            rdsConnectionInfo.grantRead(lambdaRole);

            this.createPipelineRules(config, ragConfig);
        }
    }
}

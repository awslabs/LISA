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

// LISA-serve Stack.
import path from 'path';

import { Stack, StackProps } from 'aws-cdk-lib';
import { AttributeType, BillingMode, Table, TableEncryption } from 'aws-cdk-lib/aws-dynamodb';
import { Peer, Port, SecurityGroup } from 'aws-cdk-lib/aws-ec2';
import { Credentials, DatabaseInstance, DatabaseInstanceEngine } from 'aws-cdk-lib/aws-rds';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';

import { FastApiContainer } from '../api-base/fastApiContainer';
import { createCdkId } from '../core/utils';
import { Vpc } from '../networking/vpc';
import { BaseProps } from '../schema';

const HERE = path.resolve(__dirname);

type CustomLisaStackProps = {
    vpc: Vpc;
} & BaseProps;
type LisaStackProps = CustomLisaStackProps & StackProps;

/**
 * LisaServe Application stack.
 */
export class LisaServeApplicationStack extends Stack {
    /** FastAPI construct */
    public readonly restApi: FastApiContainer;
    public readonly modelsPs: StringParameter;
    public readonly endpointUrl: StringParameter;

    /**
   * @param {Construct} scope - The parent or owner of the construct.
   * @param {string} id - The unique identifier for the construct within its scope.
   * @param {LisaStackProps} props - Properties for the Stack.
   */
    constructor (scope: Construct, id: string, props: LisaStackProps) {
        super(scope, id, props);

        const { config, vpc } = props;
        const rdsConfig = config.restApiConfig.rdsConfig;

        let tokenTable;
        if (config.restApiConfig.internetFacing) {
            // Create DynamoDB Table for enabling API token usage
            tokenTable = new Table(this, 'TokenTable', {
                tableName: `${config.deploymentName}-LISAApiTokenTable`,
                partitionKey: {
                    name: 'token',
                    type: AttributeType.STRING,
                },
                billingMode: BillingMode.PAY_PER_REQUEST,
                encryption: TableEncryption.AWS_MANAGED,
                removalPolicy: config.removalPolicy,
            });
        }

        // Create REST API
        const restApi = new FastApiContainer(this, 'RestApi', {
            apiName: 'REST',
            config: config,
            resourcePath: path.join(HERE, 'rest-api'),
            securityGroup: vpc.securityGroups.restApiAlbSg,
            taskConfig: config.restApiConfig,
            tokenTable: tokenTable,
            vpc: vpc.vpc,
        });

        // LiteLLM requires a PostgreSQL database to support multiple-instance scaling with dynamic model management.
        const connectionParamName = 'LiteLLMDbConnectionInfo';

        const litellmDbSg = new SecurityGroup(this, 'LISA-LiteLLMScalingSg', {
            vpc: vpc.vpc,
            description: 'Security group for LiteLLM dynamic model management database.',
        });
        vpc.vpc.isolatedSubnets.concat(vpc.vpc.privateSubnets).forEach((subnet) => {
            litellmDbSg.connections.allowFrom(
                Peer.ipv4(subnet.ipv4CidrBlock),
                Port.tcp(rdsConfig.dbPort),
                'Allow REST API private subnets to communicate with LiteLLM database',
            );
        });

        const username = rdsConfig.username;
        const dbCreds = Credentials.fromGeneratedSecret(username);

        // DB is a Single AZ instance for cost + inability to make non-Aurora multi-AZ cluster in CDK
        // DB is not expected to be under any form of heavy load.
        // https://github.com/aws/aws-cdk/issues/25547
        const litellmDb = new DatabaseInstance(this, 'LiteLLMScalingDB', {
            engine: DatabaseInstanceEngine.POSTGRES,
            vpc: vpc.vpc,
            credentials: dbCreds,
            securityGroups: [litellmDbSg!],
            removalPolicy: config.removalPolicy,
        });

        const litellmDbPasswordSecret = litellmDb.secret!;
        const litellmDbConnectionInfoPs = new StringParameter(this, createCdkId([connectionParamName, 'StringParameter']), {
            parameterName: `${config.deploymentPrefix}/${connectionParamName}`,
            stringValue: JSON.stringify({
                username: username,
                passwordSecretId: litellmDbPasswordSecret.secretName,
                dbHost: litellmDb.dbInstanceEndpointAddress,
                dbName: rdsConfig.dbName,
                dbPort: rdsConfig.dbPort,
            }),
        });
        litellmDbPasswordSecret.grantRead(restApi.taskRole);
        litellmDbConnectionInfoPs.grantRead(restApi.taskRole);
        restApi.container.addEnvironment('LITELLM_DB_INFO_PS_NAME', litellmDbConnectionInfoPs.parameterName);

        // Create Parameter Store entry with RestAPI URI
        this.endpointUrl = new StringParameter(this, createCdkId(['LisaServeRestApiUri', 'StringParameter']), {
            parameterName: `${config.deploymentPrefix}/lisaServeRestApiUri`,
            stringValue: restApi.endpoint,
            description: 'URI for LISA Serve API',
        });

        // Create Parameter Store entry with registeredModels
        this.modelsPs = new StringParameter(this, createCdkId(['RegisteredModels', 'StringParameter']), {
            parameterName: `${config.deploymentPrefix}/registeredModels`,
            stringValue: JSON.stringify([]),
            description: 'Serialized JSON of registered models data',
        });

        this.modelsPs.grantRead(restApi.taskRole);
        // Add parameter as container environment variable for both RestAPI and RagAPI
        restApi.container.addEnvironment('REGISTERED_MODELS_PS_NAME', this.modelsPs.parameterName);
        restApi.node.addDependency(this.modelsPs);

        // Update
        this.restApi = restApi;
    }
}

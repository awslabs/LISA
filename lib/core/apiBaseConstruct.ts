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


import { Authorizer, Cors, EndpointType, RestApi, StageOptions } from 'aws-cdk-lib/aws-apigateway';

import { AttributeType, BillingMode, ProjectionType, TableEncryption } from 'aws-cdk-lib/aws-dynamodb';

import { CustomAuthorizer } from '../api-base/authorizer';
import { Duration, Stack, StackProps } from 'aws-cdk-lib';
import { ITable, Table } from 'aws-cdk-lib/aws-dynamodb';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';
import { Code, Function, } from 'aws-cdk-lib/aws-lambda';

import { createCdkId } from '../core/utils';
import { Vpc } from '../networking/vpc';
import { APP_MANAGEMENT_KEY, BaseProps, Config } from '../schema';
import {
    Effect,
    ManagedPolicy,
    PolicyDocument,
    PolicyStatement,
    Role,
    ServicePrincipal,
} from 'aws-cdk-lib/aws-iam';
import { Secret } from 'aws-cdk-lib/aws-secretsmanager';
import { LAMBDA_PATH } from '../util';
import { getPythonRuntime } from '../api-base/utils';
import { ISecurityGroup } from 'aws-cdk-lib/aws-ec2';
import { EventBus } from 'aws-cdk-lib/aws-events';

export type LisaApiBaseProps = {
    vpc: Vpc;
    securityGroups: ISecurityGroup[];
} & BaseProps &
    StackProps;

/**
 * Base stack resources for LISA REST API
 */
export class LisaApiBaseConstruct extends Construct {
    public readonly restApi: RestApi;
    public readonly authorizer?: Authorizer;
    public readonly restApiId: string;
    public readonly rootResourceId: string;
    public readonly restApiUrl: string;
    public readonly tokenTable?: ITable;
    public readonly managementKeySecretName: string;

    constructor (scope: Stack, id: string, props: LisaApiBaseProps) {
        super(scope, id);

        const { config, vpc, securityGroups } = props;

        // TokenTable is now managed in API Base so it's independent of Serve
        // Create the table - if it already exists from previous Serve deployment,
        // CloudFormation will handle the conflict. For new deployments, it will be created.
        let tokenTable: Table | undefined;

        // Use new table name to avoid conflicts with existing Serve stack deployments
        const tableName = `${config.deploymentName}-LISAApiBaseTokenTable`;
        const tokenTableNameParam = `${config.deploymentPrefix}/tokenTableName`;

        // Create the table with new name
        // Serve stack will automatically use the new table via SSM parameter reference
        tokenTable = new Table(scope, 'TokenTable', {
            tableName: tableName,
            partitionKey: {
                name: 'token',
                type: AttributeType.STRING,
            },
            billingMode: BillingMode.PAY_PER_REQUEST,
            encryption: TableEncryption.AWS_MANAGED,
            removalPolicy: config.removalPolicy,
        });

        // Add GSI for querying tokens by createdFor
        tokenTable.addGlobalSecondaryIndex({
            indexName: 'createdFor-index',
            partitionKey: { name: 'createdFor', type: AttributeType.STRING },
            projectionType: ProjectionType.ALL,
        });

        // Store token table name in SSM for cross-stack reference
        new StringParameter(scope, 'TokenTableNameParameter', {
            parameterName: tokenTableNameParam,
            stringValue: tokenTable.tableName,
            description: 'DynamoDB table name for API tokens',
        });

        this.tokenTable = tokenTable;

        const { managementKeySecretName } = this.createManagementKeySecret(scope, config, vpc, securityGroups);
        this.managementKeySecretName = managementKeySecretName;

        const deployOptions: StageOptions = {
            stageName: config.deploymentStage,
            throttlingRateLimit: 100,
            throttlingBurstLimit: 100,
        };

        if (config.authConfig) {
            // Create the authorizer Lambda for APIGW
            const authorizer = new CustomAuthorizer(scope, 'LisaApiAuthorizer', {
                config: config,
                securityGroups: [vpc.securityGroups.lambdaSg],
                tokenTable: this.tokenTable,
                vpc,
                managementKeySecretName: this.managementKeySecretName,
                ...(config.roles &&
                {
                    role: Role.fromRoleName(scope, 'AuthorizerRole', config.roles.RestApiAuthorizerRole),
                })
            });
            this.authorizer = authorizer.authorizer;
        }

        const restApi = new RestApi(scope, `${scope.node.id}-RestApi`, {
            description: 'Base API Gateway for LISA.',
            endpointConfiguration: { types: [config.privateEndpoints ? EndpointType.PRIVATE : EndpointType.REGIONAL] },
            deploy: true,
            deployOptions,
            defaultCorsPreflightOptions: {
                allowOrigins: Cors.ALL_ORIGINS,
                allowHeaders: [...Cors.DEFAULT_HEADERS],
            },
            // Support binary media types used for documentation images and fonts
            binaryMediaTypes: ['font/*', 'image/*'],
        });


        this.restApi = restApi;
        this.restApiId = restApi.restApiId;
        this.rootResourceId = restApi.restApiRootResourceId;
        this.restApiUrl = restApi.url;
    }

    private createManagementKeySecret (scope: Stack, config: Config, vpc: Vpc, securityGroups: ISecurityGroup[]): { managementKeySecretName: string } {
        const managementKeySecretName = `${config.deploymentName}-management-key`;

        const managementEventBus = new EventBus(scope, createCdkId([scope.node.id, 'managementEventBus']), {
            eventBusName: `${config.deploymentName}-management-events`,
        });

        const managementKeySecret = new Secret(scope, createCdkId([scope.node.id, 'managementKeySecret']), {
            secretName: managementKeySecretName,
            description: 'LISA management key secret',
            generateSecretString: {
                excludePunctuation: true,
                passwordLength: 16
            },
            removalPolicy: config.removalPolicy
        });

        const rotationLambda = new Function(scope, createCdkId([scope.node.id, 'managementKeyRotationLambda']), {
            runtime: getPythonRuntime(),
            handler: 'management_key.handler',
            code: Code.fromAsset(config.lambdaPath || LAMBDA_PATH),
            timeout: Duration.minutes(5),
            environment: {
                EVENT_BUS_NAME: managementEventBus.eventBusName,
            },
            role: new Role(scope, createCdkId([scope.node.id, 'managementKeyRotationRole']), {
                assumedBy: new ServicePrincipal('lambda.amazonaws.com'),
                managedPolicies: [
                    ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaVPCAccessExecutionRole'),
                ],
                inlinePolicies: {
                    'SecretsManagerRotation': new PolicyDocument({
                        statements: [
                            new PolicyStatement({
                                effect: Effect.ALLOW,
                                actions: [
                                    'secretsmanager:DescribeSecret',
                                    'secretsmanager:GetSecretValue',
                                    'secretsmanager:PutSecretValue',
                                    'secretsmanager:UpdateSecretVersionStage'
                                ],
                                resources: [managementKeySecret.secretArn]
                            }),
                            new PolicyStatement({
                                effect: Effect.ALLOW,
                                actions: ['events:PutEvents'],
                                resources: [managementEventBus.eventBusArn]
                            })
                        ]
                    })
                }
            }),
            securityGroups: securityGroups,
            vpc: vpc.vpc,
        });

        managementKeySecret.addRotationSchedule('RotationSchedule', {
            automaticallyAfter: Duration.days(30),
            rotationLambda: rotationLambda
        });

        new StringParameter(scope, createCdkId(['AppManagementKeySecretName']), {
            parameterName: `${config.deploymentPrefix}/${APP_MANAGEMENT_KEY}`,
            stringValue: managementKeySecret.secretName,
        });

        return { managementKeySecretName };
    }
}

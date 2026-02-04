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


import { Authorizer, CfnAccount, Cors, EndpointType, RestApi, StageOptions } from 'aws-cdk-lib/aws-apigateway';

import { AttributeType, BillingMode, ProjectionType, TableEncryption } from 'aws-cdk-lib/aws-dynamodb';

import { CustomAuthorizer } from '../api-base/authorizer';
import { CfnResource, Duration, RemovalPolicy, Stack, StackProps } from 'aws-cdk-lib';
import { ITable, Table } from 'aws-cdk-lib/aws-dynamodb';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';
import { Code, Function, IFunction, LayerVersion } from 'aws-cdk-lib/aws-lambda';

import { createCdkId } from '../core/utils';
import { Vpc } from '../networking/vpc';
import { APP_MANAGEMENT_KEY, BaseProps, Config } from '../schema';
import {
    Effect,
    ManagedPolicy,
    PolicyStatement,
    Role,
    ServicePrincipal,
} from 'aws-cdk-lib/aws-iam';
import { Secret } from 'aws-cdk-lib/aws-secretsmanager';
import { LAMBDA_PATH } from '../util';
import { getPythonRuntime } from '../api-base/utils';
import { ISecurityGroup } from 'aws-cdk-lib/aws-ec2';
import { EventBus } from 'aws-cdk-lib/aws-events';
import { Bucket, BucketEncryption, HttpMethods } from 'aws-cdk-lib/aws-s3';

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
    public readonly iamAuthSetupFn: IFunction;
    public readonly imagesBucket: Bucket;

    constructor (scope: Stack, id: string, props: LisaApiBaseProps) {
        super(scope, id);

        const { config, vpc, securityGroups } = props;

        // Get bucket access logs bucket
        const bucketAccessLogsBucket = Bucket.fromBucketArn(scope, 'BucketAccessLogsBucket',
            StringParameter.valueForStringParameter(scope, `${config.deploymentPrefix}/bucket/bucket-access-logs`)
        );

        // Create Images S3 bucket for generated images and videos
        // This is created in API Base stack so it's available to both Chat and Serve stacks
        this.imagesBucket = new Bucket(scope, 'GeneratedImagesBucket', {
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
            serverAccessLogsPrefix: 'logs/generated-images-bucket/',
            encryption: BucketEncryption.S3_MANAGED
        });

        // Store bucket name in SSM for cross-stack access
        new StringParameter(scope, 'GeneratedImagesBucketNameParameter', {
            parameterName: `${config.deploymentPrefix}/generatedImagesBucketName`,
            stringValue: this.imagesBucket.bucketName,
            description: 'S3 bucket name for generated images and videos',
        });

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
            deletionProtection: config.removalPolicy !== RemovalPolicy.DESTROY,
        });

        // Set DeletionPolicy to RetainExceptOnCreate to allow CloudFormation to import existing tables
        const cfnTokenTable = tokenTable.node.defaultChild as CfnResource;
        cfnTokenTable.applyRemovalPolicy(RemovalPolicy.RETAIN_ON_UPDATE_OR_DELETE);

        // Add GSI for querying tokens by username
        tokenTable.addGlobalSecondaryIndex({
            indexName: 'username-index',
            partitionKey: { name: 'username', type: AttributeType.STRING },
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

        // Create shared IAM auth setup Lambda for PGVector databases
        // This Lambda is used by Serve, RAG, and vector_store_deployer stacks
        this.iamAuthSetupFn = this.createIamAuthSetupLambda(scope, config, vpc, securityGroups);

        // Create IAM role for API Gateway to write logs to CloudWatch
        // This is an account-level setting required before enabling API Gateway logging
        const apiGatewayCloudWatchRole = new Role(scope, 'ApiGatewayCloudWatchRole', {
            assumedBy: new ServicePrincipal('apigateway.amazonaws.com'),
            managedPolicies: [
                ManagedPolicy.fromAwsManagedPolicyName('service-role/AmazonAPIGatewayPushToCloudWatchLogs'), // pragma: allowlist secret
            ],
        });

        // Configure API Gateway account settings with the CloudWatch role
        const apiGatewayAccount = new CfnAccount(scope, 'ApiGatewayAccount', {
            cloudWatchRoleArn: apiGatewayCloudWatchRole.roleArn,
        });

        // Ensure the role is created before the account settings
        apiGatewayAccount.node.addDependency(apiGatewayCloudWatchRole);

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
            endpointTypes: [config.privateEndpoints ? EndpointType.PRIVATE : EndpointType.REGIONAL],
            deploy: true,
            deployOptions,
            defaultCorsPreflightOptions: {
                allowOrigins: Cors.ALL_ORIGINS,
                allowHeaders: [...Cors.DEFAULT_HEADERS],
            },
            // Support binary media types used for documentation images and fonts
            binaryMediaTypes: ['font/*', 'image/*'],
        });

        // Ensure API Gateway account settings (CloudWatch role) are configured before the API stage
        restApi.node.addDependency(apiGatewayAccount);


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

        // Create the role first without the secret policy to avoid circular dependency
        // The circular dependency occurs when:
        // 1. Role has inline policy referencing secret ARN
        // 2. Secret's rotation schedule references the role
        // 3. Secret's auto-created KMS key policy references the role
        const rotationRole = new Role(scope, createCdkId([scope.node.id, 'managementKeyRotationRole']), {
            assumedBy: new ServicePrincipal('lambda.amazonaws.com'),
            managedPolicies: [
                ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaVPCAccessExecutionRole'),
            ],
        });

        // Grant EventBus permissions to the role
        rotationRole.addToPolicy(new PolicyStatement({
            effect: Effect.ALLOW,
            actions: ['events:PutEvents'],
            resources: [managementEventBus.eventBusArn]
        }));

        const managementKeySecret = new Secret(scope, createCdkId([scope.node.id, 'managementKeySecret']), {
            secretName: managementKeySecretName,
            description: 'LISA management key secret',
            generateSecretString: {
                excludePunctuation: true,
                passwordLength: 16
            },
            removalPolicy: config.removalPolicy
        });

        // Grant secret permissions after secret is created using CDK's grant methods
        // This avoids circular dependency by letting CDK manage the dependency order
        managementKeySecret.grantRead(rotationRole);
        managementKeySecret.grantWrite(rotationRole);

        const rotationLambda = new Function(scope, createCdkId([scope.node.id, 'managementKeyRotationLambda']), {
            runtime: getPythonRuntime(),
            handler: 'management_key.handler',
            code: Code.fromAsset(config.lambdaPath || LAMBDA_PATH),
            timeout: Duration.minutes(5),
            environment: {
                EVENT_BUS_NAME: managementEventBus.eventBusName,
            },
            role: rotationRole,
            securityGroups: securityGroups,
            vpc: vpc.vpc,
            vpcSubnets: vpc.subnetSelection
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

    /**
     * Creates a shared Lambda for IAM authentication setup on PGVector databases.
     * This Lambda creates IAM database users and deletes bootstrap secrets.
     * It's shared across Serve, RAG, and vector_store_deployer stacks.
     */
    private createIamAuthSetupLambda (scope: Stack, config: Config, vpc: Vpc, securityGroups: ISecurityGroup[]): IFunction {
        // Create IAM role for the Lambda
        const iamAuthSetupRole = new Role(scope, 'IamAuthSetupRole', {
            assumedBy: new ServicePrincipal('lambda.amazonaws.com'),
            managedPolicies: [
                ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaVPCAccessExecutionRole'),
            ],
        });

        // Grant permissions to read/delete secrets (specific secrets will be passed via event)
        iamAuthSetupRole.addToPolicy(new PolicyStatement({
            effect: Effect.ALLOW,
            actions: ['secretsmanager:GetSecretValue', 'secretsmanager:DeleteSecret'],
            resources: [`arn:${config.partition}:secretsmanager:${config.region}:${config.accountNumber}:secret:*`],
        }));

        // Get common layer for psycopg2
        const commonLayer = LayerVersion.fromLayerVersionArn(
            scope,
            'IamAuthCommonLayer',
            StringParameter.valueForStringParameter(scope, `${config.deploymentPrefix}/layerVersion/common`),
        );

        const iamAuthSetupFn = new Function(scope, 'IamAuthSetupFn', {
            functionName: createCdkId([config.deploymentName, config.deploymentStage, 'iam_auth_setup']),
            runtime: getPythonRuntime(),
            handler: 'utilities.db_setup_iam_auth.handler',
            code: Code.fromAsset(config.lambdaPath || LAMBDA_PATH),
            timeout: Duration.minutes(2),
            memorySize: 256,
            role: iamAuthSetupRole,
            vpc: vpc.vpc,
            vpcSubnets: vpc.subnetSelection,
            securityGroups: securityGroups,
            layers: [commonLayer],
        });

        // Store the IAM auth setup Lambda ARN in SSM for other stacks to use
        new StringParameter(scope, 'IamAuthSetupFnArnParam', {
            parameterName: `${config.deploymentPrefix}/iamAuthSetupFnArn`,
            stringValue: iamAuthSetupFn.functionArn,
            description: 'ARN of the shared IAM auth setup Lambda for PGVector databases',
        });

        // Store the IAM auth setup Lambda role ARN in SSM for granting secret permissions
        new StringParameter(scope, 'IamAuthSetupRoleArnParam', {
            parameterName: `${config.deploymentPrefix}/iamAuthSetupRoleArn`,
            stringValue: iamAuthSetupRole.roleArn,
            description: 'ARN of the IAM auth setup Lambda role for granting secret permissions',
        });

        return iamAuthSetupFn;
    }
}

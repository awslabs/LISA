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

import crypto from 'node:crypto';

import { IAuthorizer, RestApi } from 'aws-cdk-lib/aws-apigateway';
import { ISecurityGroup } from 'aws-cdk-lib/aws-ec2';
import { Repository } from 'aws-cdk-lib/aws-ecr';
import {
    Effect,
    IRole,
    ManagedPolicy,
    Policy,
    PolicyDocument,
    PolicyStatement,
    Role,
    ServicePrincipal,
} from 'aws-cdk-lib/aws-iam';
import { Code, Function, LayerVersion } from 'aws-cdk-lib/aws-lambda';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { CustomResource, Duration } from 'aws-cdk-lib';
import { Provider } from 'aws-cdk-lib/custom-resources';
import { Construct } from 'constructs';

import { getPythonRuntime, PythonLambdaFunction, registerAPIEndpoint } from '../api-base/utils';
import { APP_MANAGEMENT_KEY, BaseProps } from '../schema';
import { Vpc } from '../networking/vpc';

import { ECSModelDeployer } from './ecs-model-deployer';
import { DockerImageBuilder } from './docker-image-builder';
import { DeleteModelStateMachine } from './state-machine/delete-model';
import { AttributeType, BillingMode, ITable, Table, TableEncryption } from 'aws-cdk-lib/aws-dynamodb';
import { CreateModelStateMachine } from './state-machine/create-model';
import { UpdateModelStateMachine } from './state-machine/update-model';
import { Secret } from 'aws-cdk-lib/aws-secretsmanager';
import { createCdkId, createLambdaRole } from '../core/utils';
import { Roles } from '../core/iam/roles';
import { LAMBDA_PATH } from '../util';

/**
 * Properties for ModelsApi Construct.
 *
 * @property {Vpc} vpc - Stack VPC
 * @property {string} restApiId - REST APIGW for UI and Lambdas
 * @property {IAuthorizer} authorizer - APIGW authorizer
 * @property {ISecurityGroup[]} securityGroups - Security groups for Lambdas
 */
type ModelsApiProps = BaseProps & {
    authorizer?: IAuthorizer;
    guardrailsTable: ITable;
    lisaServeEndpointUrlPs?: StringParameter;
    restApiId: string;
    rootResourceId: string;
    securityGroups: ISecurityGroup[];
    vpc: Vpc;
};

/**
 * API for managing Models
 */
export class ModelsApi extends Construct {
    constructor (scope: Construct, id: string, props: ModelsApiProps) {
        super(scope, id);

        const { authorizer, config, guardrailsTable, restApiId, rootResourceId, securityGroups, vpc } = props;
        const lambdaPath = config.lambdaPath || LAMBDA_PATH;

        const lisaServeEndpointUrlPs = props.lisaServeEndpointUrlPs ?? StringParameter.fromStringParameterName(
            scope,
            createCdkId(['LisaRestApiUri', 'StringParameter']),
            `${config.deploymentPrefix}/lisaServeRestApiUri`,
        );

        // Get common layer based on arn from SSM due to issues with cross stack references
        const commonLambdaLayer = LayerVersion.fromLayerVersionArn(
            this,
            'models-common-lambda-layer',
            StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/layerVersion/common`),
        );

        const fastapiLambdaLayer = LayerVersion.fromLayerVersionArn(
            this,
            'models-fastapi-lambda-layer',
            StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/layerVersion/fastapi`),
        );

        const lambdaLayers = [commonLambdaLayer, fastapiLambdaLayer];
        const restApi = RestApi.fromRestApiAttributes(this, 'RestApi', {
            restApiId: restApiId,
            rootResourceId: rootResourceId,
        });

        // generates a random hexadecimal string of a specific length
        const generateDisambiguator = (size: number): string =>
            Buffer.from(
                // one byte is 2 hex characters so only generate ceil(size/2) bytes of randomness
                crypto.getRandomValues(new Uint8Array(Math.ceil(size / 2))),
            )
                .toString('hex')
                .slice(0, size);

        const modelTable = new Table(this, 'ModelTable', {
            partitionKey: {
                name: 'model_id',
                type: AttributeType.STRING
            },
            billingMode: BillingMode.PAY_PER_REQUEST,
            encryption: TableEncryption.AWS_MANAGED,
            removalPolicy: config.removalPolicy,
        });

        // Create SSM parameter for model table name
        new StringParameter(this, 'ModelTableNameParameter', {
            parameterName: `${config.deploymentPrefix}/modelTableName`,
            stringValue: modelTable.tableName,
        });

        const ecsModelBuildRepo = new Repository(this, 'ecs-model-build-repo');

        const ecsModelDeployer = new ECSModelDeployer(this, 'ecs-model-deployer', {
            securityGroupId: vpc.securityGroups.ecsModelAlbSg.securityGroupId,
            config: config,
            vpc: vpc
        });

        const dockerImageBuilder = new DockerImageBuilder(this, 'docker-image-builder', {
            ecrUri: ecsModelBuildRepo.repositoryUri,
            mountS3DebUrl: config.mountS3DebUrl!,
            config: config,
            securityGroups: [vpc.securityGroups.lambdaSg],
            vpc
        });

        const managementKeyName = StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/${APP_MANAGEMENT_KEY}`);

        const stateMachineExecutionRole = config.roles ?
            { executionRole: Role.fromRoleName(this, Roles.MODEL_SFN_ROLE, config.roles.ModelSfnRole) } :
            undefined;

        const stateMachinesLambdaRole = config.roles ?
            Role.fromRoleName(this, Roles.MODEL_SFN_LAMBDA_ROLE, config.roles.ModelsSfnLambdaRole) :
            this.createStateMachineLambdaRole(modelTable.tableArn, guardrailsTable.tableArn, dockerImageBuilder.dockerImageBuilderFn.functionArn,
                ecsModelDeployer.ecsModelDeployerFn.functionArn, lisaServeEndpointUrlPs.parameterArn, managementKeyName, config);

        const createModelStateMachine = new CreateModelStateMachine(this, 'CreateModelWorkflow', {
            config: config,
            modelTable: modelTable,
            guardrailsTable: guardrailsTable,
            lambdaLayers: lambdaLayers,
            role: stateMachinesLambdaRole,
            vpc: vpc,
            securityGroups: securityGroups,
            dockerImageBuilderFnArn: dockerImageBuilder.dockerImageBuilderFn.functionArn,
            ecsModelDeployerFnArn: ecsModelDeployer.ecsModelDeployerFn.functionArn,
            ecsModelImageRepository: ecsModelBuildRepo,
            restApiContainerEndpointPs: lisaServeEndpointUrlPs,
            managementKeyName: managementKeyName,
            ...(stateMachineExecutionRole),
        });

        const deleteModelStateMachine = new DeleteModelStateMachine(this, 'DeleteModelWorkflow', {
            config: config,
            modelTable: modelTable,
            guardrailsTable: guardrailsTable,
            lambdaLayers: lambdaLayers,
            role: stateMachinesLambdaRole,
            vpc: vpc,
            securityGroups: securityGroups,
            restApiContainerEndpointPs: lisaServeEndpointUrlPs,
            managementKeyName: managementKeyName,
            ...(stateMachineExecutionRole),
        });

        const updateModelStateMachine = new UpdateModelStateMachine(this, 'UpdateModelWorkflow', {
            config: config,
            modelTable: modelTable,
            guardrailsTable: guardrailsTable,
            lambdaLayers: lambdaLayers,
            role: stateMachinesLambdaRole,
            vpc: vpc,
            securityGroups: securityGroups,
            restApiContainerEndpointPs: lisaServeEndpointUrlPs,
            managementKeyName: managementKeyName,
            ...(stateMachineExecutionRole),
        });

        const scheduleManagementLambda = new Function(this, 'ScheduleManagement', {
            runtime: getDefaultRuntime(),
            handler: 'models.scheduling.schedule_management.lambda_handler',
            code: Code.fromAsset(lambdaPath),
            layers: lambdaLayers,
            environment: {
                MODEL_TABLE_NAME: modelTable.tableName,
            },
            role: stateMachinesLambdaRole,
            vpc: vpc.vpc,
            securityGroups: securityGroups,
            timeout: Duration.minutes(5),
            description: 'Manages Auto Scaling scheduled actions for LISA model scheduling',
        });

        const environment = {
            LISA_API_URL_PS_NAME: lisaServeEndpointUrlPs.parameterName,
            REST_API_VERSION: 'v2',
            RESTAPI_SSL_CERT_ARN: config.restApiConfig?.sslCertIamArn ?? '',
            CREATE_SFN_ARN: createModelStateMachine.stateMachineArn,
            DELETE_SFN_ARN: deleteModelStateMachine.stateMachineArn,
            UPDATE_SFN_ARN: updateModelStateMachine.stateMachineArn,
            MODEL_TABLE_NAME: modelTable.tableName,
            SCHEDULE_MANAGEMENT_FUNCTION_NAME: scheduleManagementLambda.functionName,
            GUARDRAILS_TABLE_NAME: guardrailsTable.tableName,
        };

        const lambdaRole: IRole = createLambdaRole(this, config.deploymentName, 'ModelApi', modelTable.tableArn, config.roles?.ModelApiRole);
        // create proxy handler
        const lambdaFunction = registerAPIEndpoint(
            this,
            restApi,
            lambdaPath,
            lambdaLayers,
            {
                name: 'handler',
                resource: 'models',
                description: 'Manage model',
                path: 'models/{proxy+}',
                method: 'ANY',
                environment
            },
            getPythonRuntime(),
            vpc,
            securityGroups,
            authorizer,
            lambdaRole,
        );
        lisaServeEndpointUrlPs.grantRead(lambdaFunction.role!);

        if (config.restApiConfig?.sslCertIamArn) {
            const certPerms = new Policy(this, 'ModelsApiCertPerms', {
                statements: [
                    new PolicyStatement({
                        actions: ['iam:GetServerCertificate'],
                        resources: [config.restApiConfig?.sslCertIamArn],
                        effect: Effect.ALLOW,
                    })
                ]
            });
            lambdaFunction.role!.attachInlinePolicy(certPerms);
            stateMachinesLambdaRole.attachInlinePolicy(certPerms);
        }

        const apis: PythonLambdaFunction[] = [
            // create endpoint for /models without a trailing slash but reuse
            // the proxy lambda so there aren't cold start issues
            {
                name: 'handler',
                resource: 'models',
                description: 'Get models',
                path: 'models',
                method: 'GET',
                disambiguator: generateDisambiguator(4),
                existingFunction: lambdaFunction.functionArn,
            },
            {
                name: 'handler',
                resource: 'models',
                description: 'Create model',
                path: 'models',
                method: 'POST',
                disambiguator: generateDisambiguator(4),
                existingFunction: lambdaFunction.functionArn,
            },
            // create an endpoints for the docs
            {
                name: 'docs',
                resource: 'models',
                description: 'Manage model',
                path: 'docs',
                method: 'GET',
                disableAuthorizer: true,
                environment
            },
            {
                name: 'handler',
                resource: 'models',
                description: 'Get API definition',
                path: 'openapi.json',
                method: 'GET',
                disambiguator: generateDisambiguator(4),
                existingFunction: lambdaFunction.functionArn,
                disableAuthorizer: true,
            },
        ];

        apis.forEach((f) => {
            registerAPIEndpoint(
                this,
                restApi,
                lambdaPath,
                lambdaLayers,
                f,
                getPythonRuntime(),
                vpc,
                securityGroups,
                authorizer,
                lambdaRole,
            );
        });

        const workflowPermissions = new Policy(this, 'ModelsApiStateMachinePerms', {
            statements: [
                new PolicyStatement({
                    effect: Effect.ALLOW,
                    actions: [
                        'states:StartExecution',
                    ],
                    resources: [
                        createModelStateMachine.stateMachineArn,
                        deleteModelStateMachine.stateMachineArn,
                        updateModelStateMachine.stateMachineArn,
                    ],
                }),
                new PolicyStatement({
                    effect: Effect.ALLOW,
                    actions: [
                        'dynamodb:GetItem',
                        'dynamodb:Scan',
                    ],
                    resources: [
                        modelTable.tableArn,
                        `${modelTable.tableArn}/*`
                    ],
                }),
                new PolicyStatement({
                    effect: Effect.ALLOW,
                    actions: [
                        'dynamodb:GetItem',
                        'dynamodb:PutItem',
                        'dynamodb:UpdateItem',
                        'dynamodb:DeleteItem',
                        'dynamodb:Query',
                        'dynamodb:Scan',
                    ],
                    resources: [
                        guardrailsTable.tableArn,
                        `${guardrailsTable.tableArn}/*`
                    ],
                }),
                new PolicyStatement({
                    effect: Effect.ALLOW,
                    actions: [
                        'autoscaling:DescribeAutoScalingGroups',
                    ],
                    resources: ['*'],  // we do not know ASG names in advance
                }),
                new PolicyStatement({
                    effect: Effect.ALLOW,
                    actions: [
                        'lambda:InvokeFunction',
                    ],
                    resources: [
                        scheduleManagementLambda.functionArn,
                    ],
                }),
            ]
        });
        lambdaFunction.role!.attachInlinePolicy(workflowPermissions);

        // Model API key cleanup - runs once per deployment version
        const modelApiKeyCleanupLambda = new Function(this, 'ModelApiKeyCleanup', {
            runtime: getPythonRuntime(),
            handler: 'models.model_api_key_cleanup.lambda_handler',
            code: Code.fromAsset(lambdaPath),
            layers: lambdaLayers,
            environment: {
                LISA_API_URL_PS_NAME: lisaServeEndpointUrlPs.parameterName,
                MANAGEMENT_KEY_NAME: managementKeyName,
                REST_API_VERSION: 'v2',
                DEPLOYMENT_PREFIX: config.deploymentPrefix || '',
            },
            role: stateMachinesLambdaRole,
            vpc: vpc.vpc,
            securityGroups: securityGroups,
            timeout: Duration.minutes(5),
            description: 'Remove api_key from existing Bedrock models to fix Invalid API Key format errors',
        });

        // Run cleanup automatically during deployment
        const cleanupProvider = new Provider(this, 'ModelApiKeyCleanupProvider', {
            onEventHandler: modelApiKeyCleanupLambda,
        });

        new CustomResource(this, 'ModelApiKeyCleanupResource', {
            serviceToken: cleanupProvider.serviceToken,
            properties: {
                // Only runs once - increment this version number if you need to run cleanup again
                CleanupVersion: '1',
            },
        });

    }

    /**
     * Creates a role for the state machine lambdas
     * @param modelTableArn - Arn of the model table
     * @param dockerImageBuilderFnArn - Arn of the docker image builder lambda
     * @param ecsModelDeployerFnArn - Arn of the ecs model deployer lambda
     * @param lisaServeEndpointUrlParamArn - Arn of the lisa serve endpoint url parameter
     * @param managementKeyName - Name of the management key secret
     * @returns The created role
     */
    createStateMachineLambdaRole (modelTableArn: string, guardrailTableArn: string ,dockerImageBuilderFnArn: string, ecsModelDeployerFnArn: string, lisaServeEndpointUrlParamArn: string, managementKeyName: string, config: any): IRole {
        return new Role(this, Roles.MODEL_SFN_LAMBDA_ROLE, {
            assumedBy: new ServicePrincipal('lambda.amazonaws.com'),
            managedPolicies: [
                ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaVPCAccessExecutionRole'),
            ],
            inlinePolicies: {
                lambdaPermissions: new PolicyDocument({
                    statements: [
                        new PolicyStatement({
                            effect: Effect.ALLOW,
                            actions: [
                                'dynamodb:DeleteItem',
                                'dynamodb:GetItem',
                                'dynamodb:PutItem',
                                'dynamodb:UpdateItem',
                                'dynamodb:Scan',
                                'dynamodb:Query'
                            ],
                            resources: [
                                modelTableArn,
                                `${modelTableArn}/*`,
                                guardrailTableArn,
                                `${guardrailTableArn}/*`,
                            ]
                        }),
                        new PolicyStatement({
                            effect: Effect.ALLOW,
                            actions: [
                                'cloudformation:CreateStack',
                                'cloudformation:DeleteStack',
                                'cloudformation:DescribeStacks',
                            ],
                            resources: [
                                'arn:*:cloudformation:*:*:stack/*',
                            ],
                        }),
                        new PolicyStatement({
                            effect: Effect.ALLOW,
                            actions: [
                                'lambda:InvokeFunction'
                            ],
                            resources: [
                                dockerImageBuilderFnArn,
                                ecsModelDeployerFnArn
                            ]
                        }),
                        new PolicyStatement({
                            effect: Effect.ALLOW,
                            actions: [
                                'ecr:DescribeImages',
                                'ecr:DescribeRepositories',
                                'ecr:GetRepositoryPolicy',
                                'ecr:ListImages'
                            ],
                            resources: ['*']
                        }),
                        new PolicyStatement({
                            effect: Effect.ALLOW,
                            actions: [
                                'ec2:CreateNetworkInterface',
                                'ec2:DescribeNetworkInterfaces',
                                'ec2:DescribeSubnets',
                                'ec2:DeleteNetworkInterface',
                                'ec2:AssignPrivateIpAddresses',
                                'ec2:UnassignPrivateIpAddresses'
                            ],
                            resources: ['*'],
                        }),
                        new PolicyStatement({
                            effect: Effect.ALLOW,
                            actions: [
                                'ec2:TerminateInstances'
                            ],
                            resources: ['*'],
                            conditions: {
                                'StringEquals': {'aws:ResourceTag/lisa_temporary_instance': 'true'}
                            }
                        }),
                        new PolicyStatement({
                            effect: Effect.ALLOW,
                            actions: [
                                'secretsmanager:GetSecretValue'
                            ],
                            resources: [`${Secret.fromSecretNameV2(this, 'ManagementKeySecret', managementKeyName).secretArn}-??????`],  // question marks required to resolve the ARN correctly
                        }),
                        new PolicyStatement({
                            effect: Effect.ALLOW,
                            actions: [
                                'autoscaling:DescribeAutoScalingGroups',
                                'autoscaling:UpdateAutoScalingGroup',
                                'autoscaling:PutScheduledUpdateGroupAction',
                                'autoscaling:DeleteScheduledAction',
                                'autoscaling:DescribeScheduledActions',
                            ],
                            resources: ['*'],  // We do not know the ASG names in advance
                        }),
                        new PolicyStatement({
                            effect: Effect.ALLOW,
                            actions: [
                                'ecs:DescribeTaskDefinition',
                                'ecs:RegisterTaskDefinition',
                                'ecs:UpdateService',
                                'ecs:DescribeServices',
                            ],
                            resources: ['*'],  // ECS resources are dynamic and created by CloudFormation
                        }),
                        new PolicyStatement({
                            effect: Effect.ALLOW,
                            actions: [
                                'cloudformation:DescribeStackResources',
                            ],
                            resources: [
                                'arn:*:cloudformation:*:*:stack/*',
                            ],
                        }),
                        new PolicyStatement({
                            effect: Effect.ALLOW,
                            actions: [
                                'iam:PassRole',
                            ],
                            resources: ['*'],
                        }),
                        new PolicyStatement({
                            effect: Effect.ALLOW,
                            actions: [
                                'bedrock:InvokeModel',
                                'bedrock:InvokeModelWithResponseStream',
                                'bedrock:ApplyGuardrail'
                            ],
                            resources: ['*'],  // Bedrock model ARNs are dynamic and region-specific
                        }),
                        new PolicyStatement({
                            effect: Effect.ALLOW,
                            actions: [
                                'ssm:GetParameter',
                            ],
                            resources: [
                                lisaServeEndpointUrlParamArn,
                                `arn:${config.partition}:ssm:${config.region}:${config.accountNumber}:parameter${config.deploymentPrefix}/lisaServeRestApiUri`,
                                `arn:${config.partition}:ssm:${config.region}:${config.accountNumber}:parameter/LISA-management-key`,
                                `arn:${config.partition}:ssm:${config.region}:${config.accountNumber}:parameter${config.deploymentPrefix}/LiteLLMDbConnectionInfo`,
                                `arn:${config.partition}:ssm:${config.region}:${config.accountNumber}:parameter${config.deploymentPrefix}/modelTableName`,
                            ],
                        }),
                        new PolicyStatement({
                            effect: Effect.ALLOW,
                            actions: [
                                'secretsmanager:GetSecretValue',
                            ],
                            resources: [
                                `arn:${config.partition}:secretsmanager:${config.region}:${config.accountNumber}:secret:*`,  // LiteLLM DB password secret
                            ],
                        }),
                    ]
                }),
            }
        });
    }

    createStateMachineExecutionRole (): IRole {
        return new Role(this, Roles.MODEL_SFN_ROLE, {
            assumedBy: new ServicePrincipal('states.amazonaws.com'),
            managedPolicies: [
                ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaRole'),
            ]
        });
    }
}

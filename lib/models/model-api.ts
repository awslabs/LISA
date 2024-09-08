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
import { LayerVersion } from 'aws-cdk-lib/aws-lambda';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';

import { PythonLambdaFunction, registerAPIEndpoint } from '../api-base/utils';
import { BaseProps } from '../schema';
import { Vpc } from '../networking/vpc';

import { ECSModelDeployer } from './ecs-model-deployer';
import { DockerImageBuilder } from './docker-image-builder';
import { DeleteModelStateMachine } from './state-machine/delete-model';
import { AttributeType, BillingMode, Table, TableEncryption } from 'aws-cdk-lib/aws-dynamodb';
import { CreateModelStateMachine } from './state-machine/create-model';

/**
 * Properties for ModelsApi Construct.
 *
 * @property {Vpc} vpc - Stack VPC
 * @property {Layer} commonLayer - Lambda layer for all Lambdas.
 * @property {IRestApi} restAPI - REST APIGW for UI and Lambdas
 * @property {IRole} lambdaExecutionRole - Execution role for lambdas
 * @property {IAuthorizer} authorizer - APIGW authorizer
 * @property {ISecurityGroup[]} securityGroups - Security groups for Lambdas
 */
type ModelsApiProps = BaseProps & {
    authorizer: IAuthorizer;
    lambdaExecutionRole?: IRole;
    lisaServeEndpointUrlPs: StringParameter;
    restApiId: string;
    rootResourceId: string;
    securityGroups?: ISecurityGroup[];
    vpc: Vpc;
};

/**
 * API for managing Models
 */
export class ModelsApi extends Construct {
    constructor (scope: Construct, id: string, props: ModelsApiProps) {
        super(scope, id);

        const { authorizer, config, lambdaExecutionRole, lisaServeEndpointUrlPs, restApiId, rootResourceId, securityGroups, vpc } = props;

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

        const ecsModelBuildRepo = new Repository(this, 'ecs-model-build-repo');

        const ecsModelDeployer = new ECSModelDeployer(this, 'ecs-model-deployer', {
            securityGroupId: vpc.securityGroups.ecsModelAlbSg.securityGroupId,
            vpcId: vpc.vpc.vpcId,
            config: config
        });

        const dockerImageBuilder = new DockerImageBuilder(this, 'docker-image-builder', {
            ecrUri: ecsModelBuildRepo.repositoryUri,
            mountS3DebUrl: config.mountS3DebUrl!
        });

        const stateMachinesLambdaRole = new Role(this, 'ModelsSfnLambdaRole', {
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
                            ],
                            resources: [
                                modelTable.tableArn,
                                `${modelTable.tableArn}/*`,
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
                                dockerImageBuilder.dockerImageBuilderFn.functionArn,
                                ecsModelDeployer.ecsModelDeployerFn.functionArn
                            ]
                        }),
                        new PolicyStatement({
                            effect: Effect.ALLOW,
                            actions: [
                                'ecr:DescribeImages'
                            ],
                            resources: ['*']
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
                                'ssm:GetParameter'
                            ],
                            resources: [
                                lisaServeEndpointUrlPs.parameterArn
                            ],
                        }),
                        new PolicyStatement({
                            effect: Effect.ALLOW,
                            actions: [
                                'secretsmanager:GetSecretValue'
                            ],
                            resources: ['*'],
                        }),
                    ]
                }),
            }
        });

        const managementKeyName = StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/managementKeySecretName`);

        const createModelStateMachine = new CreateModelStateMachine(this, 'CreateModelWorkflow', {
            config: config,
            modelTable: modelTable,
            lambdaLayers: [commonLambdaLayer, fastapiLambdaLayer],
            role: stateMachinesLambdaRole,
            vpc: vpc.vpc,
            securityGroups: securityGroups,
            dockerImageBuilderFnArn: dockerImageBuilder.dockerImageBuilderFn.functionArn,
            ecsModelDeployerFnArn: ecsModelDeployer.ecsModelDeployerFn.functionArn,
            ecsModelImageRepository: ecsModelBuildRepo,
            restApiContainerEndpointPs: lisaServeEndpointUrlPs,
            managementKeyName
        });

        const deleteModelStateMachine = new DeleteModelStateMachine(this, 'DeleteModelWorkflow', {
            config: config,
            modelTable: modelTable,
            lambdaLayers: [commonLambdaLayer, fastapiLambdaLayer],
            role: stateMachinesLambdaRole,
            vpc: vpc.vpc,
            securityGroups: securityGroups,
            restApiContainerEndpointPs: lisaServeEndpointUrlPs,
        });

        const environment = {
            LISA_API_URL_PS_NAME: lisaServeEndpointUrlPs.parameterName,
            REST_API_VERSION: config.restApiConfig.apiVersion,
            RESTAPI_SSL_CERT_ARN: config.restApiConfig.loadBalancerConfig.sslCertIamArn ?? '',
            CREATE_SFN_ARN: createModelStateMachine.stateMachineArn,
            DELETE_SFN_ARN: deleteModelStateMachine.stateMachineArn,
            MODEL_TABLE_NAME: modelTable.tableName,
        };

        // create proxy handler
        const lambdaFunction = registerAPIEndpoint(
            this,
            restApi,
            authorizer,
            config.lambdaSourcePath,
            [commonLambdaLayer, fastapiLambdaLayer],
            {
                name: 'handler',
                resource: 'models',
                description: 'Manage model',
                path: 'models/{proxy+}',
                method: 'ANY',
                environment
            },
            config.lambdaConfig.pythonRuntime,
            lambdaExecutionRole,
            vpc.vpc,
            securityGroups,
        );
        lisaServeEndpointUrlPs.grantRead(lambdaFunction.role!);

        if (config.restApiConfig.loadBalancerConfig.sslCertIamArn) {
            const additionalPerms = new Policy(this, 'ModelsApiAdditionalPerms', {
                statements: [
                    new PolicyStatement({
                        actions: ['iam:GetServerCertificate'],
                        resources: [config.restApiConfig.loadBalancerConfig.sslCertIamArn],
                        effect: Effect.ALLOW,
                    })
                ]
            });
            lambdaFunction.role!.attachInlinePolicy(additionalPerms);
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
                authorizer,
                config.lambdaSourcePath,
                [commonLambdaLayer],
                f,
                config.lambdaConfig.pythonRuntime,
                lambdaExecutionRole,
                vpc.vpc,
                securityGroups,
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
            ]
        });
        lambdaFunction.role!.attachInlinePolicy(workflowPermissions);
    }
}

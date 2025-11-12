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

import { Cors, IAuthorizer, RestApi } from 'aws-cdk-lib/aws-apigateway';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import { Effect, IRole, ManagedPolicy, Policy, PolicyDocument, PolicyStatement, Role, ServicePrincipal } from 'aws-cdk-lib/aws-iam';
import { ISecurityGroup } from 'aws-cdk-lib/aws-ec2';
import { IFunction, LayerVersion } from 'aws-cdk-lib/aws-lambda';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';

import { getDefaultRuntime, registerAPIEndpoint } from '../api-base/utils';
import { BaseProps } from '../schema';
import { createCdkId, createLambdaRole } from '../core/utils';
import { Vpc } from '../networking/vpc';
import { LAMBDA_PATH } from '../util';
import { McpServerDeployer } from './mcp-server-deployer';
import { CreateMcpServerStateMachine } from './state-machine/create-mcp-server';
import { DeleteMcpServerStateMachine } from './state-machine/delete-mcp-server';
import { UpdateMcpServerStateMachine } from './state-machine/update-mcp-server';
import { Bucket, HttpMethods } from 'aws-cdk-lib/aws-s3';
import { RemovalPolicy } from 'aws-cdk-lib';

type McpServerApiProps = {
    authorizer: IAuthorizer;
    restApiId: string;
    rootResourceId: string;
    securityGroups: ISecurityGroup[];
    vpc: Vpc;
} & BaseProps;

/**
 * API for managing MCP server dynamic hosting infrastructure
 */
export class McpServerApi extends Construct {
    readonly createStateMachineArn: string;
    readonly deleteStateMachineArn: string;
    readonly updateStateMachineArn: string;
    readonly mcpServerDeployerFn: IFunction;

    constructor (scope: Construct, id: string, props: McpServerApiProps) {
        super(scope, id);

        const { authorizer, config, restApiId, rootResourceId, securityGroups, vpc } = props;

        // Get common layer based on arn from SSM due to issues with cross stack references
        const commonLambdaLayer = LayerVersion.fromLayerVersionArn(
            this,
            'mcpserver-common-lambda-layer',
            StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/layerVersion/common`),
        );

        const fastapiLambdaLayer = LayerVersion.fromLayerVersionArn(
            this,
            'mcpserver-fastapi-lambda-layer',
            StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/layerVersion/fastapi`),
        );

        const lambdaLayers = [commonLambdaLayer, fastapiLambdaLayer];

        // Get lisa serve endpoint URL parameter
        const lisaServeEndpointUrlPs = StringParameter.fromStringParameterName(
            this,
            'lisaServeEndpointUrlPs',
            `${config.deploymentPrefix}/lisaServeRestApiUri`
        );

        // Get management key name
        const managementKeyName = StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/managementKeySecretName`);

        const mcpServersTable = new dynamodb.Table(this, 'HostMcpServerTable', {
            partitionKey: {
                name: 'id',
                type: dynamodb.AttributeType.STRING
            },
            billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption: dynamodb.TableEncryption.AWS_MANAGED,
            removalPolicy: config.removalPolicy,
        });

        const bucketAccessLogsBucket = Bucket.fromBucketArn(scope, 'BucketAccessLogsBucket',
            StringParameter.valueForStringParameter(scope, `${config.deploymentPrefix}/bucket/bucket-access-logs`)
        );

        const bucket = new Bucket(scope, createCdkId(['LISA', 'MCP-Hosting', config.deploymentName, config.deploymentStage]), {
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
            serverAccessLogsPrefix: 'logs/mcp-hosting-bucket/'
        });

        // Get reference to REST API first (will be reused)
        const restApi = RestApi.fromRestApiAttributes(this, 'RestApi', {
            restApiId: restApiId,
            rootResourceId: rootResourceId,
        });

        // Create or get the /mcp resource explicitly to capture its ID
        // This resource ID is needed for the deployer to reference it when creating server routes
        // We do this before registerAPIEndpoint so we can pass the ID to the deployer
        let mcpResource = restApi.root.getResource('mcp');
        if (!mcpResource) {
            mcpResource = restApi.root.addResource('mcp');
        }
        // Add CORS preflight support for the /mcp resource
        // This ensures OPTIONS method is available even if the resource already existed
        // addCorsPreflight is idempotent - it won't create duplicate OPTIONS methods
        mcpResource.addCorsPreflight({
            allowOrigins: Cors.ALL_ORIGINS,
            allowHeaders: Cors.DEFAULT_HEADERS,
        });
        const mcpResourceId = mcpResource.resourceId;

        // Create MCP server deployer
        // Pass authorizer ID so deployed servers can use the same authorizer
        const authorizerId = authorizer.authorizerId;
        const mcpServerDeployer = new McpServerDeployer(this, 'mcp-server-deployer', {
            securityGroupId: vpc.securityGroups.ecsModelAlbSg.securityGroupId,
            config: config,
            vpc: vpc,
            restApiId: restApiId,
            rootResourceId: rootResourceId,
            hostingBucketArn: bucket.bucketArn,
            mcpResourceId: mcpResourceId,
            authorizerId: authorizerId,
        });

        this.mcpServerDeployerFn = mcpServerDeployer.mcpServerDeployerFn;

        // Create state machine Lambda role
        const stateMachinesLambdaRole = this.createStateMachineLambdaRole(
            mcpServersTable.tableArn,
            mcpServerDeployer.mcpServerDeployerFn.functionArn,
            lisaServeEndpointUrlPs.parameterArn,
            managementKeyName,
            config
        );

        // Create state machine for creating MCP servers
        const createMcpServerStateMachine = new CreateMcpServerStateMachine(this, 'CreateMcpServerWorkflow', {
            config: config,
            mcpServerTable: mcpServersTable,
            lambdaLayers: lambdaLayers,
            role: stateMachinesLambdaRole,
            vpc: vpc,
            securityGroups: securityGroups,
            mcpServerDeployerFnArn: mcpServerDeployer.mcpServerDeployerFn.functionArn,
            managementKeyName: managementKeyName,
        });

        this.createStateMachineArn = createMcpServerStateMachine.stateMachineArn;

        // Create state machine for deleting MCP servers
        const deleteMcpServerStateMachine = new DeleteMcpServerStateMachine(this, 'DeleteMcpServerWorkflow', {
            config: config,
            mcpServerTable: mcpServersTable,
            lambdaLayers: lambdaLayers,
            role: stateMachinesLambdaRole,
            vpc: vpc,
            securityGroups: securityGroups,
        });

        this.deleteStateMachineArn = deleteMcpServerStateMachine.stateMachineArn;

        // Create state machine for updating MCP servers
        const updateMcpServerStateMachine = new UpdateMcpServerStateMachine(this, 'UpdateMcpServerWorkflow', {
            config: config,
            mcpServerTable: mcpServersTable,
            lambdaLayers: lambdaLayers,
            role: stateMachinesLambdaRole,
            vpc: vpc,
            securityGroups: securityGroups,
        });

        this.updateStateMachineArn = updateMcpServerStateMachine.stateMachineArn;

        const env = {
            MCP_SERVERS_TABLE_NAME: mcpServersTable.tableName,
            CREATE_MCP_SERVER_SFN_ARN: createMcpServerStateMachine.stateMachineArn,
            DELETE_MCP_SERVER_SFN_ARN: deleteMcpServerStateMachine.stateMachineArn,
            UPDATE_MCP_SERVER_SFN_ARN: updateMcpServerStateMachine.stateMachineArn,
            ADMIN_GROUP: config.authConfig?.adminGroup || '',
        };

        const lambdaRole = createLambdaRole(this, config.deploymentName, 'McpServerDynamicApi', mcpServersTable.tableArn, config.roles?.LambdaExecutionRole);
        const lambdaPath = config.lambdaPath || LAMBDA_PATH;

        // Create the API Lambda function to trigger the MCP server create state machine
        // Note: registerAPIEndpoint will use getOrCreateResource which will find the existing /mcp resource
        const lambdaFunction = registerAPIEndpoint(
            this,
            restApi,
            lambdaPath,
            lambdaLayers,
            {
                name: 'create_hosted_mcp_server',
                resource: 'mcp_server',
                description: 'Create LISA MCP hosted server',
                path: 'mcp',
                method: 'POST',
                environment: env
            },
            getDefaultRuntime(),
            vpc,
            securityGroups,
            authorizer,
            lambdaRole,
        );

        // Register GET endpoint for listing hosted MCP servers
        registerAPIEndpoint(
            this,
            restApi,
            lambdaPath,
            lambdaLayers,
            {
                name: 'list_hosted_mcp_servers',
                resource: 'mcp_server',
                description: 'List LISA MCP hosted servers',
                path: 'mcp',
                method: 'GET',
                environment: env
            },
            getDefaultRuntime(),
            vpc,
            securityGroups,
            authorizer,
            lambdaRole,
        );

        // Register GET endpoint for getting a specific hosted MCP server by ID
        registerAPIEndpoint(
            this,
            restApi,
            lambdaPath,
            lambdaLayers,
            {
                name: 'get_hosted_mcp_server',
                resource: 'mcp_server',
                description: 'Get LISA MCP hosted server by ID',
                path: 'mcp/{serverId}',
                method: 'GET',
                environment: env
            },
            getDefaultRuntime(),
            vpc,
            securityGroups,
            authorizer,
            lambdaRole,
        );

        // Register DELETE endpoint for deleting a hosted MCP server by ID
        registerAPIEndpoint(
            this,
            restApi,
            lambdaPath,
            lambdaLayers,
            {
                name: 'delete_hosted_mcp_server',
                resource: 'mcp_server',
                description: 'Delete LISA MCP hosted server by ID',
                path: 'mcp/{serverId}',
                method: 'DELETE',
                environment: env
            },
            getDefaultRuntime(),
            vpc,
            securityGroups,
            authorizer,
            lambdaRole,
        );

        // Register PUT endpoint for updating a hosted MCP server by ID
        registerAPIEndpoint(
            this,
            restApi,
            lambdaPath,
            lambdaLayers,
            {
                name: 'update_hosted_mcp_server',
                resource: 'mcp_server',
                description: 'Update LISA MCP hosted server by ID',
                path: 'mcp/{serverId}',
                method: 'PUT',
                environment: env
            },
            getDefaultRuntime(),
            vpc,
            securityGroups,
            authorizer,
            lambdaRole,
        );

        lisaServeEndpointUrlPs.grantRead(lambdaFunction.role!);

        // Grant permissions for state machine invocation
        const workflowPermissions = new Policy(this, 'McpServerApiStateMachinePerms', {
            statements: [
                new PolicyStatement({
                    effect: Effect.ALLOW,
                    actions: [
                        'states:StartExecution',
                    ],
                    resources: [
                        createMcpServerStateMachine.stateMachineArn,
                        deleteMcpServerStateMachine.stateMachineArn,
                        updateMcpServerStateMachine.stateMachineArn,
                    ],
                }),
                new PolicyStatement({
                    effect: Effect.ALLOW,
                    actions: [
                        'dynamodb:GetItem',
                        'dynamodb:Scan',
                        'dynamodb:PutItem',
                        'dynamodb:UpdateItem',
                        'dynamodb:DeleteItem',
                    ],
                    resources: [
                        mcpServersTable.tableArn,
                        `${mcpServersTable.tableArn}/*`
                    ],
                }),
            ]
        });
        lambdaFunction.role!.attachInlinePolicy(workflowPermissions);
    }

    /**
     * Creates a role for the state machine lambdas
     * @param mcpServerTableArn - Arn of the MCP server table
     * @param mcpServerDeployerFnArn - Arn of the MCP server deployer lambda
     * @param lisaServeEndpointUrlParamArn - Arn of the lisa serve endpoint url parameter
     * @param managementKeyName - Name of the management key secret
     * @param config - Config object
     * @returns The created role
     */
    createStateMachineLambdaRole (mcpServerTableArn: string, mcpServerDeployerFnArn: string, lisaServeEndpointUrlParamArn: string, managementKeyName: string, config: any): IRole {
        const statements: PolicyStatement[] = [
            new PolicyStatement({
                effect: Effect.ALLOW,
                actions: [
                    'dynamodb:DeleteItem',
                    'dynamodb:GetItem',
                    'dynamodb:PutItem',
                    'dynamodb:UpdateItem',
                    'dynamodb:Scan',
                ],
                resources: [
                    mcpServerTableArn,
                    `${mcpServerTableArn}/*`,
                ]
            }),
            new PolicyStatement({
                effect: Effect.ALLOW,
                actions: [
                    'cloudformation:CreateStack',
                    'cloudformation:DeleteStack',
                    'cloudformation:DescribeStacks',
                    'cloudformation:DescribeStackResources',
                ],
                resources: [
                    // Limit CloudFormation permissions to MCP server stacks that this deployment creates.
                    `arn:${config.partition}:cloudformation:${config.region}:${config.accountNumber}:stack/${config.appName}-${config.deploymentName}-${config.deploymentStage}-mcp-server-*`,
                ],
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
            // Allow passing task/execution roles to ECS when registering task definitions
            new PolicyStatement({
                effect: Effect.ALLOW,
                actions: ['iam:PassRole'],
                resources: ['*'],
                conditions: {
                    StringEquals: {
                        'iam:PassedToService': 'ecs-tasks.amazonaws.com'
                    }
                }
            }),
            new PolicyStatement({
                effect: Effect.ALLOW,
                actions: [
                    'application-autoscaling:RegisterScalableTarget',
                    'application-autoscaling:DescribeScalableTargets',
                    'application-autoscaling:DeregisterScalableTarget',
                ],
                resources: ['*'],  // Application Auto Scaling resources are dynamic
            }),
            new PolicyStatement({
                effect: Effect.ALLOW,
                actions: [
                    'lambda:InvokeFunction'
                ],
                resources: [
                    mcpServerDeployerFnArn
                ]
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
                    'ssm:GetParameter',
                ],
                resources: [
                    lisaServeEndpointUrlParamArn,
                    `arn:${config.partition}:ssm:${config.region}:${config.accountNumber}:parameter${config.deploymentPrefix}/lisaServeRestApiUri`,
                    `arn:${config.partition}:ssm:${config.region}:${config.accountNumber}:parameter/LISA-lisa-management-key`,
                ],
            }),
        ];

        // Add permissions for MCP Connections table if chat is deployed
        // This table is created in the chat stack and stores user-facing MCP connections
        if (config.deployChat) {
            // Reference the table by ARN pattern (table will be created in chat stack)
            // CDK generates table names, so we use a pattern that matches the naming convention
            // Format: {StackName}-{ConstructId}{Hash} or {StackName}-{ConstructId}-{Hash}
            // Stack name format: {deploymentName}-{appName}-chat-{deploymentStage}
            // Construct ID: McpServersTable
            const stackNamePattern = `${config.deploymentName}-${config.appName}-chat-${config.deploymentStage}`;
            const mcpConnectionsTableArnPattern = `arn:${config.partition}:dynamodb:${config.region}:${config.accountNumber}:table/${stackNamePattern}-*McpServersTable*`;
            statements.push(
                new PolicyStatement({
                    effect: Effect.ALLOW,
                    actions: [
                        'dynamodb:PutItem',
                        'dynamodb:UpdateItem',
                        'dynamodb:GetItem',
                        'dynamodb:DeleteItem',
                        'dynamodb:Scan',
                    ],
                    resources: [
                        mcpConnectionsTableArnPattern,
                    ],
                }),
                new PolicyStatement({
                    effect: Effect.ALLOW,
                    actions: [
                        'ssm:GetParameter',
                    ],
                    resources: [
                        `arn:${config.partition}:ssm:${config.region}:${config.accountNumber}:parameter${config.deploymentPrefix}/table/mcpServersTable`,
                        `arn:${config.partition}:ssm:${config.region}:${config.accountNumber}:parameter${config.deploymentPrefix}/LisaApiUrl`,
                    ],
                })
            );
        }

        return new Role(this, 'McpServerSfnLambdaRole', {
            assumedBy: new ServicePrincipal('lambda.amazonaws.com'),
            managedPolicies: [
                ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaVPCAccessExecutionRole'),
            ],
            inlinePolicies: {
                lambdaPermissions: new PolicyDocument({
                    statements: statements,
                }),
            }
        });
    }
}

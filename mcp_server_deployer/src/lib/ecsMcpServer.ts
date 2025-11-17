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

import { Duration, RemovalPolicy } from 'aws-cdk-lib';
import { ISecurityGroup, IVpc, SubnetSelection } from 'aws-cdk-lib/aws-ec2';
import {
    ContainerImage,
    Protocol,
} from 'aws-cdk-lib/aws-ecs';
import { Role } from 'aws-cdk-lib/aws-iam';
import { Bucket } from 'aws-cdk-lib/aws-s3';
import {
    AuthorizationType,
    ConnectionType,
    Cors,
    Deployment,
    HttpIntegration,
    IAuthorizer,
    MockIntegration,
    Resource,
    RestApi,
    VpcLink,
} from 'aws-cdk-lib/aws-apigateway';
import { NetworkLoadBalancer, Protocol as ELBProtocol, ApplicationListener } from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import { AlbListenerTarget } from 'aws-cdk-lib/aws-elasticloadbalancingv2-targets';
import { Construct } from 'constructs';

import { PartialConfig } from '../../../lib/schema';
import { ECSFargateCluster } from './ecsFargateCluster';
import { getMcpServerIdentifier, McpServerConfig } from './utils';
import { createCdkId } from '../../../lib/core/utils';

/**
 * Properties for the EcsMcpServer Construct.
 *
 * @property {IVpc} vpc - The virtual private cloud (VPC).
 * @property {ISecurityGroup} securityGroup - The security group to use for the ECS cluster
 * @property {McpServerConfig} mcpServerConfig - The MCP server configuration.
 */
type EcsMcpServerProps = {
    mcpServerConfig: McpServerConfig;
    securityGroup: ISecurityGroup;
    vpc: IVpc;
    subnetSelection?: SubnetSelection;
    config: PartialConfig;
    restApiId?: string;
    rootResourceId?: string;
    mcpResourceId?: string;
    authorizer?: IAuthorizer;
};

/**
 * Create an ECS Fargate MCP server.
 */
export class EcsMcpServer extends Construct {
    /** MCP server endpoint URL of application load balancer. */
    public readonly endpointUrl: string;

    /**
     * @param {Construct} scope - The parent or owner of the construct.
     * @param {string} id - The unique identifier for the construct within its scope.
     * @param {EcsMcpServerProps} props - The properties of the construct.
     */
    constructor (scope: Construct, id: string, props: EcsMcpServerProps) {
        super(scope, id);
        const { config, mcpServerConfig, securityGroup, vpc, subnetSelection, restApiId, rootResourceId, mcpResourceId } = props;

        const identifier = getMcpServerIdentifier(mcpServerConfig);

        // Resolve IAM roles
        const taskExecutionRole = mcpServerConfig.taskExecutionRoleArn
            ? Role.fromRoleArn(this, 'ExecutionRole', mcpServerConfig.taskExecutionRoleArn)
            : undefined;

        const taskRole = mcpServerConfig.taskRoleArn
            ? Role.fromRoleArn(this, 'TaskRole', mcpServerConfig.taskRoleArn)
            : undefined;

        // Create container image
        const containerImage = this.getContainerImage( mcpServerConfig);

        // Grant S3 read access if s3Path is provided
        // Hosting bucket ARN should be passed via environment variable
        const hostingBucketArn = process.env['LISA_HOSTING_BUCKET_ARN'];
        if (mcpServerConfig.s3Path && hostingBucketArn) {
            const hostingBucket = Bucket.fromBucketArn(this, 'HostingBucket', hostingBucketArn);
            if (taskRole) {
                hostingBucket.grantRead(taskRole);
            }
        }

        // Create container definition configuration
        const containerDefinitionConfig = this.createContainerDefinition(
            containerImage,
            mcpServerConfig,
        );

        const modelCluster = new ECSFargateCluster(scope, `${id}-FargateCluster`, {
            identifier: identifier,
            config,
            mcpServerConfig,
            securityGroup,
            vpc,
            subnetSelection,
            taskExecutionRole,
            taskRole,
            containerDefinitionConfig,
        });

        // Create API Gateway route if API Gateway details are provided
        if (restApiId && rootResourceId && mcpResourceId) {
            this.createApiGatewayRoute(
                scope,
                identifier,
                restApiId,
                rootResourceId,
                mcpResourceId,
                vpc,
                modelCluster.albListener,
                mcpServerConfig,
                config,
            );
        }

        this.endpointUrl = modelCluster.endpointUrl;
    }

    /**
     * Creates API Gateway route to ALB endpoint via NLB
     */
    private createApiGatewayRoute (
        scope: Construct,
        identifier: string,
        restApiId: string,
        rootResourceId: string,
        mcpResourceId: string,
        vpc: IVpc,
        albListener: ApplicationListener,
        mcpServerConfig: McpServerConfig,
        config: PartialConfig,
    ): void {
        // Get authorizer ID from environment variable
        const authorizerId = process.env['LISA_AUTHORIZER_ID'];
        // Get reference to existing API Gateway
        const restApi = RestApi.fromRestApiAttributes(scope, `${identifier}-RestApi`, {
            restApiId: restApiId,
            rootResourceId: rootResourceId,
        });

        // Determine container port
        // For STDIO servers, mcp-proxy exposes HTTP on port 8080
        // For HTTP/SSE servers, use the configured port or default 8000
        const containerPort = mcpServerConfig.serverType === 'stdio' ? 8080 : (mcpServerConfig.port || 8000);

        // For REST API v1, VPC Link requires a Network Load Balancer (NLB)
        // Create an NLB that targets the ALB listener (not Fargate tasks directly)
        // This follows the recommended pattern: API Gateway -> NLB -> ALB -> Fargate
        // The ALB provides better HTTP features (health checks, routing, etc.)
        // The NLB just bridges API Gateway to the ALB
        const nlb = new NetworkLoadBalancer(scope, `${identifier}-NLB`, {
            vpc: vpc,
            internetFacing: false,
            loadBalancerName: createCdkId([identifier, 'NLB'], 32, 2).toLowerCase(),
            vpcSubnets: {
                subnets: vpc.publicSubnets.length > 0 ? vpc.publicSubnets : vpc.privateSubnets,
            },
        });

        // Add listener to NLB that forwards to ALB
        const nlbListener = nlb.addListener(`${identifier}-NLBListener`, {
            port: 80,
            protocol: ELBProtocol.TCP,
        });

        // Target the ALB listener (not Fargate tasks directly)
        // This leverages the ALB's HTTP features while satisfying API Gateway VPC Link's NLB requirement
        // Use configured health check or defaults
        const nlbHealthCheck = mcpServerConfig.loadBalancerConfig?.healthCheckConfig
            ? {
                path: mcpServerConfig.loadBalancerConfig.healthCheckConfig.path,
                port: containerPort.toString(),
                protocol: ELBProtocol.HTTP,
                healthyThresholdCount: mcpServerConfig.loadBalancerConfig.healthCheckConfig.healthyThresholdCount,
                unhealthyThresholdCount: mcpServerConfig.loadBalancerConfig.healthCheckConfig.unhealthyThresholdCount,
                timeout: Duration.seconds(mcpServerConfig.loadBalancerConfig.healthCheckConfig.timeout),
                interval: Duration.seconds(mcpServerConfig.loadBalancerConfig.healthCheckConfig.interval),
            }
            : {
                path: '/status',
                port: containerPort.toString(),
                protocol: ELBProtocol.HTTP,
                healthyThresholdCount: 2,
                unhealthyThresholdCount: 3,
                timeout: Duration.seconds(10),
                interval: Duration.seconds(30),
            };

        nlbListener.addTargets(`${identifier}-NLBTargets`, {
            targets: [new AlbListenerTarget(albListener)],
            port: containerPort,
            healthCheck: nlbHealthCheck,
        });

        // Create VPC Link using the NLB
        const vpcLink = new VpcLink(scope, `${identifier}-VpcLink`, {
            vpcLinkName: createCdkId([identifier, 'VpcLink']),
            description: `VPC Link for MCP server ${identifier}`,
            targets: [nlb],
        });

        // Retain VPC Link on stack deletion to avoid deletion failures when stages
        // still reference deployments that include integrations using this VPC Link
        vpcLink.applyRemovalPolicy(RemovalPolicy.RETAIN);
        nlb.applyRemovalPolicy(RemovalPolicy.RETAIN);

        // Create resource path: /mcp/{serverId}/*
        // Use Resource.fromResourceAttributes() to reference the existing /mcp resource
        // The resource ID is passed as a parameter
        if (!mcpResourceId) {
            throw new Error('mcpResourceId is required. Please ensure the /mcp resource is created first.');
        }
        const mcpResource = Resource.fromResourceAttributes(scope, `${identifier}-McpResource`, {
            restApi: restApi,
            resourceId: mcpResourceId,
            path: '/mcp',
        });

        // Track all methods created to ensure deployment depends on them
        const createdMethods: any[] = [];

        const allowedCorsHeaders = Array.from(new Set([
            ...Cors.DEFAULT_HEADERS,
            'Accept',
            'Mcp-Session-Id',
            'Last-Event-Id',
            'mcp-protocol-version',
            'X-Amz-User-Agent',
        ]));

        // Create or get server-specific resource
        let serverResource = mcpResource.getResource(identifier);
        if (!serverResource) {
            serverResource = mcpResource.addResource(identifier);
            // Add CORS preflight support (creates OPTIONS method automatically)
            serverResource.addCorsPreflight({
                allowOrigins: Cors.ALL_ORIGINS,
                allowHeaders: allowedCorsHeaders,
            });
        }

        // Define methods list for reuse (exclude OPTIONS since CORS preflight handles it)
        const methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH'];

        const corsIntegrationResponses = [
            {
                statusCode: '200',
                responseParameters: {
                    'method.response.header.Access-Control-Allow-Origin': '\'*\'',
                    'method.response.header.Access-Control-Allow-Credentials': '\'false\'',
                },
            },
        ];

        const corsMethodResponse = {
            statusCode: '200',
            responseParameters: {
                'method.response.header.Access-Control-Allow-Origin': true,
                'method.response.header.Access-Control-Allow-Credentials': true,
            },
        };

        const cors405MethodResponse = {
            statusCode: '405',
            responseParameters: {
                'method.response.header.Access-Control-Allow-Origin': true,
                'method.response.header.Access-Control-Allow-Credentials': true,
            },
        };

        // Create or get proxy resource FIRST (before /health) to ensure proper routing
        // The proxy resource will catch all paths except exact matches like /health
        let proxyResource = serverResource.getResource('{proxy+}');
        if (!proxyResource) {
            proxyResource = serverResource.addResource('{proxy+}');
            // Add CORS preflight support (creates OPTIONS method automatically)
            proxyResource.addCorsPreflight({
                allowOrigins: Cors.ALL_ORIGINS,
                allowHeaders: allowedCorsHeaders,
            });
        }

        // Create HTTP integration for API Gateway - let proxy pass full path
        const nlbDnsName = nlb.loadBalancerDnsName;
        const mcpServerIntegration = new HttpIntegration(
            `http://${nlbDnsName}/{proxy}`,
            {
                httpMethod: 'ANY',
                proxy: true,
                options: {
                    vpcLink: vpcLink,
                    connectionType: ConnectionType.VPC_LINK,
                    requestParameters: {
                        'integration.request.path.proxy': 'method.request.path.proxy',
                        'integration.request.header.Accept': 'method.request.header.Accept',
                        'integration.request.header.X-Forwarded-Host': 'context.domainName',
                        'integration.request.header.X-Forwarded-Proto': '\'https\'',
                        'integration.request.header.X-Forwarded-Path': 'method.request.path.proxy',
                    },
                    integrationResponses: corsIntegrationResponses,
                },
            },
        );

        // Add methods with request parameters
        // Use addProxy for cleaner routing or add individual methods
        // Note: OPTIONS is handled by CORS preflight, so we skip it here
        methods.forEach((method) => {
            const methodOptions: any = {
                requestParameters: {
                    'method.request.path.proxy': true,
                    'method.request.header.Accept': true,
                },
                methodResponses: [corsMethodResponse],
            };

            // Apply authorizer if provided
            if (authorizerId) {
                methodOptions.authorizationType = AuthorizationType.CUSTOM;
            }

            const methodObj = proxyResource.addMethod(method, mcpServerIntegration, methodOptions);
            createdMethods.push(methodObj);

            // Set authorizer ID directly on the CfnMethod if authorizer ID is provided
            if (authorizerId) {
                const cfnMethod = methodObj.node.defaultChild as any;
                if (cfnMethod) {
                    cfnMethod.authorizationType = 'CUSTOM';
                    cfnMethod.authorizerId = authorizerId;
                }
            }
        });

        // Also add method to server resource root (no proxy) - use same integration but without proxy path
        const rootIntegration = new HttpIntegration(
            `http://${nlbDnsName}`,
            {
                httpMethod: 'ANY',
                proxy: true,
                options: {
                    vpcLink: vpcLink,
                    connectionType: ConnectionType.VPC_LINK,
                    requestParameters: {
                        'integration.request.header.Accept': 'method.request.header.Accept',
                        'integration.request.header.X-Forwarded-Host': 'context.domainName',
                        'integration.request.header.X-Forwarded-Proto': '\'https\'',
                        // Note: Authorization header is NOT included, which prevents it from being forwarded
                    },
                    integrationResponses: corsIntegrationResponses,
                },
            },
        );

        methods.forEach((method) => {
            // Base method options
            const methodOptions: any = {
                requestParameters: {
                    'method.request.header.Accept': true,
                },
                methodResponses: [corsMethodResponse],
            };

            // Apply authorizer if provided
            // Note: OPTIONS is handled by CORS preflight, so we skip it here
            if (authorizerId) {
                methodOptions.authorizationType = AuthorizationType.CUSTOM;
            }

            const methodObj = serverResource.addMethod(method, rootIntegration, methodOptions);
            createdMethods.push(methodObj);

            // Set authorizer ID directly on the CfnMethod if authorizer ID is provided
            if (authorizerId) {
                const cfnMethod = methodObj.node.defaultChild as any;
                if (cfnMethod) {
                    cfnMethod.authorizationType = 'CUSTOM';
                    cfnMethod.authorizerId = authorizerId;
                }
            }
        });

        // Add explicit child resource "/mcp" under the server path and enforce 405s for MCP Client integration
        let mcpChildResource = serverResource.getResource('mcp');
        if (!mcpChildResource) {
            mcpChildResource = serverResource.addResource('mcp');
            // Add CORS preflight support (creates OPTIONS method automatically)
            mcpChildResource.addCorsPreflight({
                allowOrigins: Cors.ALL_ORIGINS,
                allowHeaders: allowedCorsHeaders,
            });
        }

        const methodsAtChild = ['GET', 'POST'];

        // Create explicit integration for "/mcp" child that targets backend "/mcp"
        const mcpChildIntegration = new HttpIntegration(
            `http://${nlbDnsName}/mcp`,
            {
                httpMethod: 'ANY',
                proxy: true,
                options: {
                    vpcLink: vpcLink,
                    connectionType: ConnectionType.VPC_LINK,
                    requestParameters: {
                        'integration.request.header.Accept': 'method.request.header.Accept',
                        'integration.request.header.X-Forwarded-Host': 'context.domainName',
                        'integration.request.header.X-Forwarded-Proto': '\'https\'',
                    },
                    integrationResponses: corsIntegrationResponses,
                },
            },
        );
        methodsAtChild.forEach((method) => {
            const methodOptions: any = {
                requestParameters: {
                    'method.request.header.Accept': true,
                },
                methodResponses: [corsMethodResponse],
            };

            if (authorizerId) {
                methodOptions.authorizationType = AuthorizationType.CUSTOM;
            }

            const mock405 = new MockIntegration({
                requestTemplates: {
                    'application/json': '{"statusCode": 405}',
                },
                integrationResponses: [
                    {
                        statusCode: '405',
                        responseTemplates: {
                            'application/json': '{"message": "Method Not Allowed"}',
                        },
                        responseParameters: {
                            'method.response.header.Access-Control-Allow-Origin': '\'*\'',
                            'method.response.header.Access-Control-Allow-Credentials': '\'false\'',
                        },
                    },
                ],
            });

            // For HTTP/STDIO servers: block GET at /mcp with 405
            // For SSE servers: block POST at /mcp with 405
            const useMock405 = (
                (mcpServerConfig.serverType !== 'sse' && method === 'GET') ||
                (mcpServerConfig.serverType === 'sse' && method === 'POST')
            );

            if (useMock405) {
                methodOptions.methodResponses = [cors405MethodResponse];
            }

            const integrationToUse = useMock405 ? mock405 : mcpChildIntegration;
            const methodObj = mcpChildResource.addMethod(method, integrationToUse, methodOptions);
            createdMethods.push(methodObj);

            if (authorizerId) {
                const cfnMethod = methodObj.node.defaultChild as any;
                if (cfnMethod) {
                    cfnMethod.authorizationType = 'CUSTOM';
                    cfnMethod.authorizerId = authorizerId;
                }
            }
        });

        // Create deployment to deploy all API Gateway resources to the stage
        // Workaround so that the APIGW endpoint always updates with the latest changes across all stacks
        // Relevant CDK issues:
        // https://github.com/aws/aws-cdk/issues/12417
        // https://github.com/aws/aws-cdk/issues/13383
        const deployment = new Deployment(scope, `${identifier}-ApiDeployment-${new Date().getTime()}`, {
            api: restApi,
        });

        // Hack to allow deploying to an existing stage
        // https://github.com/aws/aws-cdk/issues/25582
        (deployment as any).resource.stageName = config.deploymentStage;

        // Ensure deployment depends on all methods
        // This ensures the deployment is created after all methods are ready
        createdMethods.forEach((methodObj) => {
            deployment.node.addDependency(methodObj);
        });


    }

    /**
     * Creates container image from configuration.
     */
    private getContainerImage (
        mcpServerConfig: McpServerConfig
    ): ContainerImage {
        // If image is provided without s3Path, it's a pre-built image - use it directly
        if (mcpServerConfig.image && !mcpServerConfig.s3Path) {
            // Check if it's an ECR ARN or registry image
            if (mcpServerConfig.image.includes('.ecr.')) {
                // For simplicity, assume it's in the same account
                // Full ARN would be: arn:aws:ecr:region:account:repository/repo:tag
                return ContainerImage.fromRegistry(mcpServerConfig.image);
            }
            // Docker Hub or other registry
            return ContainerImage.fromRegistry(mcpServerConfig.image);
        }

        // If s3Path is provided, use a base image and configure via command/entryPoint overrides
        // This avoids requiring Docker during CDK synthesis
        // (image may be provided as baseImage if both image and s3Path are present)
        if (mcpServerConfig.s3Path) {
            const hostingBucketArn = process.env['LISA_HOSTING_BUCKET_ARN'];
            if (!hostingBucketArn) {
                throw new Error('LISA_HOSTING_BUCKET_ARN environment variable is required when s3Path is provided');
            }
            // Use the provided image as base, or default to a suitable base image
            const baseImage = mcpServerConfig.image || (mcpServerConfig.serverType === 'stdio'
                ? 'python:3.12-slim-bookworm'
                : 'python:3.12-slim-bookworm');
            return ContainerImage.fromRegistry(baseImage);
        }

        // Default: use a common base image
        // This should be replaced with a proper base image for MCP servers
        return ContainerImage.fromRegistry('node:20-slim');
    }

    /**
     * Creates container definition configuration for the MCP server.
     * Returns the configuration object to be used in FargateCluster.
     */
    private createContainerDefinition (
        image: ContainerImage,
        mcpServerConfig: McpServerConfig,
    ): {
        image: ContainerImage;
        environment: { [key: string]: string };
        portMappings: Array<{ containerPort: number; protocol: Protocol }>;
        command?: string[];
        entryPoint?: string[];
    } {
        // Build environment variables
        const environment: { [key: string]: string } = {
            ...mcpServerConfig.environment,
            MCP_SERVER_TYPE: mcpServerConfig.serverType,
            START_COMMAND: mcpServerConfig.startCommand,
        };

        // Add S3 path if provided (will be used in entrypoint script)
        if (mcpServerConfig.s3Path) {
            environment.S3_PATH = mcpServerConfig.s3Path;
            const hostingBucketArn = process.env['LISA_HOSTING_BUCKET_ARN'];
            if (hostingBucketArn) {
                // Extract bucket name from ARN: arn:aws:s3:::bucket-name
                const bucketName = hostingBucketArn.split(':').pop() || '';
                if (bucketName) {
                    environment.S3_BUCKET = bucketName;
                }
            }
        }

        // Add port if provided
        if (mcpServerConfig.port) {
            environment.PORT = mcpServerConfig.port.toString();
        }

        // Port mappings
        // STDIO servers use mcp-proxy which exposes port 8080
        // HTTP/SSE servers use their specified port or default 8000
        const portMappings = mcpServerConfig.port
            ? [{ containerPort: mcpServerConfig.port, protocol: Protocol.TCP }]
            : mcpServerConfig.serverType === 'stdio'
                ? [{ containerPort: 8080, protocol: Protocol.TCP }] // mcp-proxy port
                : [{ containerPort: 8000, protocol: Protocol.TCP }];

        // For pre-built images with STDIO servers, or S3-based deployments, we need to override the command
        // to handle S3 downloads and wrap with mcp-proxy if needed. The image may have its own ENTRYPOINT, but we override it.
        let command: string[] | undefined;
        let entryPoint: string[] | undefined;

        // Check if this is a pre-built image (image provided without s3Path)
        const isPrebuiltImage = mcpServerConfig.image && !mcpServerConfig.s3Path;
        // Check if this is an S3-based deployment (s3Path provided)
        const isS3Based = !!mcpServerConfig.s3Path;

        // For S3-based deployments, we need to install dependencies and set up the entrypoint
        if (isS3Based) {
            if (mcpServerConfig.serverType === 'stdio') {
                // For STDIO servers with S3, install mcp-proxy and set up entrypoint
                let bashScript = 'set -e; ';

                // Install dependencies if not already present
                bashScript += 'if ! command -v aws >/dev/null 2>&1; then ';
                bashScript += 'apt-get update && apt-get install -y --no-install-recommends awscli && apt-get clean && rm -rf /var/lib/apt/lists/*; ';
                bashScript += 'fi; ';

                // Install mcp-proxy if not present
                bashScript += 'if ! command -v mcp-proxy >/dev/null 2>&1 && [ ! -f /root/.local/bin/mcp-proxy ]; then ';
                bashScript += 'if ! command -v curl >/dev/null 2>&1; then apt-get update && apt-get install -y --no-install-recommends curl && apt-get clean && rm -rf /var/lib/apt/lists/*; fi; ';
                bashScript += 'if ! command -v nodejs >/dev/null 2>&1; then apt-get update && apt-get install -y --no-install-recommends nodejs npm && apt-get clean && rm -rf /var/lib/apt/lists/*; fi; ';
                bashScript += 'curl -LsSf https://astral.sh/uv/install.sh | sh || true; ';
                bashScript += 'export PATH="/root/.local/bin:$PATH"; ';
                bashScript += '/root/.local/bin/uv tool install mcp-proxy || true; ';
                bashScript += 'fi; ';

                // Create working directory
                bashScript += 'mkdir -p /app/server; ';

                // Download from S3
                bashScript += 'if [ -n "$S3_BUCKET" ] && [ -n "$S3_PATH" ]; then ';
                bashScript += 'echo "Downloading server files from s3://$S3_BUCKET/$S3_PATH..."; ';
                bashScript += 'aws s3 sync "s3://$S3_BUCKET/$S3_PATH" /app/server/; ';
                bashScript += 'chmod +x /app/server/* 2>/dev/null || true; ';
                bashScript += 'fi; ';

                // Change to server directory if files were downloaded
                bashScript += 'if [ -d /app/server ] && [ "$(ls -A /app/server)" ]; then cd /app/server; fi; ';

                // Execute with mcp-proxy
                bashScript += `START_CMD='${mcpServerConfig.startCommand.replace(/'/g, '\'\\\'\'')}'; `;
                bashScript += 'export PATH="/root/.local/bin:$PATH"; ';
                bashScript += 'if [ -f /root/.local/bin/mcp-proxy ]; then ';
                bashScript += 'eval exec /root/.local/bin/mcp-proxy --stateless --transport streamablehttp --port=8080 --host=0.0.0.0 --allow-origin="*" "$START_CMD"; ';
                bashScript += 'elif [ -f /root/.cargo/bin/mcp-proxy ]; then ';
                bashScript += 'eval exec /root/.cargo/bin/mcp-proxy --stateless --transport streamablehttp --port=8080 --host=0.0.0.0 --allow-origin="*" "$START_CMD"; ';
                bashScript += 'elif command -v mcp-proxy >/dev/null 2>&1; then ';
                bashScript += 'eval exec mcp-proxy --stateless --transport streamablehttp --port=8080 --host=0.0.0.0 --allow-origin="*" "$START_CMD"; ';
                bashScript += 'else ';
                bashScript += 'echo "ERROR: mcp-proxy not found. Attempting to install..."; ';
                bashScript += 'curl -LsSf https://astral.sh/uv/install.sh | sh && /root/.local/bin/uv tool install mcp-proxy && eval exec /root/.local/bin/mcp-proxy --stateless --transport streamablehttp --port=8080 --host=0.0.0.0 --allow-origin="*" "$START_CMD"; ';
                bashScript += 'fi';

                entryPoint = ['/bin/bash', '-c'];
                command = [bashScript];
            } else {
                // For HTTP/SSE servers with S3, download files and execute start command
                let bashScript = 'set -e; ';

                // Install AWS CLI if not present
                bashScript += 'if ! command -v aws >/dev/null 2>&1; then ';
                bashScript += 'apt-get update && apt-get install -y --no-install-recommends awscli && apt-get clean && rm -rf /var/lib/apt/lists/*; ';
                bashScript += 'fi; ';

                // Create working directory
                bashScript += 'mkdir -p /app/server; ';

                // Download from S3
                bashScript += 'if [ -n "$S3_BUCKET" ] && [ -n "$S3_PATH" ]; then ';
                bashScript += 'echo "Downloading server files from s3://$S3_BUCKET/$S3_PATH..."; ';
                bashScript += 'aws s3 sync "s3://$S3_BUCKET/$S3_PATH" /app/server/; ';
                bashScript += 'chmod +x /app/server/* 2>/dev/null || true; ';
                bashScript += 'export PATH="/app/server:$PATH"; ';
                bashScript += 'fi; ';

                // Change to server directory if files were downloaded, otherwise stay in /app
                bashScript += 'if [ -d /app/server ] && [ "$(ls -A /app/server)" ]; then cd /app/server; else cd /app; fi; ';

                // Execute the start command
                bashScript += `exec ${mcpServerConfig.startCommand}`;

                entryPoint = ['/bin/bash', '-c'];
                command = [bashScript];
            }
        } else if (isPrebuiltImage && mcpServerConfig.serverType === 'stdio') {
            // For pre-built STDIO images, we need to override with mcp-proxy wrapper
            // Build a bash script that:
            // 1. Downloads from S3 if configured (with environment variable substitution)
            // 2. Wraps the startCommand with mcp-proxy
            // Use a single-line script for ECS command array
            let bashScript = 'set -e; ';

            // Add S3 download logic if s3Path is provided
            if (mcpServerConfig.s3Path) {
                bashScript += 'if [ -n "$S3_BUCKET" ] && [ -n "$S3_PATH" ]; then ';
                bashScript += 'echo "Downloading server files from s3://$S3_BUCKET/$S3_PATH..."; ';
                bashScript += 'aws s3 sync "s3://$S3_BUCKET/$S3_PATH" /app/server/; ';
                bashScript += 'chmod +x /app/server/* 2>/dev/null || true; ';
                bashScript += 'fi; ';
                bashScript += 'if [ -d /app/server ] && [ "$(ls -A /app/server)" ]; then cd /app/server; fi; ';
            }

            // Add mcp-proxy execution with fallback paths
            // mcp-proxy expects the command as a positional argument (after --port and --host), not --command flag
            // The startCommand may contain spaces, so we need to evaluate it properly in the shell context
            // Use eval to properly handle commands with spaces and arguments
            bashScript += `START_CMD='${mcpServerConfig.startCommand.replace(/'/g, '\'\\\'\'')}'; `;
            bashScript += 'if [ -f /root/.local/bin/mcp-proxy ]; then ';
            bashScript += 'eval exec /root/.local/bin/mcp-proxy --stateless --transport streamablehttp --port=8080 --host=0.0.0.0 --allow-origin="*" "$START_CMD"; ';
            bashScript += 'elif [ -f /root/.cargo/bin/mcp-proxy ]; then ';
            bashScript += 'eval exec /root/.cargo/bin/mcp-proxy --stateless --transport streamablehttp --port=8080 --host=0.0.0.0 --allow-origin="*" "$START_CMD"; ';
            bashScript += 'elif command -v mcp-proxy >/dev/null 2>&1; then ';
            bashScript += 'eval exec mcp-proxy --stateless --transport streamablehttp --port=8080 --host=0.0.0.0 --allow-origin="*" "$START_CMD"; ';
            bashScript += 'else ';
            bashScript += 'echo "ERROR: mcp-proxy not found. Please ensure mcp-proxy is installed in your Docker image."; ';
            bashScript += 'exit 1; ';
            bashScript += 'fi';

            // Use bash to execute the script
            entryPoint = ['/bin/bash', '-c'];
            command = [bashScript];
        }

        return {
            image,
            environment,
            portMappings,
            command,
            entryPoint,
        };
    }
}

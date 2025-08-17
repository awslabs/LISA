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

// Deploy application to different stages.
import { AddPermissionBoundary, ConvertInlinePoliciesToManaged } from '@cdklabs/cdk-enterprise-iac';
import {
    Aspects,
    CfnResource,
    CliCredentialsStackSynthesizer,
    DefaultStackSynthesizer,
    IAspect,
    IStackSynthesizer,
    Stack,
    Stage,
    StageProps,
    Tags,
} from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { AwsSolutionsChecks, NagSuppressions, NIST80053R5Checks } from 'cdk-nag';
import { LaunchTemplate } from 'aws-cdk-lib/aws-ec2';
import { Function } from 'aws-cdk-lib/aws-lambda';
import { ContainerDefinition, TaskDefinition } from 'aws-cdk-lib/aws-ecs';

import { LisaChatApplicationStack } from './chat';
import { ARCHITECTURE, CoreStack } from './core';
import { LisaApiBaseStack } from './core/api_base';
import { LisaApiDeploymentStack } from './core/api_deployment';
import { createCdkId } from './core/utils';
import { LisaServeIAMStack } from './iam';
import { LisaModelsApiStack } from './models';
import { LisaNetworkingStack } from './networking';
import { LisaRagStack } from './rag';
import { BaseProps, Config, stackSynthesizerType } from './schema';
import { LisaServeApplicationStack } from './serve';
import { UserInterfaceStack } from './user-interface';
import { LisaDocsStack } from './docs';
import { LisaMetricsStack } from './metrics';

import fs from 'node:fs';
import { VERSION_PATH } from './util';


export const VERSION: string = fs.readFileSync(VERSION_PATH, 'utf8').trim();


type CustomLisaServeApplicationStageProps = {} & BaseProps;
type LisaServeApplicationStageProps = CustomLisaServeApplicationStageProps & StageProps;

/**
 * Modifies all AWS::EC2::LaunchTemplate resources in a CDK application. It directly adjusts the synthesized
 * CloudFormation template, setting the HttpPutResponseHopLimit within MetadataOptions to 2 and HttpTokens to required.
 */
class UpdateLaunchTemplateMetadataOptions implements IAspect {
    /**
   * Checks if the given node is an instance of CfnResource and specifically an AWS::EC2::LaunchTemplate resource.
   * If both conditions are true, it applies a direct override to the CloudFormation resource's properties, setting
   * the HttpPutResponseHopLimit to 2 and HttpTokens to 'required'.
   *
   * @param {Construct} node - The CDK construct being visited.
   */
    public visit (node: Construct): void {
    // Check if the node is a CloudFormation resource of type AWS::EC2::LaunchTemplate
        if (node instanceof CfnResource && node.cfnResourceType === 'AWS::EC2::LaunchTemplate') {
            // Directly modify the CloudFormation properties to include the desired settings
            node.addOverride('Properties.LaunchTemplateData.MetadataOptions.HttpPutResponseHopLimit', 2);
            node.addOverride('Properties.LaunchTemplateData.MetadataOptions.HttpTokens', 'required');
        }
    }
}

class ApplyCertEnvironmentVariables implements IAspect {
    private certificateAuthorityBundle: string;
    constructor (certificateAuthorityBundle: string) {
        this.certificateAuthorityBundle = certificateAuthorityBundle;
    }

    public visit (node: Construct): void {
        const vars = {
            'AWS_CA_BUNDLE': this.certificateAuthorityBundle,
            'REQUESTS_CA_BUNDLE': this.certificateAuthorityBundle,
            'SSL_CERT_DIR': '/etc/pki/tls/certs',
            'SSL_CERT_FILE': this.certificateAuthorityBundle,
        };

        if (node instanceof Function) {
            this.configureLambda(node, vars);
        }
    }

    private configureLambda (lambda: Function, vars: Record<string, string>) {
        Object.entries(vars).forEach(([key, value]) => {
            lambda.addEnvironment(key, value);
        });
    }
}

class ApplyProxyEnvironmentVariables implements IAspect {
    /**
    * This crawls the synth'd cfn template and ensures proxy configs are applied to anything that needs them.
    * @param {webProxy} string - The proxy config sourced from config.yaml
    * @param {noProxy} string - The no porxy config sourced from config.yaml
    * @param {config} Config - Config sourced from config.yaml
    */
    private webProxy: string;
    private noProxy: string;
    private config: Config;

    constructor (webProxy: string, noProxy: string, config: Config) {
        this.webProxy = webProxy;
        this.noProxy = noProxy;
        this.config = config;
    }

    public visit (node: Construct): void {
        const commonNoProxy = '169.254.169.254,169.254.170.2,/var/run/docker.sock';
        const fullNoProxy = `${this.noProxy},${commonNoProxy}`;

        // These are the proxy env vars we set for lambda and task defs for containers
        const proxy = {
            'HTTPS_PROXY': this.webProxy,
            'HTTP_PROXY': this.webProxy,
            'https_proxy': this.webProxy,
            'http_proxy': this.webProxy,
            'NO_PROXY': fullNoProxy,
            'no_proxy': fullNoProxy
        };

        // Check if the node is a lambda/launchtemplate/task def and call the correct method
        if (node instanceof CfnResource && node.cfnResourceType === 'AWS::Lambda::Function') {
            this.configureLambda(node, proxy);
        } else if (node instanceof LaunchTemplate) {
            this.configureLaunchTemplate(node, proxy);
        } else if (node instanceof TaskDefinition) {
            this.configureTaskDefinition(node, proxy);
        }
    }

    private configureLambda (lambda: any, proxy: Record<string, string>) {
        if (!this.config.subnets || !Array.isArray(this.config.subnets)) {
            throw new Error('Configuration error: subnets must be an array of subnet objects');
        }

        // Configure VPC settings
        lambda.addPropertyOverride('VpcConfig', {
            SubnetIds: this.config.subnets.map((subnet) => subnet.subnetId),
            SecurityGroupIds: [this.config.securityGroupConfig?.lambdaSecurityGroupId]
        });

        // Get the role reference and ID
        const roleRef = lambda.cfnProperties?.Role || lambda.cfnProperties?.role;
        if (!roleRef) return;

        const resolvedRole = Stack.of(lambda).resolve(roleRef);
        const roleId = resolvedRole['Fn::GetAtt']?.[0] || resolvedRole['Ref'];
        if (!roleId) return;

        // Find and update the role
        const role = Stack.of(lambda).node.findAll()
            .find((construct) => construct instanceof CfnResource &&
                  construct.cfnResourceType === 'AWS::IAM::Role' &&
                  Stack.of(construct).resolve((construct as any).logicalId) === roleId) as any;

        if (role) {
            // Add VPC execution policy
            const lambdaVpcPolicyArn = {
                'Fn::Join': ['',['arn:',{'Ref':'AWS::Partition'},':iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole']]
            };

            const currentPolicies = Stack.of(role).resolve(role.cfnProperties?.ManagedPolicyArns || role.cfnProperties?.managedPolicyArns);
            if (currentPolicies) {
                // Add the VPC execution policy if not already present
                if (!currentPolicies.some((policy: any) => JSON.stringify(policy) === JSON.stringify(lambdaVpcPolicyArn))) {
                    currentPolicies.push(lambdaVpcPolicyArn);
                    role.addPropertyOverride('ManagedPolicyArns', currentPolicies);
                }
            } else {
                // No managed policies yet, add the VPC execution policy
                role.addPropertyOverride('ManagedPolicyArns', [lambdaVpcPolicyArn]);
            }
        }

        // Add proxy environment variables
        lambda.addPropertyOverride('Environment.Variables', proxy);
    }

    private configureLaunchTemplate (launchTemplate: LaunchTemplate, proxy: Record<string, string>) {
        const userDataCommands = this.generateUserDataCommands(proxy); // Generate commands for launch template
        userDataCommands.forEach((command) => { // Add each command as a new line in the UserData script
            launchTemplate.userData?.addCommands(command);
        });
    }

    private configureTaskDefinition (taskDefinition: TaskDefinition, proxy: Record<string, string>) {
        const containers = taskDefinition.node.findAll().filter((child) => child instanceof ContainerDefinition);
        if (containers.length > 0) { // We want to make sure there's a container
            const container = containers[0] as ContainerDefinition; // Take the 0th indexed container(every task def should only have one)
            Object.entries(proxy).forEach(([key, value]) => {
                container.addEnvironment(key, value); // Add each proxy env var to the container def
            });
        } else {
            console.warn('No containers found in the task definition');
        }
    }

    private generateUserDataCommands (proxy: Record<string, string>): string[] {
        return [
            '#!/bin/bash',
            'set -e',

            // Configure ECS
            'echo \'ECS_ENABLE_TASK_IAM_ROLE=true\' >> /etc/ecs/ecs.config',
            'echo \'ECS_ENABLE_TASK_ENI=true\' >> /etc/ecs/ecs.config',
            'echo \'ECS_AWSVPC_BLOCK_IMDS=true\' >> /etc/ecs/ecs.config',
            ...Object.entries(proxy).map(([key, value]) => `echo "${key}=${value}" >> /etc/ecs/ecs.config`),

            // Configure ECS service
            'mkdir -p /etc/systemd/system/ecs.service.d',
            `cat <<EOF > /etc/systemd/system/ecs.service.d/http-proxy.conf
[Service]
${Object.entries(proxy).map(([key, value]) => `Environment="${key}=${value}"`).join('\n')}
EOF`,

            // Configure Docker
            'mkdir -p /etc/systemd/system/docker.service.d',
            `cat <<EOF > /etc/systemd/system/docker.service.d/http-proxy.conf
[Service]
${Object.entries(proxy).map(([key, value]) => `Environment="${key}=${value}"`).join('\n')}
EOF`,

            // Set system-wide proxy settings
            `cat <<EOF >> /etc/environment
${Object.entries(proxy).map(([key, value]) => `${key}=${value}`).join('\n')}
EOF`,

            // Reload systemd and restart services
            'systemctl daemon-reload',
            'systemctl restart docker',
            'systemctl restart ecs',

            // Export variables for the current session
            ...Object.entries(proxy).map(([key, value]) => `export ${key}=${value}`)
        ];
    }
}

/**
 * Removes all AWS::EC2::SecurityGroup resources in a CDK application. It directly removes the synthesized
 * CloudFormation template, removing the AWS::EC2::SecurityGroup resources.
 */
class RemoveSecurityGroupAspect implements IAspect {
    private readonly sgId?: string;

    /**
     * Constructs the aspect with the given security group ID.
     *
     * @param {string} sgId - The SG ID you'd like to use instead of auto gen'd ones, in this case it's applied to ECS instances
     */
    constructor (sgId?: string) {
        this.sgId = sgId;
    }

    /**
     * Checks if the given node is an instance of CfnResource and specifically an AWS::EC2::SecurityGroup or SecurityGroupIngress resource.
     * If true, we delete these objects because we're importing these resources
     *
     * @param {Construct} node - The CDK construct being visited.
     */
    public visit (node: Construct): void {
        // Check if the node is a CloudFormation resource of type AWS::EC2::SecurityGroup
        if (node instanceof CfnResource && node.cfnResourceType === 'AWS::EC2::SecurityGroup') {
            // Remove SG resource
            const parent = node.node.scope;
            parent?.node.tryRemoveChild(node.node.id);
        }
        if (node instanceof CfnResource && node.cfnResourceType === 'AWS::EC2::SecurityGroupIngress') {
            // Remove SGI resource
            const parent = node.node.scope;
            parent?.node.tryRemoveChild(node.node.id);
        }
        if (this.sgId) {
            if (node instanceof CfnResource && node.cfnResourceType === 'AWS::EC2::LaunchTemplate') {
                // Directly modify the CloudFormation properties to remove get attr pointing to removed sg(s)
                node.addOverride('Properties.LaunchTemplateData.SecurityGroupIds', [this.sgId]);
            }
        }
    }
}

export type CommonStackProps = {
    synthesizer?: IStackSynthesizer;
} & BaseProps;

/**
 * LISA-serve Application Stage.
 */
export class LisaServeApplicationStage extends Stage {
    readonly stacks: Stack[] = [];

    /**
   * @param {Construct} scope - The parent or owner of the construct.
   * @param {string} id - The unique identifier for the construct within its scope.
   * @param {LisaServeApplicationStageProps} props - Properties for the stage.
   */
    constructor (scope: Construct, id: string, props: LisaServeApplicationStageProps) {
        super(scope, id, props);

        const { config } = props;
        const baseStackProps: CommonStackProps = {
            config,
        };

        if (config.stackSynthesizer) {
            switch (config.stackSynthesizer) {
                case stackSynthesizerType.CliCredentialsStackSynthesizer:
                    baseStackProps.synthesizer = new CliCredentialsStackSynthesizer();
                    break;
                case stackSynthesizerType.DefaultStackSynthesizer:
                    baseStackProps.synthesizer = new DefaultStackSynthesizer();
                    break;
                case stackSynthesizerType.LegacyStackSynthesizer:
                    baseStackProps.synthesizer = new DefaultStackSynthesizer();
                    break;
                default:
                    throw Error('Unrecognized config value: "stackSynthesizer"');
            }
        }

        // Stacks
        const iamStack = new LisaServeIAMStack(this, 'LisaServeIAMStack', {
            ...baseStackProps,
            stackName: createCdkId([config.deploymentName, config.appName, 'IAM', config.deploymentStage]),
            description: `LISA-serve: ${config.deploymentName}-${config.deploymentStage} IAM`,
        });
        this.stacks.push(iamStack);

        const networkingStack = new LisaNetworkingStack(this, 'LisaNetworking', {
            ...baseStackProps,
            stackName: createCdkId([config.deploymentName, config.appName, 'networking', config.deploymentStage]),
            description: `LISA-networking: ${config.deploymentName}-${config.deploymentStage}`,
        });
        this.stacks.push(networkingStack);

        const coreStack = new CoreStack(this, 'LisaCore', {
            ...baseStackProps,
            stackName: createCdkId([config.deploymentName, config.appName, 'core', config.deploymentStage]),
            description: `LISA-core: ${config.deploymentName}-${config.deploymentStage}`,
        });
        this.stacks.push(coreStack);

        const serveStack = new LisaServeApplicationStack(this, 'LisaServe', {
            ...baseStackProps,
            description: `LISA-serve: ${config.deploymentName}-${config.deploymentStage}`,
            stackName: createCdkId([config.deploymentName, config.appName, 'serve', config.deploymentStage]),
            vpc: networkingStack.vpc,
            securityGroups: [networkingStack.vpc.securityGroups.lambdaSg],
        });
        this.stacks.push(serveStack);
        serveStack.addDependency(networkingStack);
        serveStack.addDependency(iamStack);

        const apiBaseStack = new LisaApiBaseStack(this, 'LisaApiBase', {
            ...baseStackProps,
            tokenTable: serveStack.tokenTable,
            stackName: createCdkId([config.deploymentName, config.appName, 'API']),
            description: `LISA-API: ${config.deploymentName}-${config.deploymentStage}`,
            vpc: networkingStack.vpc
        });
        apiBaseStack.addDependency(coreStack);
        apiBaseStack.addDependency(serveStack);
        this.stacks.push(apiBaseStack);

        const apiDeploymentStack = new LisaApiDeploymentStack(this, 'LisaApiDeployment', {
            ...baseStackProps,
            description: `LISA-api-deployment: ${config.deploymentName}-${config.deploymentStage}`,
            stackName: createCdkId([config.deploymentName, config.appName, 'api-deployment', config.deploymentStage]),
            restApiId: apiBaseStack.restApiId,
        });
        apiDeploymentStack.addDependency(apiBaseStack);

        const modelsApiDeploymentStack = new LisaModelsApiStack(this, 'LisaModelsApiDeployment', {
            ...baseStackProps,
            authorizer: apiBaseStack.authorizer,
            description: `LISA-models: ${config.deploymentName}-${config.deploymentStage}`,
            lisaServeEndpointUrlPs: config.restApiConfig.internetFacing ? serveStack.endpointUrl : undefined,
            restApiId: apiBaseStack.restApiId,
            rootResourceId: apiBaseStack.rootResourceId,
            stackName: createCdkId([config.deploymentName, config.appName, 'models', config.deploymentStage]),
            securityGroups: [networkingStack.vpc.securityGroups.ecsModelAlbSg],
            vpc: networkingStack.vpc,
        });
        modelsApiDeploymentStack.addDependency(serveStack);
        apiDeploymentStack.addDependency(modelsApiDeploymentStack);
        this.stacks.push(modelsApiDeploymentStack);

        if (config.deployRag) {
            const ragStack = new LisaRagStack(this, 'LisaRAG', {
                ...baseStackProps,
                authorizer: apiBaseStack.authorizer!,
                description: `LISA-rag: ${config.deploymentName}-${config.deploymentStage}`,
                restApiId: apiBaseStack.restApiId,
                rootResourceId: apiBaseStack.rootResourceId,
                endpointUrl: config.restApiConfig.internetFacing ? serveStack.endpointUrl : undefined,
                modelsPs: config.restApiConfig.internetFacing ? serveStack.modelsPs : undefined,
                stackName: createCdkId([config.deploymentName, config.appName, 'rag', config.deploymentStage]),
                securityGroups: [networkingStack.vpc.securityGroups.lambdaSg],
                vpc: networkingStack.vpc,
            });
            ragStack.addDependency(coreStack);
            ragStack.addDependency(iamStack);
            ragStack.addDependency(apiBaseStack);
            this.stacks.push(ragStack);
            apiDeploymentStack.addDependency(ragStack);
        }

        // Declare metricsStack here so that we can reference it in chatStack
        let metricsStack: LisaMetricsStack | undefined;
        if (config.deployMetrics) {
            metricsStack = new LisaMetricsStack(this, 'LisaMetrics', {
                ...baseStackProps,
                authorizer: apiBaseStack.authorizer!,
                stackName: createCdkId([config.deploymentName, config.appName, 'metrics', config.deploymentStage]),
                description: `LISA-metrics: ${config.deploymentName}-${config.deploymentStage}`,
                restApiId: apiBaseStack.restApiId,
                rootResourceId: apiBaseStack.rootResourceId,
                securityGroups: [networkingStack.vpc.securityGroups.lambdaSg],
                vpc: networkingStack.vpc,
            });
            metricsStack.addDependency(apiBaseStack);
            metricsStack.addDependency(coreStack);
            apiDeploymentStack.addDependency(metricsStack);
            this.stacks.push(metricsStack);
        }

        if (config.deployChat) {
            const chatStack = new LisaChatApplicationStack(this, 'LisaChat', {
                ...baseStackProps,
                authorizer: apiBaseStack.authorizer!,
                stackName: createCdkId([config.deploymentName, config.appName, 'chat', config.deploymentStage]),
                description: `LISA-chat: ${config.deploymentName}-${config.deploymentStage}`,
                restApiId: apiBaseStack.restApiId,
                rootResourceId: apiBaseStack.rootResourceId,
                securityGroups: [networkingStack.vpc.securityGroups.lambdaSg],
                vpc: networkingStack.vpc,
            });
            chatStack.addDependency(apiBaseStack);
            chatStack.addDependency(coreStack);
            if (metricsStack) {
                chatStack.addDependency(metricsStack);
            }
            apiDeploymentStack.addDependency(chatStack);
            this.stacks.push(chatStack);

            if (config.deployUi) {
                const uiStack = new UserInterfaceStack(this, 'LisaUserInterface', {
                    ...baseStackProps,
                    architecture: ARCHITECTURE,
                    stackName: createCdkId([config.deploymentName, config.appName, 'ui', config.deploymentStage]),
                    description: `LISA-user-interface: ${config.deploymentName}-${config.deploymentStage}`,
                    restApiId: apiBaseStack.restApiId,
                    rootResourceId: apiBaseStack.rootResourceId,
                });
                uiStack.addDependency(chatStack);
                uiStack.addDependency(serveStack);
                uiStack.addDependency(apiBaseStack);
                apiDeploymentStack.addDependency(uiStack);
                this.stacks.push(uiStack);
            }
        }

        if (config.deployDocs) {
            const docsStack = new LisaDocsStack(this, 'LisaDocs', {
                ...baseStackProps
            });
            this.stacks.push(docsStack);
        }

        this.stacks.push(apiDeploymentStack);

        // Set resource tags
        if (!config.region.includes('iso')) {
            for (const tag of config.tags ?? []) {
                Tags.of(this).add(tag['Key'], tag['Value']);
            }
            Tags.of(this).add('VERSION', VERSION);
        }

        // Apply permissions boundary aspect to all stacks if the boundary is defined in
        // config.yaml
        if (config.permissionsBoundaryAspect) {
            this.stacks.forEach((lisaStack) => {
                Aspects.of(lisaStack).add(new AddPermissionBoundary({
                    permissionsBoundaryPolicyName: config.permissionsBoundaryAspect!.permissionsBoundaryPolicyName,
                    rolePrefix: `${config.permissionsBoundaryAspect!.rolePrefix}-${config.deploymentName}`,
                    policyPrefix: `${config.permissionsBoundaryAspect!.policyPrefix}-${config.deploymentName}`,
                    instanceProfilePrefix: `${config.permissionsBoundaryAspect!.instanceProfilePrefix}-${config.deploymentName}`
                }));
            });
        }

        if (config.convertInlinePoliciesToManaged) {
            this.stacks.forEach((lisaStack) => {
                Aspects.of(lisaStack).add(new ConvertInlinePoliciesToManaged());
            });
        }
        // Nag Suppressions
        this.stacks.forEach((lisaStack) => {
            NagSuppressions.addStackSuppressions(
                lisaStack,
                [
                    {
                        id: 'NIST.800.53.R5-LambdaConcurrency',
                        reason: 'Not applying lambda concurrency limits',
                    },
                    {
                        id: 'NIST.800.53.R5-LambdaDLQ',
                        reason: 'Not creating lambda DLQs',
                    },
                ],
            );
        });

        // Run CDK-nag on app if specified
        if (config.runCdkNag) {
            this.stacks.forEach((lisaStack) => {
                Aspects.of(lisaStack).add(new AwsSolutionsChecks({ reports: true, verbose: true }));
                Aspects.of(lisaStack).add(new NIST80053R5Checks({ reports: true, verbose: true }));
            });
        }

        if (config.webProxy) {
            this.stacks.forEach((lisaStack) => {
                Aspects.of(lisaStack).add(new ApplyProxyEnvironmentVariables(config.webProxy!, config.noProxy!, config));
            });
        }

        if (config.securityGroupConfig) {
            this.stacks.forEach((lisaStack) => {
                Aspects.of(lisaStack).add(new RemoveSecurityGroupAspect(config.securityGroupConfig?.modelSecurityGroupId));
            });
        }

        if (config.region.includes('iso')) {
            this.stacks.forEach((lisaStack) => {
                Aspects.of(lisaStack).add(new ApplyCertEnvironmentVariables(config.certificateAuthorityBundle));
            });
        }

        // Enforce updates to EC2 launch templates
        Aspects.of(this).add(new UpdateLaunchTemplateMetadataOptions());
    }
}

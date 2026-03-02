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
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as events from 'aws-cdk-lib/aws-events';
import { Construct } from 'constructs';
import { AwsSolutionsChecks, NagSuppressions, NIST80053R5Checks } from 'cdk-nag';

import { LisaChatApplicationStack } from './chat';
import { ARCHITECTURE, CoreStack } from './core';
import { LisaApiBaseStack } from './core/api_base';
import { LisaApiDeploymentStack } from './core/api_deployment';
import { createCdkId } from './core/utils';
import { LisaServeIAMStack } from './iam';
import { LisaModelsApiStack } from './models';
import { LisaNetworkingStack } from './networking';
import { LisaRagStack } from './rag';
import { BaseProps, stackSynthesizerType } from './schema';
import { LisaServeApplicationStack } from './serve';
import { McpWorkbenchStack } from './serve/mcpWorkbenchStack';
import { UserInterfaceStack } from './user-interface';
import { LisaDocsStack } from './docs';
import { LisaMetricsStack } from './metrics';
import { LisaMcpApiStack } from './mcp';
import { LisaApiTokensStack } from './api-tokens';

import fs from 'node:fs';
import { VERSION_PATH } from './util';
import { AdcLambdaCABundleAspect } from './util/adcCertBundleAspect';


export const VERSION: string = fs.readFileSync(VERSION_PATH, 'utf8').trim();

/**
 * Creates a DefaultStackSynthesizer with custom bootstrap qualifier and role ARNs.
 *
 * @param {BaseProps['config']} config - The configuration object containing AWS account details
 * @param {string} rolePrefix - Optional prefix for role names
 * @returns {DefaultStackSynthesizer} Configured stack synthesizer instance
 */
function createDefaultStackSynthesizer (config: BaseProps['config']): DefaultStackSynthesizer {
    if (!config.bootstrapQualifier) {
        return new DefaultStackSynthesizer();
    }

    const rolePrefix = config.bootstrapRolePrefix ?? '';

    return new DefaultStackSynthesizer({
        qualifier: config.bootstrapQualifier,
        cloudFormationExecutionRole: `arn:${config.partition}:iam::${config.accountNumber}:role/${rolePrefix}cdk-${config.bootstrapQualifier}-cfn-exec-${config.accountNumber}-${config.region}`,
        deployRoleArn: `arn:${config.partition}:iam::${config.accountNumber}:role/${rolePrefix}cdk-${config.bootstrapQualifier}-deploy-${config.accountNumber}-${config.region}`,
        fileAssetPublishingRoleArn: `arn:${config.partition}:iam::${config.accountNumber}:role/${rolePrefix}cdk-${config.bootstrapQualifier}-file-pub-${config.accountNumber}-${config.region}`,
        imageAssetPublishingRoleArn: `arn:${config.partition}:iam::${config.accountNumber}:role/${rolePrefix}cdk-${config.bootstrapQualifier}-image-pub-${config.accountNumber}-${config.region}`,
        lookupRoleArn: `arn:${config.partition}:iam::${config.accountNumber}:role/${rolePrefix}cdk-${config.bootstrapQualifier}-lookup-${config.accountNumber}-${config.region}`
    });
}

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

/**
 * Removes Tags property from all AWS::Lambda::EventSourceMapping resources in a CDK application.
 * This is required for AWS GovCloud regions which don't support Tags on EventSourceMapping resources.
 */
class RemoveEventSourceMappingTagsAspect implements IAspect {
    /**
     * Checks if the given node is an instance of CfnResource and specifically an AWS::Lambda::EventSourceMapping resource.
     * If true, it removes the Tags property to prevent deployment failures in AWS GovCloud regions.
     *
     * @param {Construct} node - The CDK construct being visited.
     */
    public visit (node: Construct): void {
        // Check if the node is a CloudFormation resource of type AWS::Lambda::EventSourceMapping
        if (node instanceof lambda.CfnEventSourceMapping) {
            // Remove Tags property for AWS GovCloud compatibility
            node.addPropertyDeletionOverride('Tags');
        }
    }
}

/**
 * Removes Tags property from all AWS::Events::Rule resources in a CDK application.
 * This is required for AWS GovCloud regions which don't support Tags on Rule resources.
 */
class RemoveEventRuleTagsAspect implements IAspect {
    /**
     * Checks if the given node is an instance of CfnResource and specifically an AWS::Events::Rule resource.
     * If true, it removes the Tags property to prevent deployment failures in AWS GovCloud regions.
     *
     * @param {Construct} node - The CDK construct being visited.
     */
    public visit (node: Construct): void {
        // Check if the node is a CloudFormation resource of type AWS::Events::Rule
        if (node instanceof events.CfnRule) {
            // Remove Tags property for AWS GovCloud compatibility
            node.addPropertyDeletionOverride('Tags');
        }
    }
}

/**
 * Removes invalid DynamoDB stream actions from table resource policies.
 * CDK 2.x can incorrectly add dynamodb:GetRecords and dynamodb:GetShardIterator
 * to table resource policies, but these are stream-only actions and cause deployment failures.
 */
class RemoveDynamoDBStreamActionsFromTablePolicyAspect implements IAspect {
    public visit (node: Construct): void {
        if (node instanceof CfnResource && node.cfnResourceType === 'AWS::DynamoDB::Table') {
            // Remove the ResourcePolicy property entirely to avoid the invalid stream actions
            node.addPropertyDeletionOverride('ResourcePolicy');
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
                    baseStackProps.synthesizer = createDefaultStackSynthesizer(config);
                    break;
                case stackSynthesizerType.LegacyStackSynthesizer:
                    baseStackProps.synthesizer = createDefaultStackSynthesizer(config);
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

        const apiBaseStack = new LisaApiBaseStack(this, 'LisaApiBase', {
            ...baseStackProps,
            stackName: createCdkId([config.deploymentName, config.appName, 'API']),
            description: `LISA-API: ${config.deploymentName}-${config.deploymentStage}`,
            vpc: networkingStack.vpc,
            securityGroups: [networkingStack.vpc.securityGroups.lambdaSg],
        });
        apiBaseStack.addDependency(coreStack);
        this.stacks.push(apiBaseStack);

        const apiDeploymentStack = new LisaApiDeploymentStack(this, 'LisaApiDeployment', {
            ...baseStackProps,
            description: `LISA-api-deployment: ${config.deploymentName}-${config.deploymentStage}`,
            stackName: createCdkId([config.deploymentName, config.appName, 'api-deployment', config.deploymentStage]),
            restApiId: apiBaseStack.restApiId,
        });
        apiDeploymentStack.addDependency(apiBaseStack);

        // API Tokens Stack - always deployed when auth is configured
        if (config.authConfig) {
            const apiTokensStack = new LisaApiTokensStack(this, 'LisaApiTokens', {
                ...baseStackProps,
                authorizer: apiBaseStack.authorizer!,
                description: `LISA-api-tokens: ${config.deploymentName}-${config.deploymentStage}`,
                restApiId: apiBaseStack.restApiId,
                rootResourceId: apiBaseStack.rootResourceId,
                stackName: createCdkId([config.deploymentName, config.appName, 'api-tokens', config.deploymentStage]),
                securityGroups: [networkingStack.vpc.securityGroups.lambdaSg],
                vpc: networkingStack.vpc,
            });
            apiTokensStack.addDependency(apiBaseStack);
            apiTokensStack.addDependency(coreStack);
            apiDeploymentStack.addDependency(apiTokensStack);
            this.stacks.push(apiTokensStack);
        }

        if (config.deployMcp) {
            const mcpApiStack = new LisaMcpApiStack(this, 'LisaMcpApi', {
                ...baseStackProps,
                authorizer: apiBaseStack.authorizer!,
                description: `LISA-mcp: ${config.deploymentName}-${config.deploymentStage}`,
                restApiId: apiBaseStack.restApiId,
                rootResourceId: apiBaseStack.rootResourceId,
                stackName: createCdkId([config.deploymentName, config.appName, 'mcp', config.deploymentStage]),
                securityGroups: [networkingStack.vpc.securityGroups.ecsModelAlbSg],
                vpc: networkingStack.vpc,
            });
            mcpApiStack.addDependency(apiBaseStack);
            // McpApiStack reads: layerVersion/*, bucket/bucket-access-logs, APP_MANAGEMENT_KEY
            mcpApiStack.addDependency(coreStack);
            apiDeploymentStack.addDependency(mcpApiStack);
            this.stacks.push(mcpApiStack);
        }
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
            this.stacks.push(metricsStack);
        }

        if (config.deployServe) {
            const serveStack = new LisaServeApplicationStack(this, 'LisaServe', {
                ...baseStackProps,
                description: `LISA-serve: ${config.deploymentName}-${config.deploymentStage}`,
                stackName: createCdkId([config.deploymentName, config.appName, 'serve', config.deploymentStage]),
                vpc: networkingStack.vpc,
                securityGroups: [networkingStack.vpc.securityGroups.lambdaSg],
                metricsQueueUrl: metricsStack ? `${config.deploymentPrefix}/queue-url/usage-metrics` : undefined,
            });
            this.stacks.push(serveStack);
            serveStack.addDependency(networkingStack);
            // ServeStack reads: roles/* from IAMStack (via EcsCluster)
            serveStack.addDependency(iamStack);
            // ServeStack reads: tokenTableName, APP_MANAGEMENT_KEY, iamAuthSetupFnArn, iamAuthSetupRoleArn from ApiBaseStack
            serveStack.addDependency(apiBaseStack);
            // ServeStack reads: queue-url/usage-metrics from MetricsStack (if deployMetrics)
            if (metricsStack) {
                serveStack.addDependency(metricsStack);
            }

            const modelsApiDeploymentStack = new LisaModelsApiStack(this, 'LisaModelsApiDeployment', {
                ...baseStackProps,
                authorizer: apiBaseStack.authorizer,
                description: `LISA-models: ${config.deploymentName}-${config.deploymentStage}`,
                lisaServeEndpointUrlPs: config.restApiConfig.internetFacing ? serveStack.endpointUrl : undefined,
                guardrailsTable: serveStack.guardrailsTable,
                restApiId: apiBaseStack.restApiId,
                rootResourceId: apiBaseStack.rootResourceId,
                stackName: createCdkId([config.deploymentName, config.appName, 'models', config.deploymentStage]),
                securityGroups: [networkingStack.vpc.securityGroups.ecsModelAlbSg],
                vpc: networkingStack.vpc,
            });
            // ModelsApiStack reads: layerVersion/*, bucket/bucket-access-logs from CoreStack
            modelsApiDeploymentStack.addDependency(coreStack);
            // ModelsApiStack reads: APP_MANAGEMENT_KEY from ApiBaseStack
            modelsApiDeploymentStack.addDependency(apiBaseStack);
            // ModelsApiStack reads: guardrailsTable from ServeStack (passed as prop, creates implicit dep)
            modelsApiDeploymentStack.addDependency(serveStack);
            apiDeploymentStack.addDependency(modelsApiDeploymentStack);
            this.stacks.push(modelsApiDeploymentStack);

            if (config.deployMcpWorkbench) {
                const mcpWorkbenchStack = new McpWorkbenchStack(this, 'LisaMcpWorkbench', {
                    ...baseStackProps,
                    stackName: createCdkId([config.deploymentName, config.appName, 'mcp-workbench', config.deploymentStage]),
                    description: `LISA-mcp-workbench: ${config.deploymentName}-${config.deploymentStage}`,
                    vpc: networkingStack.vpc,
                    restApiId: apiBaseStack.restApiId,
                    rootResourceId: apiBaseStack.rootResourceId,
                    apiCluster: serveStack.restApi.apiCluster,
                    authorizer: apiBaseStack.authorizer,
                });
                mcpWorkbenchStack.addDependency(coreStack);
                mcpWorkbenchStack.addDependency(apiBaseStack);
                mcpWorkbenchStack.addDependency(serveStack);
                apiDeploymentStack.addDependency(mcpWorkbenchStack);
                this.stacks.push(mcpWorkbenchStack);
            }

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
                // RagStack reads: layerVersion/*, bucket/bucket-access-logs from CoreStack
                ragStack.addDependency(coreStack);
                // RagStack reads: roles/ragLambdaRoleId from IAMStack
                ragStack.addDependency(iamStack);
                // RagStack reads: iamAuthSetupFnArn, iamAuthSetupRoleArn from ApiBaseStack
                ragStack.addDependency(apiBaseStack);
                // RagStack reads: modelTableName from ModelsApiStack
                ragStack.addDependency(modelsApiDeploymentStack);
                this.stacks.push(ragStack);
                apiDeploymentStack.addDependency(ragStack);
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
                // ChatStack reads: layerVersion/*, bucket/bucket-access-logs from CoreStack
                chatStack.addDependency(coreStack);
                chatStack.addDependency(apiBaseStack);
                // ChatStack reads: modelTableName from ModelsApiStack
                chatStack.addDependency(modelsApiDeploymentStack);
                // ChatStack reads: serve/endpoint from ServeStack
                chatStack.addDependency(serveStack);
                // ChatStack reads: queue-name/usage-metrics from MetricsStack (if deployMetrics)
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
                    // UIStack reads: bucket/bucket-access-logs from CoreStack
                    uiStack.addDependency(coreStack);
                    uiStack.addDependency(chatStack);
                    // UIStack reads: lisaServeRestApiUri from ServeStack
                    uiStack.addDependency(serveStack);
                    uiStack.addDependency(apiBaseStack);
                    apiDeploymentStack.addDependency(uiStack);
                    this.stacks.push(uiStack);
                }
            }

        }

        if (config.deployDocs) {
            const docsStack = new LisaDocsStack(this, 'LisaDocs', {
                ...baseStackProps
            });
            // DocsStack reads: bucket/bucket-access-logs from CoreStack
            docsStack.addDependency(coreStack);
            this.stacks.push(docsStack);
        }

        this.stacks.push(apiDeploymentStack);

        // Set CA certs for isolated regions
        if (config.region.includes('iso')) {
            const adcCABundleAspect = new AdcLambdaCABundleAspect();
            this.stacks.forEach((stack) => Aspects.of(stack).add(adcCABundleAspect));
        }

        // Set resource tags if not isolated region
        if (!config.region.includes('iso')) {
            for (const tag of config.tags ?? []) {
                Tags.of(this).add(tag['Key'], tag['Value']);
            }
            Tags.of(this).add('VERSION', VERSION);
        }

        // Apply permissions boundary aspect to all stacks if the boundary is defined in config.yaml
        if (config.permissionsBoundaryAspect) {
            this.stacks.forEach((lisaStack) => {
                Aspects.of(lisaStack).add(new AddPermissionBoundary(config.permissionsBoundaryAspect!));
            });
        }

        if (config.convertInlinePoliciesToManaged) {
            this.stacks.forEach((stack) => Aspects.of(stack).add(new ConvertInlinePoliciesToManaged()));
        }

        // Nag Suppressions
        this.stacks.forEach((stack) => {
            NagSuppressions.addStackSuppressions(stack, [
                {
                    id: 'NIST.800.53.R5-LambdaConcurrency',
                    reason: 'Not applying lambda concurrency limits',
                },
                {
                    id: 'NIST.800.53.R5-LambdaDLQ',
                    reason: 'Not creating lambda DLQs',
                },
            ]);
        });

        // Run CDK-nag on app if specified
        if (config.runCdkNag) {
            this.stacks.forEach((stack) => {
                Aspects.of(stack).add(new AwsSolutionsChecks({ reports: true, verbose: true }));
                Aspects.of(stack).add(new NIST80053R5Checks({ reports: true, verbose: true }));
            });
        }

        if (config.securityGroupConfig) {
            this.stacks.forEach((stack) => {
                Aspects.of(stack).add(new RemoveSecurityGroupAspect(config.securityGroupConfig?.modelSecurityGroupId));
            });
        }

        // Enforce updates to EC2 launch templates
        Aspects.of(this).add(new UpdateLaunchTemplateMetadataOptions());

        // Remove invalid DynamoDB stream actions from table resource policies
        // CDK 2.x bug adds GetRecords/GetShardIterator to table policies which are stream-only actions
        Aspects.of(this).add(new RemoveDynamoDBStreamActionsFromTablePolicyAspect());

        // Apply EventSourceMapping tags removal aspect for AWS GovCloud regions
        // AWS GovCloud regions don't support Tags on EventSourceMapping resources
        if (config.region.includes('gov')) {
            Aspects.of(this).add(new RemoveEventSourceMappingTagsAspect());
            Aspects.of(this).add(new RemoveEventRuleTagsAspect());
        }
    }
}

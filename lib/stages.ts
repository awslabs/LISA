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
    Stage,
    StageProps,
    Tags,
} from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { AwsSolutionsChecks, NIST80053R5Checks } from 'cdk-nag';

import { LisaChatApplicationStack } from './chat';
import { CoreStack, ARCHITECTURE } from './core';
import { LisaApiBaseStack } from './core/api_base';
import { LisaApiDeploymentStack } from './core/api_deployment';
import { createCdkId } from './core/utils';
import { LisaServeIAMStack } from './iam_stack';
import { LisaModelsApiStack } from './models';
import { LisaNetworkingStack } from './networking';
import { LisaRagStack } from './rag';
import { BaseProps, stackSynthesizerType } from './schema';
import { LisaServeApplicationStack } from './serve';
import { UserInterfaceStack } from './user-interface';
import { LisaDocsStack } from './docs';

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

type CommonStackProps = {
    synthesizer?: IStackSynthesizer;
} & BaseProps;

/**
 * LISA-serve Application Stage.
 */
export class LisaServeApplicationStage extends Stage {
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

        const stacks = [];
        // Stacks
        const iamStack = new LisaServeIAMStack(this, 'LisaServeIAMStack', {
            ...baseStackProps,
            stackName: createCdkId([config.deploymentName, config.appName, 'IAM', config.deploymentStage]),
            description: `LISA-serve: ${config.deploymentName}-${config.deploymentStage} IAM`,
        });
        stacks.push(iamStack);

        const networkingStack = new LisaNetworkingStack(this, 'LisaNetworking', {
            ...baseStackProps,
            stackName: createCdkId([config.deploymentName, config.appName, 'networking', config.deploymentStage]),
            description: `LISA-networking: ${config.deploymentName}-${config.deploymentStage}`,
        });
        stacks.push(networkingStack);

        const coreStack = new CoreStack(this, 'LisaCore', {
            ...baseStackProps,
            stackName: createCdkId([config.deploymentName, config.appName, 'core', config.deploymentStage]),
            description: `LISA-core: ${config.deploymentName}-${config.deploymentStage}`,
            vpc: networkingStack.vpc,
        });
        stacks.push(coreStack);

        const serveStack = new LisaServeApplicationStack(this, 'LisaServe', {
            ...baseStackProps,
            description: `LISA-serve: ${config.deploymentName}-${config.deploymentStage}`,
            stackName: createCdkId([config.deploymentName, config.appName, 'serve', config.deploymentStage]),
            vpc: networkingStack.vpc,
        });
        stacks.push(serveStack);

        serveStack.addDependency(iamStack);

        const apiBaseStack = new LisaApiBaseStack(this, 'LisaApiBase', {
            ...baseStackProps,
            stackName: createCdkId([config.deploymentName, config.appName, 'API']),
            description: `LISA-API: ${config.deploymentName}-${config.deploymentStage}`,
            vpc: networkingStack.vpc,
        });
        apiBaseStack.addDependency(coreStack);
        apiBaseStack.addDependency(serveStack);
        stacks.push(apiBaseStack);

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
            lisaServeEndpointUrlPs: serveStack.endpointUrl,
            restApiId: apiBaseStack.restApiId,
            rootResourceId: apiBaseStack.rootResourceId,
            stackName: createCdkId([config.deploymentName, config.appName, 'models', config.deploymentStage]),
            vpc: networkingStack.vpc,
        });
        modelsApiDeploymentStack.addDependency(serveStack);
        apiDeploymentStack.addDependency(modelsApiDeploymentStack);
        stacks.push(modelsApiDeploymentStack);

        if (config.deployChat) {
            const chatStack = new LisaChatApplicationStack(this, 'LisaChat', {
                ...baseStackProps,
                authorizer: apiBaseStack.authorizer,
                stackName: createCdkId([config.deploymentName, config.appName, 'chat', config.deploymentStage]),
                description: `LISA-chat: ${config.deploymentName}-${config.deploymentStage}`,
                restApiId: apiBaseStack.restApiId,
                rootResourceId: apiBaseStack.rootResourceId,
                vpc: networkingStack.vpc,
            });
            chatStack.addDependency(apiBaseStack);
            chatStack.addDependency(coreStack);
            apiDeploymentStack.addDependency(chatStack);
            stacks.push(chatStack);

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
                stacks.push(uiStack);

                if (config.deployRag) {
                    const ragStack = new LisaRagStack(this, 'LisaRAG', {
                        ...baseStackProps,
                        authorizer: apiBaseStack.authorizer,
                        description: `LISA-rag: ${config.deploymentName}-${config.deploymentStage}`,
                        endpointUrl: serveStack.endpointUrl,
                        modelsPs: serveStack.modelsPs,
                        restApiId: apiBaseStack.restApiId,
                        rootResourceId: apiBaseStack.rootResourceId,
                        stackName: createCdkId([config.deploymentName, config.appName, 'rag', config.deploymentStage]),
                        vpc: networkingStack.vpc,
                    });
                    ragStack.addDependency(coreStack);
                    ragStack.addDependency(iamStack);
                    ragStack.addDependency(apiBaseStack);
                    stacks.push(ragStack);

                    if (config.deployRag) {
                        uiStack.addDependency(ragStack);
                        apiDeploymentStack.addDependency(ragStack);
                    }
                }
            }
        }

        if (config.deployDocs) {
            const docsStack = new LisaDocsStack(this, 'LisaDocs', {
                ...baseStackProps
            });
            stacks.push(docsStack);
        }

        stacks.push(apiDeploymentStack);

        // Set resource tags
        if (!config.region.includes('iso')) {
            for (const tag of config.tags ?? []) {
                Tags.of(this).add(tag['Key'], tag['Value']);
            }
        }

        // Apply permissions boundary aspect to all stacks if the boundary is defined in
        // config.yaml
        if (config.permissionsBoundaryAspect) {
            stacks.forEach((lisaStack) => {
                Aspects.of(lisaStack).add(new AddPermissionBoundary(config.permissionsBoundaryAspect!));
            });
        }

        if (config.convertInlinePoliciesToManaged) {
            stacks.forEach((lisaStack) => {
                Aspects.of(lisaStack).add(new ConvertInlinePoliciesToManaged());
            });
        }

        // Run CDK-nag on app if specified
        if (config.runCdkNag) {
            stacks.forEach((lisaStack) => {
                Aspects.of(lisaStack).add(new AwsSolutionsChecks({ reports: true, verbose: true }));
                Aspects.of(lisaStack).add(new NIST80053R5Checks({ reports: true, verbose: true }));
            });
        }

        // Enforce updates to EC2 launch templates
        Aspects.of(this).add(new UpdateLaunchTemplateMetadataOptions());
    }
}

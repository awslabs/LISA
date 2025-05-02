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

import * as cdk from 'aws-cdk-lib';
import { LisaNetworkingStack } from '../../../lib/networking/index';
import { LisaApiBaseStack } from '../../../lib/core/api_base';
import { LisaChatApplicationStack } from '../../../lib/chat/index';
import { ARCHITECTURE, CoreStack } from '../../../lib/core/index';
import { LisaApiDeploymentStack } from '../../../lib/core/api_deployment';
import { LisaServeIAMStack } from '../../../lib/iam/iam_stack';
import { LisaServeApplicationStack } from '../../../lib/serve/index';
import { UserInterfaceStack } from '../../../lib/user-interface/index';
import ConfigParser from './ConfigParser';
import { Config } from '../../../lib/schema';
import { LisaDocsStack } from '../../../lib/docs';
import { LisaModelsApiStack } from '../../../lib/models';
import { LisaRagStack } from '../../../lib/rag';
import fs from 'node:fs';
import { DOCS_DIST_PATH, ECS_MODEL_DEPLOYER_DIST_PATH, VECTOR_STORE_DEPLOYER_DIST_PATH, WEBAPP_DIST_PATH } from '../../../lib/util';

export default class MockApp {

    private static mockApp: any;

    static getStacks () {
        if (!this.mockApp) {
            this.mockApp = MockApp.create();
        }
        return this.mockApp.stacks;
    }
    static getApp () {
        if (!this.mockApp) {
            this.mockApp = MockApp.create();
        }
        return this.mockApp.app;
    }

    static create (config?: Config) {
        process.env.NODE_ENV = 'test';
        const app = new cdk.App({
            context: {
                // Skip bundling for all assets
                '@aws-cdk/core:newStyleStackSynthesis': true,
                '@aws-cdk/aws-lambda:recognizeLayerVersion': true,
                '@aws-cdk/core:skipBundling': true,
                'aws:cdk:bundling-stacks': []
            }
        });
        config = config || ConfigParser.parseConfig();
        const baseStackProps = {
            env: {
                account: '012345678901',
                region: config.region,
            },
            config,
        };

        // Create dist folders to ensure stack creation
        [VECTOR_STORE_DEPLOYER_DIST_PATH, ECS_MODEL_DEPLOYER_DIST_PATH, DOCS_DIST_PATH, WEBAPP_DIST_PATH].forEach((distFolder) =>
            fs.mkdirSync(distFolder, { recursive: true })
        );

        const networkingStack = new LisaNetworkingStack(app, 'LisaNetworking', {
            ...baseStackProps,
            stackName: 'LisaNetworking'
        });
        const serveStack = new LisaServeApplicationStack(app, 'LisaServe', {
            ...baseStackProps,
            stackName: 'LisaServe',
            vpc: networkingStack.vpc,
        });
        const apiBaseStack = new LisaApiBaseStack(app, 'LisaApiBase', {
            ...baseStackProps,
            tokenTable: serveStack.tokenTable,
            stackName: 'LisaApiBase',
            vpc: networkingStack.vpc,
        });
        const chatStack = new LisaChatApplicationStack(app, 'LisaChat', {
            ...baseStackProps,
            authorizer: apiBaseStack.authorizer!,
            stackName: 'LisaChat',
            restApiId: apiBaseStack.restApiId,
            rootResourceId: apiBaseStack.rootResourceId,
            securityGroups: [networkingStack.vpc.securityGroups.lambdaSg],
            vpc: networkingStack.vpc,
        });
        const apiDeploymentStack = new LisaApiDeploymentStack(app, 'LisaApiDeployment', {
            ...baseStackProps,
            stackName: 'LisaApiDeployment',
            restApiId: apiBaseStack.restApiId,
        });
        const iamStack = new LisaServeIAMStack(app, 'LisaIAM', {
            ...baseStackProps,
            stackName: 'LisaIAM',
            config: config,
        });

        const uiStack = new UserInterfaceStack(app, 'LisaUI', {
            ...baseStackProps,
            architecture: ARCHITECTURE,
            stackName: 'LisaUI',
            restApiId: apiBaseStack.restApiId,
            rootResourceId: apiBaseStack.rootResourceId,
        });

        const docStack = new LisaDocsStack(app, 'LisaDocs', {
            ...baseStackProps,
            stackName: 'LisaDocs'
        });

        const coreStack = new CoreStack(app, 'LisaCore', {
            ...baseStackProps,
            stackName: 'LisaCore'
        });

        const ragStack = new LisaRagStack(app, 'LisaRAG', {
            ...baseStackProps,
            stackName: 'LisaRAG',
            authorizer: apiBaseStack.authorizer!,
            endpointUrl: serveStack.endpointUrl,
            modelsPs: serveStack.modelsPs,
            restApiId: apiBaseStack.restApiId,
            rootResourceId: apiBaseStack.rootResourceId,
            securityGroups: [networkingStack.vpc.securityGroups.lambdaSg],
            vpc: networkingStack.vpc,
        });

        const modelsStack = new LisaModelsApiStack(app, 'LisaModels', {
            ...baseStackProps,
            stackName: 'LisaModels',
            authorizer: apiBaseStack.authorizer,
            lisaServeEndpointUrlPs: serveStack.endpointUrl,
            restApiId: apiBaseStack.restApiId,
            rootResourceId: apiBaseStack.rootResourceId,
            securityGroups: [networkingStack.vpc.securityGroups.ecsModelAlbSg],
            vpc: networkingStack.vpc,
        });

        const stacks = [
            networkingStack,
            iamStack,
            apiBaseStack,
            apiDeploymentStack,
            chatStack,
            serveStack,
            uiStack,
            docStack,
            coreStack,
            modelsStack,
            ragStack,
        ];

        return { app, stacks };
    }
}

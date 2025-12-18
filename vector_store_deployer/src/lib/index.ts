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
import { App, Aspects, ValidationError } from 'aws-cdk-lib/core';
import { AddPermissionBoundary } from '@cdklabs/cdk-enterprise-iac';
import { OpenSearchVectorStoreStack } from './opensearch';
import { PGVectorStoreStack } from './pgvector';
import { RagRepositoryDeploymentConfigSchema, RagRepositoryType, PartialConfigSchema } from '../../../lib/schema';
import { BedrockKnowledgeBaseStack } from './bedrock_knowledge_base';

const app = new App();

console.log(`LISA_RAG_CONFIG = ${process.env['LISA_RAG_CONFIG']}`);
const ragConfig = RagRepositoryDeploymentConfigSchema.parse(JSON.parse(process.env['LISA_RAG_CONFIG']!));
console.log(`LISA_CONFIG = ${process.env['LISA_CONFIG']}`);
const config = PartialConfigSchema.parse(JSON.parse(process.env['LISA_CONFIG']!));
const stackName = process.env['LISA_STACK_NAME'];
console.log(`Using stack name: ${stackName}`);

if (!stackName) {
    throw new Error('LISA_STACK_NAME environment variable is required');
}

const vectorStoreProps = {
    config,
    ragConfig,
    env: {
        account: config.accountNumber,
        region: config.region
    },
};

let stack;
if (ragConfig.type === RagRepositoryType.OPENSEARCH) {
    stack = new OpenSearchVectorStoreStack(app, stackName, {
        ...vectorStoreProps,
    });
} else if (ragConfig.type === RagRepositoryType.PGVECTOR) {
    stack = new PGVectorStoreStack(app, stackName, {
        ...vectorStoreProps,
    });
} else if (ragConfig.type === RagRepositoryType.BEDROCK_KNOWLEDGE_BASE) {
    if (!ragConfig.pipelines || ragConfig.pipelines.length === 0) {
        throw new ValidationError('Bedrock KB repository has no pipelines, which means there are no datasources configured', app);
    }
    stack = new BedrockKnowledgeBaseStack(app, stackName, {
        ...vectorStoreProps,
    });
} else {
    console.error(`Unsupported repository type: ${ragConfig.type}`);
    throw new ValidationError(`Unsupported repository type: ${ragConfig.type}`, app);
}


if (stack && config.permissionsBoundaryAspect) {
    Aspects.of(stack).add(new AddPermissionBoundary(config.permissionsBoundaryAspect!));
}

app.synth();

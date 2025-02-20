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
import { App } from 'aws-cdk-lib/core';
import { OpenSearchVectorStoreStack } from './opensearch';
import { PGVectorStoreStack } from './pgvector';
import { RagRepositoryConfigSchema, RagRepositoryType,PartialConfigSchema } from '#root/lib/schema';

const app = new App();

console.log(`LISA_RAG_CONFIG = ${process.env['LISA_RAG_CONFIG']}`);
const ragConfig = RagRepositoryConfigSchema.parse(JSON.parse(process.env['LISA_RAG_CONFIG']!));
console.log(`LISA_CONFIG = ${process.env['LISA_CONFIG']}`);
const config = PartialConfigSchema.parse(JSON.parse(process.env['LISA_CONFIG']!));

const vectorStoreProps = {
    config,
    ragConfig,
    env: {
        account: config.accountNumber,
        region: config.region
    },
};

const stackName = process.env['LISA_STACK_NAME']!;
console.log(`Using stack name: ${stackName}`);

if  (ragConfig.type === RagRepositoryType.OPENSEARCH) {
    new OpenSearchVectorStoreStack(app, stackName, {
        ...vectorStoreProps,
    });
} else if (ragConfig.type === RagRepositoryType.PGVECTOR) {
    new PGVectorStoreStack(app, stackName, {
        ...vectorStoreProps,
    });
} else {
    console.error(`Unsupported repository type: ${ragConfig.type}`);
    throw new Error(`Unsupported repository type: ${ragConfig.type}`);
}

app.synth();

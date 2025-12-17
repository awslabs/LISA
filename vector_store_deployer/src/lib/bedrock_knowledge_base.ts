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
import { StackProps } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { RagRepositoryDeploymentConfig, PartialConfig } from '../../../lib/schema';
import { PipelineStack } from './pipeline-stack';

// Type definition for BedrockKnowledgeBaseStack properties
type BedrockKnowledgeBaseStackProps = StackProps & {
    config: PartialConfig,
    ragConfig: RagRepositoryDeploymentConfig,
};

// BedrockKnowledgeBaseStack class, extending PipelineStack
export class BedrockKnowledgeBaseStack extends PipelineStack {
    constructor (scope: Construct, id: string, props: BedrockKnowledgeBaseStackProps) {
        super(scope, id, props);

        // Destructure the configuration properties
        const { config, ragConfig } = props;

        this.createPipelineRules(config, ragConfig);
    }
}

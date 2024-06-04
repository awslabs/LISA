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

// LISA-serve Stack.
import path from 'path';

import { Stack, StackProps } from 'aws-cdk-lib';
import { AttributeType, BillingMode, Table, TableEncryption } from 'aws-cdk-lib/aws-dynamodb';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';

import { EcsModel } from './ecs-model';
import { FastApiContainer } from '../api-base/fastApiContainer';
import { createCdkId, getModelIdentifier } from '../core/utils';
import { Vpc } from '../networking/vpc';
import { BaseProps, ModelType, RegisteredModel } from '../schema';
import { ApplicationLoadBalancer } from 'aws-cdk-lib/aws-elasticloadbalancingv2';

const HERE = path.resolve(__dirname);

interface CustomLisaStackProps extends BaseProps {
  vpc: Vpc;
  alb: ApplicationLoadBalancer;
}
type LisaStackProps = CustomLisaStackProps & StackProps;

/**
 * LisaServe Application stack.
 */
export class LisaServeApplicationStack extends Stack {
  /** FastAPI construct */
  public readonly restApi: FastApiContainer;
  public readonly modelsPs: StringParameter;
  public readonly endpointUrl: StringParameter;

  /**
   * @param {Construct} scope - The parent or owner of the construct.
   * @param {string} id - The unique identifier for the construct within its scope.
   * @param {LisaStackProps} props - Properties for the Stack.
   */
  constructor(scope: Construct, id: string, props: LisaStackProps) {
    super(scope, id, props);

    const { config, vpc, alb } = props;

    // Create DynamoDB Table for enabling API token usage
    const tokenTable = new Table(this, 'TokenTable', {
      tableName: 'LISAApiTokenTable',
      partitionKey: {
        name: 'token',
        type: AttributeType.STRING,
      },
      billingMode: BillingMode.PAY_PER_REQUEST,
      encryption: TableEncryption.AWS_MANAGED,
      removalPolicy: config.removalPolicy,
    });

    // Create REST API
    const restApi = new FastApiContainer(this, 'RestApi', {
      apiName: 'REST',
      config: config,
      resourcePath: path.join(HERE, 'rest-api'),
      securityGroup: vpc.securityGroups.restApiAlbSg,
      taskConfig: config.restApiConfig,
      tokenTable: tokenTable,
      vpc: vpc.vpc,
      alb
    });

    // Create Parameter Store entry with RestAPI URI
    this.endpointUrl = new StringParameter(this, createCdkId(['LisaServeRestApiUri', 'StringParameter']), {
      parameterName: `${config.deploymentPrefix}/lisaServeRestApiUri`,
      stringValue: restApi.endpoint,
      description: 'URI for LISA Serve API',
    });

    // Register all models
    const registeredModels: RegisteredModel[] = [];

    // Create ECS models
    for (const modelConfig of config.ecsModels) {
      if (modelConfig.deploy) {
        // Create ECS Model Construct
        const ecsModel = new EcsModel(this, createCdkId([getModelIdentifier(modelConfig), 'EcsModel']), {
          config: config,
          modelConfig: modelConfig,
          securityGroup: vpc.securityGroups.ecsModelAlbSg,
          vpc: vpc.vpc,
        });

        // Create metadata to register model in parameter store
        const registeredModel: RegisteredModel = {
          provider: `${modelConfig.modelHosting}.${modelConfig.modelType}.${modelConfig.inferenceContainer}`,
          modelName: modelConfig.modelName,
          modelType: modelConfig.modelType,
          endpointUrl: ecsModel.endpointUrl,
        };

        // For textgen models, add metadata whether streaming is supported
        if (modelConfig.modelType == ModelType.TEXTGEN) {
          registeredModel.streaming = modelConfig.streaming!;
        }
        registeredModels.push(registeredModel);
      }
    }

    // Create Parameter Store entry with registeredModels
    this.modelsPs = new StringParameter(this, createCdkId(['RegisteredModels', 'StringParameter']), {
      parameterName: `${config.deploymentPrefix}/registeredModels`,
      stringValue: JSON.stringify(registeredModels),
      description: 'Serialized JSON of registered models data',
    });

    this.modelsPs.grantRead(restApi.taskRole);
    // Add parameter as container environment variable for both RestAPI and RagAPI
    restApi.container.addEnvironment('REGISTERED_MODELS_PS_NAME', this.modelsPs.parameterName);

    // Update
    this.restApi = restApi;
  }
}

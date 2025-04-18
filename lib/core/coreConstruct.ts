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
import * as lambda from 'aws-cdk-lib/aws-lambda';
import { ILayerVersion, LayerVersion } from 'aws-cdk-lib/aws-lambda';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';

import { Layer } from './layers';
import { BaseProps } from '../schema';
import { createCdkId } from './utils';
import { PythonLayerVersion } from '@aws-cdk/aws-lambda-python-alpha';
import { getDefaultRuntime } from '../api-base/utils';
import { Stack, StackProps } from 'aws-cdk-lib';
import { COMMON_LAYER_PATH, FASTAPI_LAYER_PATH, AUTHORIZER_LAYER_PATH, SDK_PATH } from '../util';

export const ARCHITECTURE = lambda.Architecture.X86_64;
process.env.DOCKER_DEFAULT_PLATFORM = ARCHITECTURE.dockerPlatform;

export type CoreStackProps = BaseProps & StackProps;

/**
 * Creates Lambda layers
 */
export class CoreConstruct extends Construct {
    /**
   * @param {Construct} scope - The parent or owner of the construct.
   * @param {string} id - The unique identifier for the construct within its scope.
   */
    constructor (scope: Stack, id: string, props: CoreStackProps) {
        super(scope, id);
        const { config } = props;

        // Create Lambda Layers
        // Build common Lambda layer
        const commonLambdaLayer = new Layer(scope, 'CommonLayer', {
            config: config,
            path: COMMON_LAYER_PATH,
            description: 'Common requirements for REST API Lambdas',
            architecture: ARCHITECTURE,
            autoUpgrade: true,
            assetPath: config.lambdaLayerAssets?.commonLayerPath,
        });

        // Build fastapi Lambda layer
        const fastapiLambdaLayer = new Layer(scope, 'FastapiLayer', {
            config: config,
            path: FASTAPI_LAYER_PATH,
            description: 'FastAPI requirements for REST API Lambdas',
            architecture: ARCHITECTURE,
            autoUpgrade: true,
            assetPath: config.lambdaLayerAssets?.fastapiLayerPath,
        });

        // Build authorizer Lambda layer
        const authorizerLambdaLayer = new Layer(scope, 'AuthorizerLayer', {
            config: config,
            path: AUTHORIZER_LAYER_PATH,
            description: 'API authorization dependencies for REST API',
            architecture: ARCHITECTURE,
            autoUpgrade: true,
            assetPath: config.lambdaLayerAssets?.authorizerLayerPath,
        });

        // Build SDK Layer
        let sdkLambdaLayer: ILayerVersion;
        if (config.lambdaLayerAssets?.sdkLayerPath) {
            sdkLambdaLayer = new LayerVersion(scope, 'SdkLayer', {
                code: lambda.Code.fromAsset(config.lambdaLayerAssets?.sdkLayerPath),
                compatibleRuntimes: [getDefaultRuntime()],
                removalPolicy: config.removalPolicy,
                description: 'LISA SDK common layer',
            });
        } else {
            sdkLambdaLayer = new PythonLayerVersion(scope, 'SdkLayer', {
                entry: SDK_PATH,
                compatibleRuntimes: [getDefaultRuntime()],
                removalPolicy: config.removalPolicy,
                description: 'LISA SDK common layer',
            });
        }

        new StringParameter(scope, 'LisaCommonLamdaLayerStringParameter', {
            parameterName: `${config.deploymentPrefix}/layerVersion/common`,
            stringValue: commonLambdaLayer.layer.layerVersionArn,
            description: 'Layer Version ARN for LISA Common Lambda Layer',
        });

        new StringParameter(scope, 'LisaFastapiLamdaLayerStringParameter', {
            parameterName: `${config.deploymentPrefix}/layerVersion/fastapi`,
            stringValue: fastapiLambdaLayer.layer.layerVersionArn,
            description: 'Layer Version ARN for LISA FastAPI Lambda Layer',
        });

        new StringParameter(scope, 'LisaAuthorizerLamdaLayerStringParameter', {
            parameterName: `${config.deploymentPrefix}/layerVersion/authorizer`,
            stringValue: authorizerLambdaLayer.layer.layerVersionArn,
            description: 'Layer Version ARN for LISA Authorizer Lambda Layer',
        });

        new StringParameter(scope, createCdkId([config.deploymentName, config.deploymentStage, 'SdkLayer']), {
            parameterName: `${config.deploymentPrefix}/layerVersion/lisa-sdk`,
            stringValue: sdkLambdaLayer.layerVersionArn,
            description: 'Layer Version ARN for LISA SDK Layer',
        });
    }
}

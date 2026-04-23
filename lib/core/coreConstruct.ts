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
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';

import { Layer, NodeLayer } from './layers';
import { BaseProps } from '../schema';
import { RemovalPolicy, Stack, StackProps } from 'aws-cdk-lib';

import { AUTHORIZER_LAYER_PATH, CDK_LAYER_PATH, COMMON_LAYER_PATH, FASTAPI_LAYER_PATH, LAMBDA_SHARED_PATH } from '../util';
import { BlockPublicAccess, Bucket, BucketEncryption, ObjectOwnership } from 'aws-cdk-lib/aws-s3';
import { getNodeRuntime, getPythonRuntime } from '../api-base/utils';

export const ARCHITECTURE = lambda.Architecture.X86_64;
process.env.DOCKER_DEFAULT_PLATFORM = ARCHITECTURE.dockerPlatform;

export type CoreStackProps = BaseProps & StackProps;

/**
 * Creates Lambda layers
 */
export class CoreConstruct extends Construct {
    public readonly loggingBucket: Bucket;
    /**
   * @param {Construct} scope - The parent or owner of the construct.
   * @param {string} id - The unique identifier for the construct within its scope.
   */
    constructor (scope: Stack, id: string, props: CoreStackProps) {
        super(scope, id);
        const { config } = props;

        this.loggingBucket = new Bucket(scope, 'BucketAccessLogsBucket', {
            removalPolicy: config.removalPolicy,
            autoDeleteObjects: config.removalPolicy === RemovalPolicy.DESTROY,
            bucketName: ([config.deploymentName, config.accountNumber, config.deploymentStage, 'bucket', 'access', 'logs'].join('-')).toLowerCase(),
            enforceSSL: true,
            encryption: BucketEncryption.S3_MANAGED,
            blockPublicAccess: BlockPublicAccess.BLOCK_ALL,
            objectOwnership: ObjectOwnership.BUCKET_OWNER_PREFERRED,
        });

        new StringParameter(scope, 'LISABucketAccessLogsBucket', {
            parameterName: `${config.deploymentPrefix}/bucket/bucket-access-logs`,
            stringValue: this.loggingBucket.bucketArn,
            description: 'A bucket for access logs from other buckets to be written to.',
        });

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

        // Build shared first-party Python source layer. Contents of
        // `lambda/shared/python/` land at /opt/python/ at runtime so every
        // Python Lambda can `import lisa.*` without bundling the source.
        const lisaSharedLayer = new lambda.LayerVersion(scope, 'LisaSharedLayer', {
            code: lambda.Code.fromAsset(LAMBDA_SHARED_PATH),
            description: 'LISA shared Python source modules (lisa.*)',
            compatibleRuntimes: [getPythonRuntime()],
            removalPolicy: config.removalPolicy,
        });

        // Build CDK Lambda layer for deployer functions
        const cdkLambdaLayer = new NodeLayer(scope, 'CdkLayer', {
            config: config,
            path: CDK_LAYER_PATH,
            description: 'AWS CDK dependencies for deployer Lambdas',
            runtime: getNodeRuntime(),
            assetPath: config.lambdaLayerAssets?.cdkLayerPath,
        });

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

        new StringParameter(scope, 'LisaCdkLamdaLayerStringParameter', {
            parameterName: `${config.deploymentPrefix}/layerVersion/cdk`,
            stringValue: cdkLambdaLayer.layer.layerVersionArn,
            description: 'Layer Version ARN for LISA CDK Lambda Layer',
        });

        new StringParameter(scope, 'LisaSharedLambdaLayerStringParameter', {
            parameterName: `${config.deploymentPrefix}/layerVersion/lisa-shared`,
            stringValue: lisaSharedLayer.layerVersionArn,
            description: 'Layer Version ARN for LISA first-party shared Python source layer',
        });
    }
}

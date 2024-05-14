import * as path from 'path';

import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';

import { Layer } from './layers';
import { Vpc } from '../networking/vpc';
import { BaseProps } from '../schema';

const HERE = path.resolve(__dirname);
const COMMON_LAYER_PATH = path.join(HERE, 'layers', 'common');
const AUTHORIZER_LAYER_PATH = path.join(HERE, 'layers', 'authorizer');
export const ARCHITECTURE = lambda.Architecture.X86_64;
process.env.DOCKER_DEFAULT_PLATFORM = ARCHITECTURE.dockerPlatform;

interface CustomCoreStackProps extends BaseProps {
  vpc: Vpc;
}
type CoreStackProps = CustomCoreStackProps & cdk.StackProps;

/**
 * Creates a virtual private cloud (VPC) and other networking resources.
 */
export class CoreStack extends cdk.Stack {
  /**
   * @param {Construct} scope - The parent or owner of the construct.
   * @param {string} id - The unique identifier for the construct within its scope.
   */
  constructor(scope: Construct, id: string, props: CoreStackProps) {
    super(scope, id, props);
    const { config } = props;

    // Create Lambda Layers
    // Build common Lambda layer
    const commonLambdaLayer = new Layer(this, 'CommonLayer', {
      config: config,
      path: COMMON_LAYER_PATH,
      description: 'Common requirements for REST API Lambdas',
      architecture: ARCHITECTURE,
      autoUpgrade: true,
      assetPath: config.lambdaLayerAssets?.commonLayerPath,
    });

    // Build authorizer Lambda layer
    const authorizerLambdaLayer = new Layer(this, 'AuthorizerLayer', {
      config: config,
      path: AUTHORIZER_LAYER_PATH,
      description: 'API authorization dependencies for REST API',
      architecture: ARCHITECTURE,
      autoUpgrade: true,
      assetPath: config.lambdaLayerAssets?.authorizerLayerPath,
    });

    new StringParameter(this, 'LisaCommonLamdaLayerStringParameter', {
      parameterName: `${config.deploymentPrefix}/layerVersion/common`,
      stringValue: commonLambdaLayer.layer.layerVersionArn,
      description: `Layer Version ARN for LISA Common Lambda Layer`,
    });

    new StringParameter(this, 'LisaAuthorizerLamdaLayerStringParameter', {
      parameterName: `${config.deploymentPrefix}/layerVersion/authorizer`,
      stringValue: authorizerLambdaLayer.layer.layerVersionArn,
      description: `Layer Version ARN for LISA Authorizer Lambda Layer`,
    });
  }
}

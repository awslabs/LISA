import * as cdk from 'aws-cdk-lib';
import { RequestAuthorizer, IdentitySource } from 'aws-cdk-lib/aws-apigateway';
import { ISecurityGroup, IVpc } from 'aws-cdk-lib/aws-ec2';
import { IRole } from 'aws-cdk-lib/aws-iam';
import { Code, Function, LayerVersion } from 'aws-cdk-lib/aws-lambda';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';

import { BaseProps } from '../schema';

/**
 * Properties for RestApiGateway Construct.
 *
 * @property {IVpc} vpc - Stack VPC
 * @property {Layer} authorizerLayer - Lambda layer for authorizer lambda.
 * @property {IRole} role - Execution role for lambdas
 * @property {ISecurityGroup[]} securityGroups - Security groups for Lambdas
 */
interface AuthorizerProps extends BaseProps {
  role?: IRole;
  vpc?: IVpc;
  securityGroups?: ISecurityGroup[];
}

/**
 * Lambda Authorizer Construct.
 */
export class Authorizer extends Construct {
  /** Authorizer Lambda */
  public readonly authorizer: RequestAuthorizer;

  /**
   * @param {Construct} scope - The parent or owner of the construct.
   * @param {string} id - The unique identifier for the construct within its scope.
   * @param {AuthorizerProps} props - The properties of the construct.
   */
  constructor(scope: Construct, id: string, props: AuthorizerProps) {
    super(scope, id);

    const { config, role, vpc, securityGroups } = props;

    const commonLambdaLayer = LayerVersion.fromLayerVersionArn(
      this,
      'base-common-lambda-layer',
      StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/layerVersion/common`),
    );

    const authorizerLambdaLayer = LayerVersion.fromLayerVersionArn(
      this,
      'base-authorizer-lambda-layer',
      StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/layerVersion/authorizer`),
    );

    // Create Lambda authorizer
    const authorizerLambda = new Function(this, 'AuthorizerLambda', {
      runtime: config.lambdaConfig.pythonRuntime,
      handler: `authorizer.lambda_functions.lambda_handler`,
      functionName: `${cdk.Stack.of(this).stackName}-lambda-authorizer`,
      code: Code.fromAsset(config.lambdaSourcePath),
      description: 'REST API and UI Authorization Lambda',
      timeout: cdk.Duration.seconds(30),
      memorySize: 128,
      layers: [authorizerLambdaLayer, commonLambdaLayer],
      environment: {
        CLIENT_ID: config.authConfig.clientId,
        AUTHORITY: config.authConfig.authority,
      },
      role: role,
      vpc: vpc,
      securityGroups: securityGroups,
    });

    // Update
    this.authorizer = new RequestAuthorizer(this, 'APIGWAuthorizer', {
      handler: authorizerLambda,
      resultsCacheTtl: cdk.Duration.seconds(0),
      identitySources: [IdentitySource.header('Authorization')],
    });
  }
}

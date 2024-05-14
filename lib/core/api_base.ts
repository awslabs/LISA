import { Stack, StackProps } from 'aws-cdk-lib';
import { Cors, EndpointType, IAuthorizer, RestApi, StageOptions } from 'aws-cdk-lib/aws-apigateway';
import { IVpc } from 'aws-cdk-lib/aws-ec2';
import { Construct } from 'constructs';

import { Authorizer } from '../api-base/authorizer';
import { BaseProps } from '../schema';

interface LisaApiBaseStackProps extends BaseProps, StackProps {
  vpc: IVpc;
}

export class LisaApiBaseStack extends Stack {
  public readonly authorizer: IAuthorizer;
  public readonly restApiId: string;
  public readonly rootResourceId: string;
  public readonly restApiUrl: string;

  constructor(scope: Construct, id: string, props: LisaApiBaseStackProps) {
    super(scope, id, props);

    const { config, vpc } = props;

    const deployOptions: StageOptions = {
      stageName: config.deploymentStage,
      throttlingRateLimit: 100,
      throttlingBurstLimit: 100,
    };

    const restApi = new RestApi(this, `${id}-RestApi`, {
      description: 'Base API Gateway for LISA.',
      endpointConfiguration: { types: [EndpointType.REGIONAL] },
      deploy: true,
      deployOptions,
      defaultCorsPreflightOptions: {
        allowOrigins: Cors.ALL_ORIGINS,
        allowHeaders: [...Cors.DEFAULT_HEADERS],
      },
      // Support binary media types used for documentation images and fonts
      binaryMediaTypes: ['font/*', 'image/*'],
    });

    // Create the authorizer Lambda for APIGW
    const authorizer = new Authorizer(this, 'LisaApiAuthorizer', {
      config: config,
      vpc,
    });

    this.restApiId = restApi.restApiId;
    this.rootResourceId = restApi.restApiRootResourceId;
    this.authorizer = authorizer.authorizer;
    this.restApiUrl = restApi.url;
  }
}

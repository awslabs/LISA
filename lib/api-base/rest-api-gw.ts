import { Cors, EndpointType, RestApi, StageOptions } from 'aws-cdk-lib/aws-apigateway';
import { Construct } from 'constructs';

import { BaseProps } from '../schema';

/**
 * Properties for RestApiGateway Construct.
 */
interface RestApiGatewayProps extends BaseProps {}

/**
 * RestApiGateway Stack.
 */
export class RestApiGateway extends Construct {
  /** REST API URL. */
  public readonly url: string;

  /** REST APIGW fronting the UI and Lambdas */
  public readonly restApi: RestApi;

  /**
   * @param {Construct} scope - The parent or owner of the construct.
   * @param {string} id - The unique identifier for the construct within its scope.
   * @param {RestApiGatewayProps} props - The properties of the construct.
   */
  constructor(scope: Construct, id: string, props: RestApiGatewayProps) {
    super(scope, id);

    const { config } = props;

    const deployOptions: StageOptions = {
      stageName: config.deploymentStage,
      throttlingRateLimit: 100,
      throttlingBurstLimit: 100,
    };

    this.restApi = new RestApi(this, `${id}-RestApi`, {
      description: 'The User Interface and session management Lambda API Layer.',
      endpointConfiguration: { types: [EndpointType.REGIONAL] },
      deployOptions,
      defaultCorsPreflightOptions: {
        allowOrigins: Cors.ALL_ORIGINS,
        allowHeaders: [...Cors.DEFAULT_HEADERS],
      },
      // Support binary media types used for documentation images and fonts
      binaryMediaTypes: ['font/*', 'image/*'],
    });

    // Update
    this.url = this.restApi.url;
  }
}

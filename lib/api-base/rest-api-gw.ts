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

import { Cors, EndpointType, RestApi, StageOptions } from 'aws-cdk-lib/aws-apigateway';
import { Construct } from 'constructs';

import { BaseProps } from '../schema';

/**
 * Properties for RestApiGateway Construct.
 */
export type RestApiGatewayProps = {} & BaseProps;

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
    constructor (scope: Construct, id: string, props: RestApiGatewayProps) {
        super(scope, id);

        const { config } = props;

        const deployOptions: StageOptions = {
            stageName: config.deploymentStage,
            throttlingRateLimit: 100,
            throttlingBurstLimit: 100,
        };

        this.restApi = new RestApi(this, `${id}-RestApi`, {
            description: 'The User Interface and session management Lambda API Layer.',
            endpointTypes: [EndpointType.REGIONAL],
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

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

import { Aws, CfnOutput, Stack, StackProps } from 'aws-cdk-lib';
import { Deployment, RestApi } from 'aws-cdk-lib/aws-apigateway';
import { Construct } from 'constructs';

import { BaseProps } from '../schema';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';

export type LisaApiDeploymentProps = {
    restApiId: string;
} & BaseProps &
  StackProps;

/**
 * Create LISA API Deployment stack resources
 */
export class LisaApiDeploymentConstruct extends Construct {
    constructor (scope: Stack, id: string, props: LisaApiDeploymentProps) {
        super(scope, id);

        const { restApiId, config } = props;

        // Workaround so that the APIGW endpoint always updates with the latest changes across all stacks
        // Relevant CDK issues:
        // https://github.com/aws/aws-cdk/issues/12417
        // https://github.com/aws/aws-cdk/issues/13383
        const deployment = new Deployment(scope, `Deployment-${new Date().getTime()}`, {
            api: RestApi.fromRestApiId(scope, 'restApiRef', restApiId),
        });

        // Hack to allow deploying to an existing stage
        // https://github.com/aws/aws-cdk/issues/25582
        (deployment as any).resource.stageName = config.deploymentStage;

        const api_url = `https://${restApiId}.execute-api.${Aws.REGION}.${Aws.URL_SUFFIX}/${config.deploymentStage}`;
        new StringParameter(scope, 'LisaApiDeploymentStringParameter', {
            parameterName: `${config.deploymentPrefix}/${config.deploymentName}/${config.appName}/LisaApiUrl`,
            stringValue: api_url,
            description: 'API Gateway URL for LISA',
        });
        new CfnOutput(scope, 'ApiUrl', {
            value: api_url,
            description: 'API Gateway URL'
        });
    }
}

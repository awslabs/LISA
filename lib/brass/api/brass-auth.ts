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

import { IAuthorizer, RestApi } from 'aws-cdk-lib/aws-apigateway';
import { Role, ServicePrincipal, ManagedPolicy, Effect, PolicyStatement } from 'aws-cdk-lib/aws-iam';
import { ISecurityGroup } from 'aws-cdk-lib/aws-ec2';
import { LayerVersion } from 'aws-cdk-lib/aws-lambda';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';

import { getDefaultRuntime, PythonLambdaFunction, registerAPIEndpoint } from '../../api-base/utils';
import { BaseProps } from '../../schema';
import { Vpc } from '../../networking/vpc';
import { LAMBDA_PATH } from '../../util';

/**
 * Properties for BrassAuthApi Construct.
 */
type BrassAuthApiProps = {
    authorizer?: IAuthorizer;
    restApiId: string;
    rootResourceId: string;
    securityGroups: ISecurityGroup[];
    vpc: Vpc;
} & BaseProps;

/**
 * API for BRASS authorization requests
 */
export class BrassAuthApi extends Construct {
    constructor (scope: Construct, id: string, props: BrassAuthApiProps) {
        super(scope, id);

        const { authorizer, config, restApiId, rootResourceId, securityGroups, vpc } = props;

        // Get common layer based on arn from SSM
        const commonLambdaLayer = LayerVersion.fromLayerVersionArn(
            this,
            'brass-common-lambda-layer',
            StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/layerVersion/common`),
        );

        const restApi = RestApi.fromRestApiAttributes(this, 'RestApi', {
            restApiId: restApiId,
            rootResourceId: rootResourceId,
        });

        const env = {
            // BRASS Bindle Lock Configuration - following same pattern as authorizer
            ADMIN_BINDLE_GUID: config.authConfig!.adminAccessBindleLockGuid,
            APP_BINDLE_GUID: config.authConfig!.appAccessBindleLockGuid,
            BRASS_ENDPOINT: config.authConfig!.brassEndpoint,
            // AWS Region for proper BRASS service signing (custom variable since AWS_REGION is reserved)
            BRASS_REGION: config.region,
        };

        // Create API Lambda functions
        const apis: PythonLambdaFunction[] = [
            {
                name: 'lambda_handler',
                resource: 'brass',
                description: 'BRASS authorization endpoint',
                path: 'brass/authorize',
                method: 'POST',
                environment: env,
            },
        ];

        // Create Lambda execution role
        const lambdaRole = new Role(this, 'BrassAuthApiRole', {
            assumedBy: new ServicePrincipal('lambda.amazonaws.com'),
            description: 'Execution role for BRASS authorization Lambda',
            managedPolicies: [
                ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaVPCAccessExecutionRole'),
            ],
        });

        // Add BRASS service permissions for bindle lock authorization
        if (config.authConfig?.adminAccessBindleLockGuid || config.authConfig?.appAccessBindleLockGuid) {
            lambdaRole.addToPolicy(new PolicyStatement({
                effect: Effect.ALLOW,
                actions: [
                    'brassservice:IsAuthorized',
                    'brassservice:BatchIsAuthorized',
                ],
                resources: ['*'], // BRASS service permissions are typically granted on all resources
            }));
        }
        
        const lambdaPath = config.lambdaPath || LAMBDA_PATH;
        
        apis.forEach((f) => {
            registerAPIEndpoint(
                this,
                restApi,
                lambdaPath,
                [commonLambdaLayer],
                f,
                getDefaultRuntime(),
                vpc,
                securityGroups,
                authorizer,
                lambdaRole,
            );
        });
    }
}

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

import * as cdk from 'aws-cdk-lib';
import { RequestAuthorizer, IdentitySource } from 'aws-cdk-lib/aws-apigateway';
import { ISecurityGroup, IVpc } from 'aws-cdk-lib/aws-ec2';
import { IRole } from 'aws-cdk-lib/aws-iam';
import { Code, Function, LayerVersion } from 'aws-cdk-lib/aws-lambda';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';

import { BaseProps } from '../schema';
import { ITable } from 'aws-cdk-lib/aws-dynamodb';

/**
 * Properties for RestApiGateway Construct.
 *
 * @property {IVpc} vpc - Stack VPC
 * @property {Layer} authorizerLayer - Lambda layer for authorizer lambda.
 * @property {IRole} role - Execution role for lambdas
 * @property {ISecurityGroup[]} securityGroups - Security groups for Lambdas
 */
type AuthorizerProps = {
    role?: IRole;
    vpc?: IVpc;
    securityGroups?: ISecurityGroup[];
    tokenTable: ITable | undefined;
} & BaseProps;

/**
 * Lambda Authorizer Construct.
 */
export class CustomAuthorizer extends Construct {
    /** Authorizer Lambda */
    public readonly authorizer: RequestAuthorizer;

    /**
   * @param {Construct} scope - The parent or owner of the construct.
   * @param {string} id - The unique identifier for the construct within its scope.
   * @param {AuthorizerProps} props - The properties of the construct.
   */
    constructor (scope: Construct, id: string, props: AuthorizerProps) {
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
            handler: 'authorizer.lambda_functions.lambda_handler',
            functionName: `${cdk.Stack.of(this).stackName}-lambda-authorizer`,
            code: Code.fromAsset(config.lambdaSourcePath),
            description: 'REST API and UI Authorization Lambda',
            timeout: cdk.Duration.seconds(30),
            memorySize: 128,
            layers: [authorizerLambdaLayer, commonLambdaLayer],
            environment: {
                CLIENT_ID: config.authConfig!.clientId,
                AUTHORITY: config.authConfig!.authority,
                ADMIN_GROUP: config.authConfig!.adminGroup,
                JWT_GROUPS_PROP: config.authConfig!.jwtGroupsProperty,
                TOKEN_TABLE_NAME: props.tokenTable?.tableName ?? ''
            },
            role: role,
            vpc: vpc,
            securityGroups: securityGroups,
        });

        props.tokenTable?.grantReadData(authorizerLambda);

        // Update
        this.authorizer = new RequestAuthorizer(this, 'APIGWAuthorizer', {
            handler: authorizerLambda,
            resultsCacheTtl: cdk.Duration.seconds(0),
            identitySources: [IdentitySource.header('Authorization')],
        });
    }
}

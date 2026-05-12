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
import { CustomResource, Duration } from 'aws-cdk-lib';
import {
    Effect,
    ManagedPolicy,
    PolicyStatement,
    Role,
    ServicePrincipal,
} from 'aws-cdk-lib/aws-iam';
import { ILayerVersion } from 'aws-cdk-lib/aws-lambda';
import { ISecurityGroup } from 'aws-cdk-lib/aws-ec2';
import { ITable } from 'aws-cdk-lib/aws-dynamodb';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { Provider } from 'aws-cdk-lib/custom-resources';
import { Construct } from 'constructs';

import { APP_MANAGEMENT_KEY, BaseProps } from '../schema';
import { Vpc } from '../networking/vpc';
import { definePythonLambda } from '../util';

export type LiteLLMSyncConstructProps = {
    modelTable: ITable;
    lambdaLayers: ILayerVersion[];
    vpc: Vpc;
    securityGroups: ISecurityGroup[];
} & BaseProps;

/**
 * Construct that creates a Lambda custom resource to sync models from DynamoDB to LiteLLM.
 * This is triggered on every deployment to ensure all models in the Models DynamoDB table
 * are registered in LiteLLM after the database is created or updated.
 */
export class LiteLLMSyncConstruct extends Construct {
    constructor (scope: Construct, id: string, props: LiteLLMSyncConstructProps) {
        super(scope, id);

        const { config, modelTable, lambdaLayers, vpc, securityGroups } = props;

        const managementKeyName = StringParameter.valueForStringParameter(
            this,
            `${config.deploymentPrefix}/${APP_MANAGEMENT_KEY}`
        );

        const litellmSyncRole = new Role(this, 'LiteLLMModelSyncRole', {
            assumedBy: new ServicePrincipal('lambda.amazonaws.com'),
            managedPolicies: [
                ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaVPCAccessExecutionRole'),
            ],
        });

        // Grant permissions to read/update the specific model table
        litellmSyncRole.addToPrincipalPolicy(new PolicyStatement({
            effect: Effect.ALLOW,
            actions: ['dynamodb:Scan', 'dynamodb:GetItem', 'dynamodb:UpdateItem'],
            resources: [modelTable.tableArn],
        }));

        // Grant access to SSM parameters
        litellmSyncRole.addToPrincipalPolicy(new PolicyStatement({
            effect: Effect.ALLOW,
            actions: ['ssm:GetParameter'],
            resources: [`arn:${config.partition}:ssm:${config.region}:${config.accountNumber}:parameter${config.deploymentPrefix}/*`],
        }));

        // Grant access to management key secret (scoped to the specific secret name)
        litellmSyncRole.addToPrincipalPolicy(new PolicyStatement({
            effect: Effect.ALLOW,
            actions: ['secretsmanager:GetSecretValue'],
            resources: [`arn:${config.partition}:secretsmanager:${config.region}:${config.accountNumber}:secret:${managementKeyName}*`],
        }));

        // Grant IAM access for SSL cert validation
        litellmSyncRole.addToPrincipalPolicy(new PolicyStatement({
            effect: Effect.ALLOW,
            actions: ['iam:GetServerCertificate'],
            resources: ['*'],
        }));

        const litellmModelSyncLambda = definePythonLambda(this, 'LiteLLMModelSync', {
            handlerDir: 'models',
            entry: 'litellm_model_sync.handler',
            config,
            layers: lambdaLayers,
            environment: {
                MODEL_TABLE_NAME: modelTable.tableName,
                MANAGEMENT_KEY_NAME: managementKeyName,
                LISA_API_URL_PS_NAME: `${config.deploymentPrefix}/lisaServeRestApiUri`,
                REST_API_VERSION: 'v2',
                RESTAPI_SSL_CERT_ARN: config.restApiConfig?.sslCertIamArn ?? '',
            },
            role: litellmSyncRole,
            vpc,
            securityGroups,
            timeout: Duration.minutes(10),
            description: 'Sync all models from DynamoDB to LiteLLM when the LiteLLM database is created or updated',
        });

        const syncProvider = new Provider(this, 'LiteLLMModelSyncProvider', {
            onEventHandler: litellmModelSyncLambda,
        });

        new CustomResource(this, 'LiteLLMModelSyncResource', {
            serviceToken: syncProvider.serviceToken,
            properties: { timestamp: new Date().toISOString() },  // Force re-run on every deployment
        });
    }
}

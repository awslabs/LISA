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

import { AttributeType, BillingMode, Table, TableEncryption } from 'aws-cdk-lib/aws-dynamodb';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';

/**
 * Properties for GuardrailsTable Construct.
 */
export type GuardrailsTableProps = {
    deploymentPrefix: string;
    removalPolicy: any;
};

/**
 * DynamoDB table for storing Bedrock Guardrails configurations per model
 */
export class GuardrailsTable extends Construct {
    public readonly table: Table;

    constructor (scope: Construct, id: string, props: GuardrailsTableProps) {
        super(scope, id);

        const { deploymentPrefix, removalPolicy } = props;

        // Create the guardrails table with composite key structure
        this.table = new Table(this, 'GuardrailsTable', {
            partitionKey: {
                name: 'guardrail_id',
                type: AttributeType.STRING
            },
            sortKey: {
                name: 'model_id',
                type: AttributeType.STRING
            },
            billingMode: BillingMode.PAY_PER_REQUEST,
            encryption: TableEncryption.AWS_MANAGED,
            removalPolicy: removalPolicy,
        });

        this.table.addGlobalSecondaryIndex({
            indexName: 'ModelIdIndex',
            partitionKey: {
                name: 'model_id',
                type: AttributeType.STRING
            },
            sortKey: {
                name: 'guardrail_id',
                type: AttributeType.STRING
            },
        });

        // Create SSM parameter for guardrails table name
        new StringParameter(this, 'GuardrailsTableNameParameter', {
            parameterName: `${deploymentPrefix}/guardrailsTableName`,
            stringValue: this.table.tableName,
        });
    }
}

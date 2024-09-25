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

// Utility functions.
import * as fs from 'fs';
import * as path from 'path';

import * as cdk from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';

import { Config, ModelConfig } from '../schema';

const IAM_DIR = path.join(__dirname, 'iam');

type JSONPolicyStatement = {
    Effect: iam.Effect;
    Action: string[];
    Resource: string | string[];
    Condition: Record<string, Record<string, string | string[]>>;
};

/**
 * Extract policy statements from JSON file.
 *
 * @param {Config} config - The application configuration.
 * @param {string} serviceName - AWS service name.
 * @returns {iam.PolicyStatement[]} - Extracted IAM policy statements.
 */
const extractPolicyStatementsFromJson = (config: Config, serviceName: string): iam.PolicyStatement[] => {
    const statementData = fs.readFileSync(path.join(IAM_DIR, `${serviceName.toLowerCase()}.json`), 'utf8');
    const statements = JSON.parse(statementData).Statement;

    statements.forEach((statement: JSONPolicyStatement) => {
        if (statement.Resource) {
            const resources = Array.isArray(statement.Resource) ? statement.Resource : [statement.Resource];
            statement.Resource = resources.map((resource: string) => {
                return resource
                    .replace(/\${AWS::AccountId}/gi, cdk.Aws.ACCOUNT_ID)
                    .replace(/\${AWS::Partition}/gi, cdk.Aws.PARTITION)
                    .replace(/\${AWS::Region}/gi, cdk.Aws.REGION);
            });
        }
    });

    return statements.map((statement: JSONPolicyStatement) => iam.PolicyStatement.fromJson(statement));
};

/**
 * Wrapper to get IAM policy statements.
 * @param {Config} config - The application configuration.
 * @param {string} serviceName - AWS service name.
 * @returns {iam.PolicyStatement[]} - Extracted IAM policy statements.
 */
export const getIamPolicyStatements = (config: Config, serviceName: string): iam.PolicyStatement[] => {
    return extractPolicyStatementsFromJson(config, serviceName);
};

/**
 * Creates a unique CDK ID using configuration data. The CDK ID is used to uniquely identify resources in the AWS
 * Cloud Development Kit (CDK). The maximum length of the CDK ID is 64 characters.
 * TODO: Make sure all IDs are valid for AWS resources like ECR, CFN, etc.
 *
 * @param {string[]} idParts - The name of the resource.
 * @throws {Error} Throws an error if the generated CDK ID is longer than 64 characters.
 * @returns {string} The generated CDK ID for the model resource.
 */
export function createCdkId (idParts: string[], maxLength: number = 64, truncationIdx: number = -1): string {
    let cdkId = idParts.join('-');
    const length = cdkId.length;

    if (length > maxLength) {
        idParts[truncationIdx] = idParts[truncationIdx].slice(0, maxLength - length);
        cdkId = idParts.join('-');
    }

    return cdkId;
}

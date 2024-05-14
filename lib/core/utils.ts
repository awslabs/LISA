/*
 Copyright (C) 2023 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
 This AWS Content is provided subject to the terms of the AWS Customer Agreement
 available at http://aws.amazon.com/agreement or other written agreement between
 Customer and either Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
*/

// Utility functions.
import * as fs from 'fs';
import * as path from 'path';

import * as cdk from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';

import { Config, ModelConfig } from '../schema';

const IAM_DIR = path.join(__dirname, 'iam');

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

  statements.forEach((statement: any) => {
    if (statement.Resource) {
      statement.Resource = [].concat(statement.Resource).map((resource: string) => {
        return resource
          .replace(/\${AWS::AccountId}/gi, cdk.Aws.ACCOUNT_ID)
          .replace(/\${AWS::Partition}/gi, cdk.Aws.PARTITION)
          .replace(/\${AWS::Region}/gi, cdk.Aws.REGION);
      });
    }
  });

  return statements.map((statement: any) => iam.PolicyStatement.fromJson(statement));
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
export function createCdkId(idParts: string[], maxLength: number = 64, truncationIdx: number = -1): string {
  let cdkId = idParts.join('-');
  const length = cdkId.length;

  if (length > maxLength) {
    idParts[truncationIdx] = idParts[truncationIdx].slice(0, maxLength - length);
    cdkId = idParts.join('-');
  }

  return cdkId;
}

/**
 * Creates a "normalized" identifier based on the provided model config. If a modelId has been
 * defined the id will be used otherwise the model name will be used. This normalized identifier
 * strips all non alpha numeric characters.
 *
 * @param {string} modelConfig model config
 * @returns {string} normalized model name for use in CDK identifiers/resource names
 */
export function getModelIdentifier(modelConfig: ModelConfig): string {
  return (modelConfig.modelId || modelConfig.modelName).replace(/[^a-zA-Z0-9]/g, '');
}

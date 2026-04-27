#!/usr/bin/env node
/**
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License").
 * You may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

/**
 * Shared integration test environment utilities.
 * Provides config loading and AWS URL fetching for integration test scripts.
 *
 * Usage:
 *   node scripts/integration-env.mjs env          # Print export statements for config
 *   node scripts/integration-env.mjs api-url     # Fetch and print API URL from SSM/CFN
 *   node scripts/integration-env.mjs alb-url     # Fetch and print ALB URL from SSM
 *   node scripts/integration-env.mjs validate    # Validate AWS credentials, exit 1 if invalid
 */

import { execSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');

function getConfigValue(pathStr) {
  try {
    const out = execSync(`node scripts/config.mjs --get ${pathStr}`, { cwd: ROOT, encoding: 'utf8' });
    return out.trim();
  } catch {
    return '';
  }
}

function getEnv() {
  const profile = getConfigValue('.profile') || '';
  const region = getConfigValue('.region') || 'us-west-2';
  const deploymentName = getConfigValue('.deploymentName') || 'prod';
  const appName = getConfigValue('.appName') || 'lisa';
  const deploymentStage = getConfigValue('.deploymentStage') || 'prod';
  const prefix = `/${deploymentStage}/${deploymentName}/${appName}`;
  return { profile, region, deploymentName, appName, deploymentStage, prefix };
}

function awsArgs(profile) {
  return profile ? `--profile ${profile}` : '';
}

function getApiUrl() {
  const { profile, region, deploymentName, appName, deploymentStage } = getEnv();
  try {
    const out = execSync(
      `aws ssm get-parameter --name "/${deploymentStage}/${deploymentName}/${appName}/LisaApiUrl" --region ${region} ${awsArgs(profile)} --query "Parameter.Value" --output text 2>/dev/null`,
      { cwd: ROOT, encoding: 'utf8' }
    );
    const url = out.trim();
    return url && url !== 'None' ? url : '';
  } catch {
    try {
      const out = execSync(
        `aws cloudformation describe-stacks --stack-name ${deploymentName}-${appName}-api-deployment-${deploymentStage} --region ${region} ${awsArgs(profile)} --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" --output text 2>/dev/null`,
        { cwd: ROOT, encoding: 'utf8' }
      );
      const url = out.trim();
      return url && url !== 'None' ? url : '';
    } catch {
      return '';
    }
  }
}

function getAlbUrl() {
  const { profile, region, deploymentName, appName, deploymentStage } = getEnv();
  try {
    const out = execSync(
      `aws ssm get-parameter --name "/${deploymentStage}/${deploymentName}/${appName}/lisaServeRestApiUri" --region ${region} ${awsArgs(profile)} --query "Parameter.Value" --output text 2>/dev/null`,
      { cwd: ROOT, encoding: 'utf8' }
    );
    const url = out.trim();
    return url && url !== 'None' ? url : '';
  } catch {
    return '';
  }
}

function validateCreds() {
  const { profile, region } = getEnv();
  try {
    execSync(`aws sts get-caller-identity --region ${region} ${awsArgs(profile)}`, {
      cwd: ROOT,
      stdio: 'pipe',
    });
    return true;
  } catch {
    return false;
  }
}

function main() {
  const cmd = process.argv[2] || 'env';
  const env = getEnv();

  switch (cmd) {
    case 'env':
      console.log(`export PROFILE="${env.profile}"`);
      console.log(`export REGION="${env.region}"`);
      console.log(`export DEPLOYMENT_NAME="${env.deploymentName}"`);
      console.log(`export APP_NAME="${env.appName}"`);
      console.log(`export DEPLOYMENT_STAGE="${env.deploymentStage}"`);
      console.log(`export PREFIX="${env.prefix}"`);
      break;
    case 'api-url':
      console.log(getApiUrl());
      break;
    case 'alb-url':
      console.log(getAlbUrl());
      break;
    case 'validate':
      if (!validateCreds()) {
        console.error('Error: No valid AWS credentials found');
        process.exit(1);
      }
      break;
    default:
      console.error(`Unknown command: ${cmd}`);
      process.exit(1);
  }
}

main();

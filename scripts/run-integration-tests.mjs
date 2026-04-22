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
 * Integration test runner. Validates credentials, deploys/tears down test resources,
 * and runs the integration test suite against a deployed LISA environment.
 *
 * Configuration is auto-discovered from config-custom.yaml + AWS SSM. No manual
 * arg passing required when config-custom.yaml is present.
 *
 * Usage:
 *   node scripts/run-integration-tests.mjs [mode]
 *
 * Modes:
 *   setup    — validate creds, deploy test resources (idempotent), wait for ready
 *   teardown — validate creds, delete all test resources
 *   run      — run pytest test/integration/ (resources must already exist)
 *   all      — setup then run (default)
 */

import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');

// ---------------------------------------------------------------------------
// Config helpers (mirrors integration-env.mjs)
// ---------------------------------------------------------------------------

function getConfigValue(pathStr) {
  try {
    const result = spawnSync('node', ['scripts/config.mjs', '--get', pathStr], { cwd: ROOT, encoding: 'utf8' });
    return result.status === 0 ? result.stdout.trim() : '';
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
  return { profile, region, deploymentName, appName, deploymentStage };
}

function ssmGetParameter(paramName, region, profile) {
  const args = ['ssm', 'get-parameter', '--name', paramName, '--region', region,
    '--query', 'Parameter.Value', '--output', 'text'];
  if (profile) args.push('--profile', profile);
  const result = spawnSync('aws', args, { cwd: ROOT, encoding: 'utf8', stdio: 'pipe' });
  if (result.status === 0 && result.stdout) {
    const url = result.stdout.trim();
    return url && url !== 'None' ? url : '';
  }
  return '';
}

function getApiUrl(env) {
  const { profile, region, deploymentName, appName, deploymentStage } = env;
  const ssmUrl = ssmGetParameter(`/${deploymentStage}/${deploymentName}/${appName}/LisaApiUrl`, region, profile);
  if (ssmUrl) return ssmUrl;
  // Fallback: CloudFormation stack output
  try {
    const stackName = `${deploymentName}-${appName}-api-deployment-${deploymentStage}`;
    const args = ['cloudformation', 'describe-stacks', '--stack-name', stackName,
      '--region', region, '--query', "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue", '--output', 'text'];
    if (profile) args.push('--profile', profile);
    const result = spawnSync('aws', args, { cwd: ROOT, encoding: 'utf8', stdio: 'pipe' });
    if (result.status === 0 && result.stdout) {
      const url = result.stdout.trim();
      return url && url !== 'None' ? url : '';
    }
  } catch { /* ignore */ }
  return '';
}

function getAlbUrl(env) {
  const { profile, region, deploymentName, appName, deploymentStage } = env;
  return ssmGetParameter(`/${deploymentStage}/${deploymentName}/${appName}/lisaServeRestApiUri`, region, profile);
}

function validateCreds(env) {
  const { profile, region } = env;
  const args = ['sts', 'get-caller-identity', '--region', region];
  if (profile) args.push('--profile', profile);
  const result = spawnSync('aws', args, { cwd: ROOT, stdio: 'pipe' });
  return result.status === 0;
}

// ---------------------------------------------------------------------------
// Subprocess helpers
// ---------------------------------------------------------------------------

function spawn(cmd, args, opts = {}) {
  const result = spawnSync(cmd, args, { stdio: 'inherit', cwd: ROOT, ...opts });
  if (result.error) {
    console.error(`Error spawning ${cmd}: ${result.error.message}`);
    process.exit(1);
  }
  return result.status ?? 1;
}

// ---------------------------------------------------------------------------
// Model preflight check
// ---------------------------------------------------------------------------

/**
 * Returns the HuggingFace model_name strings for all self-hosted models in the
 * integration deploy lists (deploy_models + deploy_embedded_models).
 * Delegates to test/python/list-integ-models.py so the source of truth stays in Python.
 */
function getSelfHostedModelNames() {
  try {
    const result = spawnSync('python', ['test/python/list-integ-models.py'], { cwd: ROOT, encoding: 'utf8' });
    if (result.status !== 0) throw new Error(result.stderr || 'non-zero exit');
    return JSON.parse(result.stdout.trim());
  } catch (e) {
    console.error(`Warning: could not read model list from integration_definitions.py: ${e.message}`);
    return [];
  }
}

/**
 * Verifies that all self-hosted integration test models have safetensors in S3.
 * Returns true if all are present, false if any are missing (and prints instructions).
 */
function checkModelsInS3(env) {
  const modelNames = getSelfHostedModelNames();
  if (modelNames.length === 0) return true;

  const modelBucket = getConfigValue('.s3BucketModels');
  if (!modelBucket) {
    console.error('Warning: s3BucketModels not set in config — skipping model S3 preflight check.');
    return true;
  }

  const { profile } = env;
  const checkScript = path.join(ROOT, 'scripts', 'check-for-models.mjs');
  const missing = [];

  console.log(`Checking ${modelNames.length} self-hosted model(s) in S3 bucket: ${modelBucket}`);
  for (const modelName of modelNames) {
    const args = [checkScript, '-m', modelName, '-s', modelBucket];
    if (profile) args.push('-p', profile);
    const result = spawnSync('node', args, { cwd: ROOT, stdio: 'inherit' });
    if (result.status !== 0) {
      missing.push(modelName);
    }
  }

  if (missing.length > 0) {
    console.error('\nThe following model(s) are missing from S3 and must be uploaded before setup:');
    for (const m of missing) {
      console.error(`\n  ${m}`);
      console.error(`  Run: ./scripts/prepare-and-upload-model.sh -m "${m}" -s ${modelBucket} -d ./models -a <HF_TOKEN>`);
    }
    console.error('\nObtain a HuggingFace token at https://huggingface.co/settings/tokens');
    console.error('The ./models directory will be created automatically as a local staging area.');
    return false;
  }

  return true;
}

// ---------------------------------------------------------------------------
// Modes
// ---------------------------------------------------------------------------

function runSetup(env, apiUrl, albUrl) {
  const { profile, region, deploymentName, appName, deploymentStage } = env;
  const pythonArgs = [
    'test/python/integration-setup-test.py',
    '--api', apiUrl,
    '--url', albUrl,
    '--deployment-name', deploymentName,
    '--deployment-stage', deploymentStage,
    '--deployment-prefix', `${deploymentName}-${appName}`,
    '--region', region,
    '--verify', 'false',
    '--wait',
  ];
  if (profile) {
    pythonArgs.push('--profile', profile);
  }
  return spawn('python', pythonArgs);
}

function runTeardown(env, apiUrl, albUrl) {
  const { profile, region, deploymentName, appName, deploymentStage } = env;
  const pythonArgs = [
    'test/python/integration-setup-test.py',
    '--api', apiUrl,
    '--url', albUrl,
    '--deployment-name', deploymentName,
    '--deployment-stage', deploymentStage,
    '--deployment-prefix', `${deploymentName}-${appName}`,
    '--region', region,
    '--verify', 'false',
    '--cleanup',
  ];
  if (profile) {
    pythonArgs.push('--profile', profile);
  }
  return spawn('python', pythonArgs);
}

function runTests() {
  return spawn('pytest', ['test/integration/', '--verbose']);
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

function main() {
  const mode = process.argv[2] || 'all';
  const validModes = ['setup', 'teardown', 'run', 'all'];
  if (!validModes.includes(mode)) {
    console.error(`Unknown mode: ${mode}. Valid modes: ${validModes.join(', ')}`);
    process.exit(1);
  }

  console.log(`\n=== LISA Integration Tests — mode: ${mode} ===\n`);

  const env = getEnv();
  console.log(`Deployment : ${env.deploymentName}-${env.appName} (${env.deploymentStage})`);
  console.log(`Region     : ${env.region}`);
  console.log(`Profile    : ${env.profile || '(default)'}`);

  // Validate AWS credentials before doing anything
  console.log('\nValidating AWS credentials...');
  if (!validateCreds(env)) {
    console.error(
      '\nError: No valid AWS credentials found.\n' +
      'Run `aws sts get-caller-identity` to diagnose, or set AWS_PROFILE / run `lisa-auth`.'
    );
    process.exit(1);
  }
  console.log('Credentials valid.\n');

  if (mode === 'run') {
    process.exit(runTests());
  }

  // Resolve URLs (needed for setup/teardown/all)
  console.log('Resolving deployment URLs from SSM...');
  const apiUrl = getApiUrl(env);
  const albUrl = getAlbUrl(env);

  if (!apiUrl) {
    console.error(
      '\nError: API URL could not be resolved from SSM or CloudFormation.\n' +
      'Ensure LISA is deployed and config-custom.yaml has the correct deploymentName/deploymentStage/region.'
    );
    process.exit(1);
  }
  if (!albUrl) {
    console.error(
      '\nError: ALB URL could not be resolved from SSM.\n' +
      'Ensure LISA is deployed and config-custom.yaml has the correct deploymentName/deploymentStage/region.'
    );
    process.exit(1);
  }

  console.log(`API URL    : ${apiUrl}`);
  console.log(`ALB URL    : ${albUrl}\n`);

  if (mode === 'setup') {
    console.log('Checking model artifacts in S3...');
    if (!checkModelsInS3(env)) process.exit(1);
    process.exit(runSetup(env, apiUrl, albUrl));
  }

  if (mode === 'teardown') {
    process.exit(runTeardown(env, apiUrl, albUrl));
  }

  if (mode === 'all') {
    console.log('Checking model artifacts in S3...');
    if (!checkModelsInS3(env)) process.exit(1);
    const setupCode = runSetup(env, apiUrl, albUrl);
    if (setupCode !== 0) {
      console.error('\nSetup failed. Skipping test run.');
      process.exit(setupCode);
    }
    console.log('\n=== Setup complete. Running integration tests... ===\n');
    process.exit(runTests());
  }
}

main();

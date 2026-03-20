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
 * Deploy orchestration - replaces make deploy.
 * Runs: install -> dockerCheck -> dockerLogin -> cleanMisc -> modelCheck -> build -> cdk deploy
 */

import { execSync, spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');

function exec(cmd, opts = {}) {
  return execSync(cmd, { cwd: ROOT, stdio: 'inherit', ...opts });
}

function getConfigValue(pathStr) {
  try {
    const out = execSync(`node scripts/config.mjs --get ${pathStr}`, { cwd: ROOT, encoding: 'utf8' });
    return out.trim();
  } catch {
    return '';
  }
}

function getConfigArray(pathStr) {
  try {
    const out = execSync(`node scripts/config.mjs --get ${pathStr}`, { cwd: ROOT, encoding: 'utf8' });
    return out.trim() ? out.trim().split('\n') : [];
  } catch {
    return [];
  }
}

async function main() {
  const headless = process.env.HEADLESS === 'true';
  const skipInstall = process.env.SKIP_INSTALL === 'true';

  const accountNumber = process.env.ACCOUNT_NUMBER || getConfigValue('.accountNumber');
  const region = process.env.REGION || getConfigValue('.region');
  const profile = process.env.PROFILE || getConfigValue('.profile');
  const partition = process.env.PARTITION || getConfigValue('.partition') || 'aws';
  const deploymentStage = process.env.DEPLOYMENT_STAGE || getConfigValue('.deploymentStage') || 'prod';
  const deploymentName = process.env.DEPLOYMENT_NAME || getConfigValue('.deploymentName') || 'prod';
  const appName = process.env.APP_NAME || getConfigValue('.appName') || 'lisa';
  const domainName = getConfigValue('.apiGatewayConfig.domainName');
  const modelBucket = getConfigValue('.s3BucketModels');

  let domain = process.env.DOMAIN;
  if (!domain) {
    if (region.includes('isob')) domain = 'sc2s.sgov.gov';
    else if (region.includes('iso')) domain = 'c2s.ic.gov';
    else domain = 'amazonaws.com';
  }

  const accountNumbersEcr = getConfigArray('.accountNumbersEcr[]');
  const ecrAccounts = [...new Set([...accountNumbersEcr, accountNumber].filter(Boolean))];
  const modelIds = getConfigArray('.ecsModels[].modelName');

  const baseUrl = domainName ? '/' : `/${deploymentStage}/`;
  const stack = process.env.STACK || `${deploymentStage}/*`;

  if (!accountNumber || !region) {
    console.error('Error: accountNumber and region must be set via env or config files.');
    process.exit(1);
  }

  if (!skipInstall) {
    console.log('Installing dependencies...');
    exec('npm run install:python');
    exec('npm install');
  }

  console.log('Checking Docker...');
  const dockerCmd = process.env.CDK_DOCKER || 'docker';
  execSync(`command -v ${dockerCmd} >/dev/null 2>&1 || { echo "Error: docker not found"; exit 1; }`, { shell: true });
  execSync(`${dockerCmd} ps >/dev/null 2>&1 || { echo "Error: Docker not running"; exit 1; }`, { shell: true });

  console.log('Logging into ECR...');
  const maxRetries = 3;
  const baseDelayMs = 2000;
  const ecrLoginCmd = 'node scripts/docker-login.mjs';
  let lastErr;
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      execSync(ecrLoginCmd, { cwd: ROOT, stdio: 'inherit', shell: true });
      lastErr = null;
      break;
    } catch (err) {
      lastErr = err;
      if (attempt < maxRetries) {
        const delayMs = baseDelayMs * Math.pow(2, attempt - 1);
        console.warn(`ECR login attempt ${attempt}/${maxRetries} failed. Retrying in ${delayMs / 1000}s...`);
        await new Promise((r) => setTimeout(r, delayMs));
      }
    }
  }
  if (lastErr) throw lastErr;

  console.log('Cleaning misc...');
  execSync('rm -f .hf_token_cache', { cwd: ROOT, stdio: 'inherit' });

  if (modelIds.length > 0 && modelBucket) {
    console.log('Checking models...');
    for (const modelId of modelIds) {
      const result = spawnSync('node', [path.join(ROOT, 'scripts', 'check-for-models.mjs'), '-m', modelId, '-s', modelBucket], {
        cwd: ROOT,
        stdio: 'inherit',
      });
      if (result.status !== 0) {
        console.log(`Model ${modelId} not found in bucket. Run prepare-and-upload-model.sh manually if needed.`);
        if (!headless) {
          const readline = (await import('node:readline')).createInterface({ input: process.stdin, output: process.stdout });
          const answer = await new Promise((resolve) => readline.question('Continue? [y/N] ', resolve));
          readline.close();
          if (answer?.toLowerCase() !== 'y') process.exit(1);
        }
      }
    }
  }

  console.log('Building...');
  exec(`BASE_URL="${baseUrl}" npm run build`);

  console.log('\n' + '='.repeat(40));
  console.log(`DEPLOYING ${stack} STACK APP INFRASTRUCTURE`);
  console.log('='.repeat(40));
  console.log(`Account Number         ${accountNumber}`);
  console.log(`Region                 ${region}`);
  console.log(`Partition              ${partition}`);
  console.log(`Domain                 ${domain}`);
  console.log(`App Name               ${appName}`);
  console.log(`Deployment Stage       ${deploymentStage}`);
  console.log(`Deployment Name        ${deploymentName}`);
  if (profile) console.log(`Deployment Profile     ${profile}`);
  console.log('='.repeat(40) + '\n');

  if (!headless) {
    const readline = (await import('node:readline')).createInterface({ input: process.stdin, output: process.stdout });
    const answer = await new Promise((resolve) => readline.question('Is the configuration correct? [y/N] ', resolve));
    readline.close();
    if (answer?.toLowerCase() !== 'y') {
      console.log('Deployment cancelled.');
      process.exit(0);
    }
  }

  const cdkArgs = [
    'deploy',
    stack,
    ...(profile ? ['--profile', profile] : []),
    ...(headless ? ['--require-approval', 'never'] : []),
    ...(process.env.EXTRA_CDK_ARGS ? process.env.EXTRA_CDK_ARGS.split(' ') : []),
  ];
  exec(`npx cdk ${cdkArgs.join(' ')}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

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
 * Destroy orchestration - replaces make destroy.
 */

import { execSync } from 'node:child_process';
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

async function main() {
  const headless = process.env.HEADLESS === 'true';

  const accountNumber = process.env.ACCOUNT_NUMBER || getConfigValue('.accountNumber');
  const region = process.env.REGION || getConfigValue('.region');
  const profile = process.env.PROFILE || getConfigValue('.profile');
  const partition = process.env.PARTITION || getConfigValue('.partition') || 'aws';
  const deploymentStage = process.env.DEPLOYMENT_STAGE || getConfigValue('.deploymentStage') || 'prod';
  const deploymentName = process.env.DEPLOYMENT_NAME || getConfigValue('.deploymentName') || 'prod';
  const appName = process.env.APP_NAME || getConfigValue('.appName') || 'lisa';

  let domain = process.env.DOMAIN;
  if (!domain) {
    if (region.includes('isob')) domain = 'sc2s.sgov.gov';
    else if (region.includes('iso')) domain = 'c2s.ic.gov';
    else domain = 'amazonaws.com';
  }

  const stack = process.env.STACK || `${deploymentStage}/*`;

  if (!accountNumber || !region) {
    console.error('Error: accountNumber and region must be set via env or config files.');
    process.exit(1);
  }

  execSync('rm -f .hf_token_cache', { cwd: ROOT, stdio: 'inherit' });

  console.log('\n' + '='.repeat(40));
  console.log(`DESTROYING ${stack} STACK APP INFRASTRUCTURE`);
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
    const { createInterface } = await import('node:readline');
    const rl = createInterface({ input: process.stdin, output: process.stdout });
    const answer = await new Promise((resolve) => rl.question('Is the configuration correct? [y/N] ', resolve));
    rl.close();
    if (answer?.toLowerCase() !== 'y') {
      console.log('Destroy cancelled.');
      process.exit(0);
    }
  }

  const cdkArgs = [
    'destroy',
    stack,
    '--force',
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

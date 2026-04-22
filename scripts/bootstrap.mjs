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
 * CDK Bootstrap - replaces make bootstrap.
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

function main() {
  const accountNumber = process.env.ACCOUNT_NUMBER || getConfigValue('.accountNumber');
  const region = process.env.REGION || getConfigValue('.region');
  const profile = process.env.PROFILE || getConfigValue('.profile');
  const partition = process.env.PARTITION || getConfigValue('.partition') || 'aws';

  if (!accountNumber || !region) {
    console.error('Error: accountNumber and region must be set via env or config files.');
    process.exit(1);
  }

  console.log(`Bootstrapping: ${accountNumber} | ${region} | ${partition}`);
  const args = [
    'bootstrap',
    `aws://${accountNumber}/${region}`,
    ...(profile ? ['--profile', profile] : []),
    '--partition',
    partition,
    '--cloudformation-execution-policies',
    `arn:${partition}:iam::aws:policy/AdministratorAccess`,
  ];
  execSync(`npx cdk ${args.join(' ')}`, { cwd: ROOT, stdio: 'inherit' });
}

main();

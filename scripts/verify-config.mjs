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
 * Verify config file - replaces scripts/verify-config.sh (removes yq dependency).
 * Checks that profile and deploymentName are empty in base config sections.
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import yaml from 'js-yaml';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');

const CONFIG_FILE = process.argv[2] || path.join(ROOT, 'config-base.yaml');

let exitCode = 0;

if (!fs.existsSync(CONFIG_FILE)) {
  console.error(`Config file not found: ${CONFIG_FILE}`);
  process.exit(1);
}

const config = yaml.load(fs.readFileSync(CONFIG_FILE, 'utf8')) || {};

const keysToCheck = ['profile', 'deploymentName'];

for (const env of Object.keys(config)) {
  if (env === 'env' || env === 'app_name' || env === '-') continue;

  const section = config[env];
  if (section == null || typeof section !== 'object') continue;

  for (const key of keysToCheck) {
    const value = section[key];
    if (value != null && value !== '') {
      console.error(`For environment=${env}, key=${key} must be empty, delete value=${value}`);
      exitCode = 1;
    }
  }
}

process.exit(exitCode);

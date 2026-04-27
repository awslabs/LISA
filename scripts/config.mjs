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
 * Config reader - replaces yq for reading config-custom.yaml and config-base.yaml.
 * Merges config (custom overrides base) and outputs values for shell scripts.
 *
 * Usage:
 *   node scripts/config.mjs --get .accountNumber
 *   node scripts/config.mjs --get .ecsModels[].modelName
 *   node scripts/config.mjs --get .accountNumbersEcr[]
 *   node scripts/config.mjs --json  # output full merged config as JSON
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import yaml from 'js-yaml';
import _ from 'lodash';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const BASE_CONFIG = path.join(ROOT, 'config-base.yaml');
const CUSTOM_CONFIG = path.join(ROOT, 'config-custom.yaml');

function loadConfig() {
  const base = yaml.load(fs.readFileSync(BASE_CONFIG, 'utf8')) || {};
  let custom = {};
  if (fs.existsSync(CUSTOM_CONFIG)) {
    custom = yaml.load(fs.readFileSync(CUSTOM_CONFIG, 'utf8')) || {};
  }
  return _.merge({}, base, custom);
}

function getAtPath(obj, pathStr) {
  const cleanPath = pathStr.replace(/^\./, '');
  const val = _.get(obj, cleanPath);
  return val;
}

function getArrayValues(obj, pathStr) {
  // Handle paths like .ecsModels[].modelName or .accountNumbersEcr[]
  const match = pathStr.match(/^\.(.+)\[\](\.\S+)?$/);
  if (!match) {
    const val = getAtPath(obj, pathStr);
    return val != null ? [val] : [];
  }
  const arrayPath = match[1];
  const subPath = match[2] ? match[2].replace(/^\./, '') : null;
  const arr = _.get(obj, arrayPath);
  if (!Array.isArray(arr)) return [];
  if (subPath) {
    return arr
      .map((item) => (item != null && typeof item === 'object' ? _.get(item, subPath) : item))
      .filter((v) => v != null && v !== '');
  }
  return arr.filter((v) => v != null && v !== '');
}

/**
 * Determine which config object should be used for a given lookup path.
 *
 * If config.env is set to an environment name (e.g. "dev") and the lookup path is
 * not explicitly env-qualified, lookups are resolved against a view where the
 * selected env block (config[env]) is merged over the root config.
 *
 * Explicit env-qualified paths like ".dev.profile" or ".env" bypass this logic
 * and use the raw merged config object.
 */
function resolveLookupConfig(config, pathStr) {
  if (!config || typeof config !== 'object') {
    return config;
  }

  const env = config.env;
  if (!env || typeof env !== 'string') {
    return config;
  }

  if (!pathStr || typeof pathStr !== 'string' || !pathStr.startsWith('.')) {
    return config;
  }

  const cleanPath = pathStr.replace(/^\./, '');

  // Always resolve ".env" and ".env.*" against the root config
  if (cleanPath === 'env' || cleanPath.startsWith('env.')) {
    return config;
  }

  // If the path is explicitly qualified with the active env (e.g. ".dev.*"),
  // treat it as an explicit reference and bypass env overlay.
  if (cleanPath === env || cleanPath.startsWith(env + '.')) {
    return config;
  }

  const envBlock = config[env];
  if (!envBlock || typeof envBlock !== 'object') {
    return config;
  }

  // Merge root config with the selected env block for lookups.
  return _.merge({}, config, envBlock);
}

function main() {
  const config = loadConfig();

  const args = process.argv.slice(2);
  if (args[0] === '--json') {
    console.log(JSON.stringify(config, null, 0));
    return;
  }

  if (args[0] === '--get' && args[1]) {
    const pathStr = args[1];
    const lookupConfig = resolveLookupConfig(config, pathStr);
    if (/\[\]/.test(pathStr)) {
      const values = getArrayValues(lookupConfig, pathStr);
      values.forEach((v) => console.log(String(v)));
    } else {
      const val = getAtPath(lookupConfig, pathStr);
      if (val != null && val !== '') {
        console.log(String(val));
      }
    }
    return;
  }

  console.error('Usage: node scripts/config.mjs --get <path> | --json');
  process.exit(1);
}

main();

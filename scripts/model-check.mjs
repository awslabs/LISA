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
 * Model check - replaces make modelCheck.
 * Verifies models are uploaded to S3.
 */

import { execSync, spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createInterface } from 'node:readline';

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

function getConfigArray(pathStr) {
  try {
    const out = execSync(`node scripts/config.mjs --get ${pathStr}`, { cwd: ROOT, encoding: 'utf8' });
    return out.trim() ? out.trim().split('\n') : [];
  } catch {
    return [];
  }
}

async function main() {
  const modelBucket = process.env.MODEL_BUCKET || getConfigValue('.s3BucketModels');
  const modelIds = getConfigArray('.ecsModels[].modelName');

  if (modelIds.length === 0 || !modelBucket) return;

  const checkScript = path.join(ROOT, 'scripts', 'check-for-models.mjs');
  const localModelDir = path.join(ROOT, 'models');

  for (const modelId of modelIds) {
    const result = spawnSync('node', [checkScript, '-m', modelId, '-s', modelBucket], {
      cwd: ROOT,
      stdio: 'inherit',
    });
    if (result.status !== 0) {
      console.log(`\nPreparing and uploading model artifacts for: ${modelId}`);
      const rl = createInterface({ input: process.stdin, output: process.stdout });
      const answer = await new Promise((resolve) => rl.question('Would you like to continue? [y/N] ', resolve));
      rl.close();
      if (answer?.toLowerCase() !== 'y') process.exit(1);
      // Run prepare-and-upload-model.sh - would need HuggingFace token from user
      console.error('Run: ./scripts/prepare-and-upload-model.sh -m', modelId, '-s', modelBucket, '-a <token> -d', localModelDir);
      process.exit(1);
    }
  }
}

main();

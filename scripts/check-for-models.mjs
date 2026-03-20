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
 * Check if model safetensors exist in S3 bucket.
 * Replaces scripts/check-for-models.sh.
 *
 * Usage: node scripts/check-for-models.mjs -m <model-id> -s <s3-bucket>
 * Exit 0 if safetensors found, 1 otherwise.
 */

import { execSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');

function parseArgs() {
  const args = process.argv.slice(2);
  let modelId = '';
  let s3Bucket = '';
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '-m' || args[i] === '--model-id') {
      modelId = args[++i] || '';
    } else if (args[i] === '-s' || args[i] === '--s3-bucket') {
      s3Bucket = args[++i] || '';
    } else if (args[i] === '-h' || args[i] === '--help') {
      console.error(`Usage: node scripts/check-for-models.mjs -m <model-id> -s <s3-bucket>`);
      process.exit(0);
    }
  }
  return { modelId, s3Bucket };
}

function main() {
  const { modelId, s3Bucket } = parseArgs();
  if (!modelId || !s3Bucket) {
    console.error('Error: -m (model-id) and -s (s3-bucket) are required');
    process.exit(1);
  }

  try {
    const out = execSync(
      `aws s3api list-objects-v2 --bucket ${s3Bucket} --prefix "${modelId}/" --output json`,
      { cwd: ROOT, encoding: 'utf8', maxBuffer: 10 * 1024 * 1024 }
    );
    const data = JSON.parse(out);
    const contents = data.Contents || [];
    const num = contents.filter((o) => o.Key && o.Key.includes('safetensor')).length;
    if (num < 1) {
      console.error(`No safetensors found for model: ${modelId} in bucket: ${s3Bucket}.`);
      process.exit(1);
    }
    console.log(`Found ${num} safetensors for model: ${modelId} in bucket: ${s3Bucket}.`);
  } catch {
    console.error(`No safetensors found for model: ${modelId} in bucket: ${s3Bucket}.`);
    process.exit(1);
  }
}

main();

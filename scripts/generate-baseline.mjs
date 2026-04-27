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
 * Generate CDK baseline templates from a release tag.
 * Replaces scripts/generate-baseline.sh.
 *
 * Usage: node scripts/generate-baseline.mjs [release-tag]
 *        npm run generate-baseline -- v5.3.0
 */

import { execSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const BASELINE_DIR = path.join(ROOT, 'test/cdk/stacks/__baselines__');

function run(cmd, opts = {}) {
  execSync(cmd, { cwd: ROOT, stdio: 'inherit', shell: true, ...opts });
}

function main() {
  const releaseTag = process.argv[2] || execSync('git describe --tags --abbrev=0', { cwd: ROOT, encoding: 'utf8' }).trim();
  console.log(`Generating baselines from release: ${releaseTag}`);

  try {
    run('git stash push -m "Temporary stash for baseline generation"');
    run(`git checkout ${releaseTag}`);
    run('npm ci');
    run('npm run build');

    fs.rmSync(BASELINE_DIR, { recursive: true, force: true });
    fs.mkdirSync(BASELINE_DIR, { recursive: true });

    run('npm test -- test/cdk/stacks/snapshot.test.ts --testNamePattern="is compatible with baseline"');
  } finally {
    run('git checkout - 2>/dev/null || true');
    run('git stash pop || true');
  }

  console.log('Baselines generated in', BASELINE_DIR);
}

main();

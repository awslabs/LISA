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
 * Assemble dist directory from workspace build outputs.
 * Replaces scripts/copy-deps.sh (copy_dist only; setup_python_dist was dead).
 */

import { execSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');

function run(cmd) {
  execSync(cmd, { cwd: ROOT, stdio: 'inherit', shell: true });
}

function main() {
  fs.mkdirSync(path.join(ROOT, 'dist'), { recursive: true });

  run('mkdir -p dist/ecs_model_deployer && rsync -av ecs_model_deployer/dist dist/ecs_model_deployer/ && cp ecs_model_deployer/Dockerfile dist/ecs_model_deployer/');
  run('mkdir -p dist/vector_store_deployer && rsync -av vector_store_deployer/dist dist/vector_store_deployer/ && cp vector_store_deployer/Dockerfile dist/vector_store_deployer/');
  run('mkdir -p dist/lisa-web && rsync -av lib/user-interface/react/dist/ dist/lisa-web');
  run('mkdir -p dist/docs && rsync -av lib/docs/dist/ dist/docs');
  run('cp VERSION dist/');

  console.log('Dist assembly complete.');
}

main();

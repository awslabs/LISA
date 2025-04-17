/**
  Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

  Licensed under the Apache License, Version 2.0 (the "License").
  You may not use this file except in compliance with the License.
  You may obtain a copy of the License at

      http://www.apache.org/licenses/LICENSE-2.0

  Unless required by applicable law or agreed to in writing, software
  distributed under the License is distributed on an "AS IS" BASIS,
  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
  See the License for the specific language governing permissions and
  limitations under the License.
*/

const esbuild = require('esbuild');

esbuild.build({
    entryPoints: ['src/index.ts', 'src/lib/index.ts'],
    bundle: true,
    minify: true,
    sourcemap: true,
    platform: 'node',
    target: 'node20',
    outdir: 'dist',
    // Exclude these from esbuild. We will add them explicily during with npm pack:prod
    external: [
    // '@cdklabs/cdk-enterprise-iac', // Include this with ESbuild because it is too big to include via node_modules
        'aws-cdk',
        'aws-cdk-lib',
        '@aws-sdk/client-iam',
        'zod'
    ],
    format: 'cjs',
}).catch(() => process.exit(1));

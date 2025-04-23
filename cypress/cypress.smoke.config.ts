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

import { defineConfig } from 'cypress';
import path from 'path';

const PROJECT_ROOT = path.resolve(__dirname);

export default defineConfig({
    video: true,                        // turn on video recording
    videoCompression: true,
    videosFolder: `${PROJECT_ROOT}/videos/smoke`,     // where to save .mp4 files
    screenshotOnRunFailure: true,       // auto‑snap on any test failure
    screenshotsFolder: `${PROJECT_ROOT}/screenshots/smoke`,
    trashAssetsBeforeRuns: true,        // wipe out old videos/screenshots

    e2e: {
        specPattern: `${PROJECT_ROOT}/src/smoke/specs/**/*.smoke.spec.ts`,
        supportFile: `${PROJECT_ROOT}/src/smoke/support/index.ts`,
        experimentalStudio: true,
        fixturesFolder: `${PROJECT_ROOT}/src/smoke/fixtures`,
        setupNodeEvents () {
        },
        baseUrl: 'https://5bma74uv9c.execute-api.us-east-1.amazonaws.com/dev',
    },
});

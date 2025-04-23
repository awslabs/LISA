/// <reference types="node" />

import { defineConfig } from 'cypress';
import path from 'path';

const PROJECT_ROOT = path.resolve(__dirname);

export default defineConfig({
    video: true,                        // turn on video recording
    videoCompression: true,
    videosFolder: `${PROJECT_ROOT}/videos/e2e`,     // where to save .mp4 files
    screenshotOnRunFailure: true,       // auto‑snap on any test failure
    screenshotsFolder: `${PROJECT_ROOT}/screenshots/e2e`,
    trashAssetsBeforeRuns: true,        // wipe out old videos/screenshots
    e2e: {
        specPattern: `${PROJECT_ROOT}/src/e2e/specs/**/*.e2e.spec.ts`,
        supportFile: `${PROJECT_ROOT}/src/e2e/support/index.ts`,
        experimentalStudio: true,
        fixturesFolder: `${PROJECT_ROOT}/src/e2e/fixtures`,
        setupNodeEvents () {
        },
        baseUrl: 'https://5bma74uv9c.execute-api.us-east-1.amazonaws.com/dev',
        env: {
            TEST_ACCOUNT_PASSWORD: process.env.TEST_ACCOUNT_PASSWORD,
        },
    },
});

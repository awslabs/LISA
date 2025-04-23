/// <reference types="node" />

import { defineConfig } from 'cypress';

export default defineConfig({
    video: true,                        // turn on video recording
    videoCompression: true,
    videosFolder: 'videos/e2e',     // where to save .mp4 files
    screenshotOnRunFailure: true,       // auto‑snap on any test failure
    screenshotsFolder: 'screenshots/e2e',
    trashAssetsBeforeRuns: true,        // wipe out old videos/screenshots
    e2e: {
        specPattern: 'src/e2e/specs/**/*.e2e.spec.ts',
        supportFile: 'src/e2e/support/index.ts',
        experimentalStudio: true,
        fixturesFolder: 'src/e2e/fixtures',
        setupNodeEvents () {
        },
        baseUrl: 'https://5bma74uv9c.execute-api.us-east-1.amazonaws.com/dev',
        env: {
            TEST_ACCOUNT_PASSWORD: process.env.TEST_ACCOUNT_PASSWORD,
        },
    },
});

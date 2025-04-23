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

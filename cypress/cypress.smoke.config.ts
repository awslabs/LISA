import { defineConfig } from 'cypress';

export default defineConfig({
    video: true,                        // turn on video recording
    videosFolder: 'videos/smoke',     // where to save .mp4 files
    screenshotOnRunFailure: true,       // auto‑snap on any test failure
    screenshotsFolder: 'screenshots/smoke',
    trashAssetsBeforeRuns: true,        // wipe out old videos/screenshots

    e2e: {
        specPattern: 'src/smoke/specs/**/*.smoke.spec.ts',
        supportFile: 'src/smoke/support/index.ts',
        experimentalStudio: true,
        fixturesFolder: 'src/smoke/fixtures',
        setupNodeEvents () {
        },
        baseUrl: 'https://5bma74uv9c.execute-api.us-east-1.amazonaws.com/dev',
    },
});

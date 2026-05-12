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

/**
 * Post-build smoke test for the React bundle.
 *
 * Why this exists:
 *   Aggressive `manualChunks` configuration in vite.config.ts can introduce
 *   cross-chunk circular dependencies that Rollup accepts silently at build
 *   time but that surface at runtime as
 *       "Cannot access lexical declaration 'X' before initialization"
 *   the moment the bundle evaluates in a real browser. Type checks and unit
 *   tests cannot catch that class of bug; only executing the built bundle
 *   can. This script does exactly that: it serves `dist/` via `vite preview`,
 *   opens the app in a headless Chromium, and fails CI on any uncaught page
 *   error or asset load failure.
 *
 * Requirements:
 *   - `npm run build` has produced `dist/index.html`
 *   - `playwright` is installed (devDependency) and its Chromium binary has
 *     been downloaded via `npx playwright install chromium`
 *
 * Env overrides:
 *   SMOKE_PREVIEW_PORT   Port for vite preview (default: 4173)
 *   SMOKE_PREVIEW_HOST   Bind host (default: 127.0.0.1)
 *   SMOKE_BASE_PATH      Path to navigate to (default: Vite `base`, or "/")
 *   SMOKE_SETTLE_MS      Time after `load` to keep watching for errors
 *                        (default: 5000)
 */

import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { setTimeout as delay } from 'node:timers/promises';

const scriptDir = dirname(fileURLToPath(import.meta.url));
const projectDir = resolve(scriptDir, '..');
const distIndex = resolve(projectDir, 'dist', 'index.html');

const PREVIEW_PORT = Number(process.env.SMOKE_PREVIEW_PORT ?? 4173);
const PREVIEW_HOST = process.env.SMOKE_PREVIEW_HOST ?? '127.0.0.1';
const BASE_PATH = (process.env.SMOKE_BASE_PATH ?? process.env.BASE_URL ?? '/').replace(/\/?$/, '/');
const URL = `http://${PREVIEW_HOST}:${PREVIEW_PORT}${BASE_PATH.startsWith('/') ? BASE_PATH : `/${BASE_PATH}`}`;

const STARTUP_TIMEOUT_MS = 30_000;
const SETTLE_MS = Number(process.env.SMOKE_SETTLE_MS ?? 5_000);

if (!existsSync(distIndex)) {
    console.error(`Smoke test aborted: ${distIndex} does not exist. Run "npm run build" first.`);
    process.exit(1);
}

let chromium;
try {
    ({ chromium } = await import('playwright'));
} catch (err) {
    console.error('Smoke test aborted: the "playwright" package is not installed.');
    console.error('Install with: npm install --save-dev playwright && npx playwright install chromium');
    console.error('Original error:', err?.message ?? err);
    process.exit(1);
}

const waitForServer = async () => {
    const deadline = Date.now() + STARTUP_TIMEOUT_MS;
    while (Date.now() < deadline) {
        try {
            const response = await fetch(URL, { method: 'GET' });
            if (response.ok || response.status === 304) return;
        } catch {
            /* server not up yet */
        }
        await delay(250);
    }
    throw new Error(`Preview server at ${URL} did not respond within ${STARTUP_TIMEOUT_MS}ms.`);
};

let previewProcess;
let browser;
let exitCode = 0;

const teardown = async () => {
    if (browser) {
        await browser.close().catch(() => { /* ignore */ });
    }
    if (previewProcess && previewProcess.exitCode === null) {
        previewProcess.kill('SIGTERM');
        await new Promise((resolveOnce) => {
            const onExit = () => resolveOnce();
            previewProcess.once('exit', onExit);
            // Last-resort timeout so we never hang forever.
            setTimeout(() => {
                previewProcess.kill('SIGKILL');
                resolveOnce();
            }, 3_000).unref();
        });
    }
};

process.on('SIGINT', async () => { await teardown(); process.exit(130); });
process.on('SIGTERM', async () => { await teardown(); process.exit(143); });

try {
    previewProcess = spawn(
        'npx',
        [
            'vite',
            'preview',
            '--strictPort',
            '--port', String(PREVIEW_PORT),
            '--host', PREVIEW_HOST,
        ],
        {
            stdio: ['ignore', 'inherit', 'inherit'],
            cwd: projectDir,
            shell: false,
        },
    );

    previewProcess.on('exit', (code) => {
        if (code !== null && code !== 0 && exitCode === 0) {
            console.error(`vite preview exited unexpectedly with code ${code}`);
            exitCode = code;
        }
    });

    await waitForServer();

    browser = await chromium.launch();
    const context = await browser.newContext();
    const page = await context.newPage();

    const pageErrors = [];
    const failedAssets = [];

    // Uncaught exceptions in the page (where TDZ / lexical-declaration errors
    // from cross-chunk cycles show up).
    page.on('pageerror', (error) => {
        pageErrors.push(error);
    });

    // Missing chunks, broken asset URLs, etc.
    page.on('requestfailed', (request) => {
        const url = request.url();
        if (/\.(m?js|css)(\?|$)/i.test(url)) {
            failedAssets.push({ url, failure: request.failure()?.errorText ?? 'unknown' });
        }
    });

    console.log(`Smoke test: loading ${URL}`);
    await page.goto(URL, { waitUntil: 'load', timeout: STARTUP_TIMEOUT_MS });
    // Keep listening for a short window after `load` so we catch errors thrown
    // from late-evaluated module bodies or idle-time prefetch.
    await delay(SETTLE_MS);

    const problems = [];
    if (pageErrors.length > 0) {
        problems.push(
            `Uncaught page errors (${pageErrors.length}):\n` +
            pageErrors.map((err, idx) => `  [${idx + 1}] ${err.message}`).join('\n'),
        );
    }
    if (failedAssets.length > 0) {
        problems.push(
            `Failed JS/CSS requests (${failedAssets.length}):\n` +
            failedAssets.map((a, idx) => `  [${idx + 1}] ${a.url}  (${a.failure})`).join('\n'),
        );
    }

    if (problems.length > 0) {
        console.error('\nSmoke test FAILED:\n' + problems.join('\n\n'));
        exitCode = 1;
    } else {
        console.log(`Smoke test passed: ${URL} evaluated cleanly.`);
    }
} catch (error) {
    console.error('Smoke test crashed:', error?.stack ?? error);
    exitCode = 1;
} finally {
    await teardown();
    process.exit(exitCode);
}

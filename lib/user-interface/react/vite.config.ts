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

import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';
import { resolve } from 'node:path';
import tailwindcss from '@tailwindcss/vite';

const normalizedBaseUrl = (() => {
    const configuredBase = process.env.BASE_URL?.trim();

    if (!configuredBase) {
        return '/';
    }

    const withLeadingSlash = configuredBase.startsWith('/') ? configuredBase : `/${configuredBase}`;
    return withLeadingSlash.endsWith('/') ? withLeadingSlash : `${withLeadingSlash}/`;
})();

/**
 * Assign an npm package to a long-lived, cacheable vendor chunk.
 *
 * Rationale: by default Rollup/Vite inlines third-party code into whichever
 * route chunk first imports it, which causes duplication across routes and
 * means every app release invalidates the entire bundle in the browser cache.
 * Pinning large, self-contained libraries to named vendor chunks makes each
 * navigation download only the route's own code once the vendor chunks are
 * cached.
 *
 * Caveat: aggressive `manualChunks` can introduce runtime
 * "Cannot access lexical declaration 'X' before initialization" errors when
 * two chunks import from each other in a cycle (Rollup can't re-order
 * execution across chunk boundaries the way it does within one chunk). To
 * avoid that class of bug we deliberately only split libraries that are
 * leaves in the import graph — no app code ends up inside them, and they do
 * not import each other. React, Redux, react-markdown, @modelcontextprotocol,
 * langchain, and oidc-client are intentionally NOT split: they are either
 * tightly intertwined with app code or with each other, and splitting them
 * produced cross-chunk cycles. Leave those to Rollup's automatic splitting,
 * which is cycle-safe.
 */
const vendorChunkFor = (id: string): string | undefined => {
    if (!id.includes('node_modules')) return undefined;

    if (id.includes('/@cloudscape-design/')) {
        return 'vendor-cloudscape';
    }
    if (id.includes('/@fortawesome/')) {
        return 'vendor-fontawesome';
    }
    if (id.includes('/react-syntax-highlighter/') || id.includes('/refractor/') || id.includes('/prismjs/') || id.includes('/highlight.js/')) {
        return 'vendor-syntax-highlighter';
    }
    if (id.includes('/pdfjs-dist/')) {
        return 'vendor-pdfjs';
    }
    if (id.includes('/mermaid/') || id.includes('/@mermaid-js/') || id.includes('/d3-') || id.includes('/cytoscape')) {
        return 'vendor-mermaid';
    }
    if (id.includes('/ace-builds/')) {
        return 'vendor-ace';
    }
    if (id.includes('/katex/')) {
        return 'vendor-katex';
    }
    if (id.includes('/jszip/')) {
        return 'vendor-jszip';
    }
    return undefined;
};

// https://vitejs.dev/config/
export default defineConfig({
    plugins: [react(), tailwindcss()] as any,
    server: {
        port: 3000,
    },
    build: {
        // We intentionally produce a few large, long-lived vendor chunks (Cloudscape, Mermaid, PDF.js, etc).
        // Keep the warning threshold above the known largest vendor chunk to reduce noise while still
        // catching accidental monolithic app chunks.
        chunkSizeWarningLimit: 3000,
        rolldownOptions: {
            output: {
                manualChunks: vendorChunkFor,
            },
        },
    },
    define: {
        global: 'globalThis',
    },
    resolve: {
        alias: {
            '@': resolve(__dirname, 'src'),
            '#root': resolve(__dirname, '..', '..', '..'),
        },
        dedupe: ['react', 'react-dom'],
    },
    optimizeDeps: {
        include: [
            'react',
            'react-dom',
            '@cloudscape-design/components',
            '@cloudscape-design/collection-hooks',
            '@cloudscape-design/chat-components',
            '@cloudscape-design/global-styles',
        ],
    },
    base: normalizedBaseUrl,
});

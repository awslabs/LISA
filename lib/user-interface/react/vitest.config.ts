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

import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react-swc';
import { resolve } from 'node:path';

export default defineConfig({
    plugins: [react()] as any,
    test: {
        globals: true,
        environment: 'jsdom',
        setupFiles: './src/test/setup.ts',
        coverage: {
            provider: 'istanbul',
            reporter: ['text', 'json', 'html', 'lcov', 'text-summary'],
            reportsDirectory: './coverage',
            exclude: [
                'node_modules/',
                'src/test/',
                '**/*.test.{ts,tsx}',
                '**/*.config.{ts,js}',
                'src/components/types.ts',
                'src/config/',
                'dist/',
                'build/',
                'scripts/',
            ],
            include: [
                'src/**/*.{ts,tsx}',
            ],
        },
    },
    resolve: {
        alias: {
            '@': resolve(__dirname, 'src'),
            '#root': resolve(__dirname, '..', '..', '..'),
        },
    },
});

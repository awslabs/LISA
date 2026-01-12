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

import js from '@eslint/js';
import tseslint from '@typescript-eslint/eslint-plugin';
import tsparser from '@typescript-eslint/parser';
import stylistic from '@stylistic/eslint-plugin';
import reactHooks from 'eslint-plugin-react-hooks';
import importPlugin from 'eslint-plugin-import';
import globals from 'globals';


const tsRules = {
    ...tseslint.configs.recommended.rules,
    'eqeqeq': ['error', 'smart'],
    // Stylistic rules
    '@stylistic/indent': 'error',
    '@stylistic/quotes': ['error', 'single'],
    '@stylistic/arrow-parens': 'error',
    '@stylistic/arrow-spacing': 'error',
    '@stylistic/brace-style': 'error',
    '@stylistic/computed-property-spacing': ['error', 'never'],
    '@stylistic/jsx-quotes': ['error', 'prefer-single'],
    '@stylistic/keyword-spacing': ['error', { 'before': true }],
    '@stylistic/semi': 'error',
    '@stylistic/space-before-function-paren': 'error',
    '@stylistic/space-infix-ops': 'error',
    '@stylistic/space-unary-ops': 'error',
    // TypeScript overrides
    '@typescript-eslint/ban-types': 'off',
    '@typescript-eslint/consistent-type-definitions': ['error', 'type'],
    '@typescript-eslint/no-non-null-assertion': 'off',
    '@typescript-eslint/no-explicit-any': 'off'
}

const reactRules = {
    ...reactHooks.configs.recommended.rules,
    // React hooks - downgrade new rules to warnings
    'react-hooks/set-state-in-effect': 'warn',
    'react-hooks/immutability': 'warn',
    'react-hooks/purity': 'warn',
    'react-hooks/use-memo': 'warn',
}

export default [
    js.configs.recommended,
    // React files - browser and jest globals only
    {
        files: ['lib/user-interface/react/**/*.ts', 'lib/user-interface/react/**/*.tsx'],
        languageOptions: {
            parser: tsparser,
            parserOptions: {
                ecmaVersion: 12,
                sourceType: 'module',
            },
            globals: {
                ...globals.browser,
                ...globals.jest,
                React: 'readonly',
            },
        },
        plugins: {
            '@typescript-eslint': tseslint,
            '@stylistic': stylistic,
            'react-hooks': reactHooks,
            'import': importPlugin,
        },
        rules: {
            ...tsRules,
            ...reactRules
        },
    },
    // All Cypress files - mocha, browser, jest, and cypress globals
    {
        files: ['cypress/**/*.ts', 'cypress/**/*.js'],
        languageOptions: {
            parser: tsparser,
            parserOptions: {
                ecmaVersion: 12,
                sourceType: 'module',
            },
            globals: {
                ...globals.mocha,
                ...globals.browser,
                ...globals.jest, // For expect and other test utilities
                // Cypress globals
                cy: 'readonly',
                Cypress: 'readonly',
            },
        },
        plugins: {
            '@typescript-eslint': tseslint,
            '@stylistic': stylistic,
            'import': importPlugin,
        },
        rules: tsRules,
    },
    // All other TypeScript files - node and jest globals
    {
        files: ['**/*.ts', '**/*.tsx'],
        ignores: [
            'lib/user-interface/react/**/*',
            'cypress/**/*'
        ],
        languageOptions: {
            parser: tsparser,
            parserOptions: {
                ecmaVersion: 12,
                sourceType: 'module',
            },
            globals: {
                ...globals.node,
                ...globals.jest,
            },
        },
        plugins: {
            '@typescript-eslint': tseslint,
            '@stylistic': stylistic,
            'import': importPlugin,
        },
        rules: tsRules,
    },
    {
        files: ['**/*.js', '**/*.mjs'],
        languageOptions: {
            globals: {
                ...globals.node,
            },
        },
    },
    {
        ignores: [
            '**/*.bundle.js',
            '**/*.d.ts',
            '**/*.min.js',
            '**/{build,coverage,dist,venv,.venv}/**',
            '**/*.config.ts',
            'cypress/dist/**',
            'ecs_model_deployer/dist/**',
            'htmlcov/**',
            'lib/docs/.vitepress/cache/**',
            'lib/docs/dist/**',
            'lib/user-interface/react/{dist,public}/**',
            'node_modules/**',
            'pnpm-lock.yaml',
            'pnpm-workspace.yaml',
            'vector_store_deployer/dist/**',
        ]
    }
];

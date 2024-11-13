import { fixupConfigRules, fixupPluginRules } from '@eslint/compat';
import stylistic from '@stylistic/eslint-plugin';
import typescriptEslint from '@typescript-eslint/eslint-plugin';
import globals from 'globals';
import tsParser from '@typescript-eslint/parser';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import js from '@eslint/js';
import { FlatCompat } from '@eslint/eslintrc';

import eslintPluginPrettierRecommended from 'eslint-plugin-prettier/recommended';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const compat = new FlatCompat({
    baseDirectory: __dirname,
    recommendedConfig: js.configs.recommended,
    allConfig: js.configs.all
});

export default [
    {
        ignores: ['**/dist', '**/node_modules', '**/package-lock.json']
    },
    eslintPluginPrettierRecommended,
    ...fixupConfigRules(
        compat.extends(
            'eslint:recommended',
            'plugin:@typescript-eslint/recommended',
            'plugin:react-hooks/recommended',
            'prettier'
        )
    ),
    {
        plugins: {
            '@stylistic': stylistic,
            '@typescript-eslint': fixupPluginRules(typescriptEslint)
        },

        languageOptions: {
            globals: {
                ...globals.browser
            },

            parser: tsParser,
            ecmaVersion: 12,
            sourceType: 'module'
        },

        rules: {
            eqeqeq: ['error', 'smart'],
            '@stylistic/indent': 'off', // Defer to prettier
            '@stylistic/quotes': 'off', // Defer to prettier
            '@stylistic/arrow-parens': 'error',
            '@stylistic/arrow-spacing': 'error',
            '@stylistic/brace-style': 'error',
            '@stylistic/computed-property-spacing': ['error', 'never'],
            '@stylistic/jsx-quotes': ['error', 'prefer-double'],
            '@stylistic/keyword-spacing': [
                'error',
                {
                    before: true
                }
            ],

            '@stylistic/semi': 'error',
            '@stylistic/space-infix-ops': 'error',
            '@stylistic/space-unary-ops': 'error',
            '@typescript-eslint/no-unused-vars': 'error',
            '@typescript-eslint/ban-types': 'off',
            '@typescript-eslint/consistent-type-definitions': ['error', 'type'],
            '@typescript-eslint/no-non-null-assertion': 'off',
            '@typescript-eslint/no-explicit-any': 'off',
            'react-hooks/rules-of-hooks': 'error',
            'react-hooks/exhaustive-deps': 'error',
            'react/prop-types': 'off'
        }
    }
];

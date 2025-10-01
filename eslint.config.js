import js from '@eslint/js';
import tseslint from '@typescript-eslint/eslint-plugin';
import tsparser from '@typescript-eslint/parser';
import stylistic from '@stylistic/eslint-plugin';
import reactHooks from 'eslint-plugin-react-hooks';
import importPlugin from 'eslint-plugin-import';

export default [
  js.configs.recommended,
  {
    files: ['**/*.ts', '**/*.tsx'],
    languageOptions: {
      parser: tsparser,
      parserOptions: {
        ecmaVersion: 12,
        sourceType: 'module',
      },
      globals: {
        browser: true,
        es2021: true,
        node: true,
        // Browser globals
        window: 'readonly',
        document: 'readonly',
        console: 'readonly',
        fetch: 'readonly',
        Response: 'readonly',
        setTimeout: 'readonly',
        clearTimeout: 'readonly',
        setInterval: 'readonly',
        clearInterval: 'readonly',
        navigator: 'readonly',
        localStorage: 'readonly',
        sessionStorage: 'readonly',
        performance: 'readonly',
        URL: 'readonly',
        URLSearchParams: 'readonly',
        FormData: 'readonly',
        Blob: 'readonly',
        File: 'readonly',
        FileReader: 'readonly',
        ClipboardItem: 'readonly',
        HTMLInputElement: 'readonly',
        HTMLDivElement: 'readonly',
        SVGElement: 'readonly',
        XMLSerializer: 'readonly',
        HTMLElement: 'readonly',
        Image: 'readonly',
        atob: 'readonly',
        btoa: 'readonly',
        React: 'readonly',
        // Node.js globals
        process: 'readonly',
        __dirname: 'readonly',
        __filename: 'readonly',
        require: 'readonly',
        module: 'readonly',
        exports: 'readonly',
        Buffer: 'readonly',
        // Test globals
        describe: 'readonly',
        it: 'readonly',
        test: 'readonly',
        expect: 'readonly',
        beforeEach: 'readonly',
        afterEach: 'readonly',
        beforeAll: 'readonly',
        afterAll: 'readonly',
        // Cypress globals
        cy: 'readonly',
        Cypress: 'readonly',
      },
    },
    plugins: {
      '@typescript-eslint': tseslint,
      '@stylistic': stylistic,
      'react-hooks': reactHooks,
      'import': importPlugin,
    },
    rules: {
      ...tseslint.configs.recommended.rules,
      ...reactHooks.configs.recommended.rules,
      'eqeqeq': ['error', 'smart'],
      '@stylistic/indent': 'error',
      '@stylistic/quotes': ['error', 'single'],
      '@stylistic/arrow-parens': 'error',
      '@stylistic/arrow-spacing': 'error',
      '@stylistic/brace-style': 'error',
      '@stylistic/computed-property-spacing': ['error', 'never'],
      '@stylistic/jsx-quotes': ['error', 'prefer-single'],
      '@stylistic/keyword-spacing': [
        'error',
        {
          'before': true
        }
      ],
      '@stylistic/semi': 'error',
      '@stylistic/space-before-function-paren': 'error',
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
    },
  },
  {
    files: ['**/*.js', '**/*.mjs'],
    languageOptions: {
      globals: {
        node: true,
        process: 'readonly',
        __dirname: 'readonly',
        __filename: 'readonly',
        require: 'readonly',
        module: 'readonly',
        exports: 'readonly',
        Buffer: 'readonly',
        console: 'readonly',
      },
    },
  },
  {
    ignores: [
      'dist/**',
      'node_modules/**', 
      'build/**',
      'coverage/**',
      'htmlcov/**',
      'lib/user-interface/react/dist/**',
      'lib/user-interface/react/public/**',
      'lib/docs/dist/**',
      'lib/docs/.vitepress/cache/**',
      'ecs_model_deployer/dist/**',
      'vector_store_deployer/dist/**',
      'cypress/dist/**',
      '.venv/**',
      'venv/**',
      '*.min.js',
      '*.bundle.js',
      '**/*.min.js',
      '**/*.bundle.js',
      '**/dist/**',
      '**/build/**',
      '**/coverage/**',
      '**/.venv/**',
      '**/venv/**',
      '**/*.d.ts'
    ]
  }
];

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

import atomOneDark from 'react-syntax-highlighter/dist/esm/styles/hljs/atom-one-dark';
import { SYSTEM_PROMPT } from '@/shared/constants/systemPrompt';

export const MODEL_COMPARISON_CONFIG = {
    MAX_MODELS: 4,
    MIN_MODELS: 2,
    DEFAULT_MAX_TOKENS: 2000,
    DEFAULT_SYSTEM_MESSAGE: SYSTEM_PROMPT,
    RETRY_ATTEMPTS: 3,
    TIMEOUT_MS: 30000,
} as const;

export const UI_CONFIG = {
    RESPONSE_MAX_WIDTH: '60em',
    CODE_BLOCK_THEME: atomOneDark,
    ANIMATION_DURATION: 200,
    GRID_BREAKPOINT: 2, // Max columns before switching to grid layout
} as const;

export const MESSAGES = {
    INSUFFICIENT_MODELS: 'You need at least 2 InService text generation models to use the comparison feature.',
    GENERATING_RESPONSE: 'Generating response...',
    FAILED_TO_GET_RESPONSE: 'Failed to get response',
    FAILED_TO_COMPARE_MODELS: 'Failed to compare models',
    ADD_MODEL_TOOLTIP: 'Add another model to compare (up to 4 total)',
    COPY_CODE_SUCCESS: 'Code copied',
    COPY_RESPONSE_SUCCESS: 'Response copied',
} as const;

export const PLACEHOLDERS = {
    PROMPT_INPUT: 'Enter your prompt here to compare responses from selected models...',
    MODEL_SELECT: (index: number) => `Select model ${index}`,
} as const;

export const ARIA_LABELS = {
    ADD_MODEL: 'Add model comparison',
    REMOVE_MODEL: (index: number) => `Remove model ${index}`,
    USER_PROMPT: 'User prompt',
    MODEL_RESPONSE: (modelName: string) => `Response from ${modelName}`,
    SEND_PROMPT: 'Send prompt',
    CODE_ACTIONS: 'Code actions',
    RESPONSE_ACTIONS: 'Response actions',
} as const;

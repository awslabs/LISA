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

import React from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark, oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism';

type SyntaxHighlightedCodeProps = {
    language: string;
    code: string;
    isDarkMode: boolean;
    highlighterProps?: Record<string, unknown>;
};

/**
 * Isolated in its own module so that react-syntax-highlighter and the prism
 * theme files are split into their own chunk, fetched lazily the first time a
 * fenced code block is rendered rather than on every chatbot route load.
 */
const SyntaxHighlightedCode: React.FC<SyntaxHighlightedCodeProps> = ({
    language,
    code,
    isDarkMode,
    highlighterProps,
}) => (
    <SyntaxHighlighter
        style={isDarkMode ? oneDark : oneLight}
        language={language}
        PreTag='div'
        {...highlighterProps}
    >
        {code}
    </SyntaxHighlighter>
);

export default SyntaxHighlightedCode;

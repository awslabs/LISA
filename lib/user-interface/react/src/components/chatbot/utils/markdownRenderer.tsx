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
import { ButtonGroup, StatusIndicator } from '@cloudscape-design/components';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark, oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism';
import remarkMath from 'remark-math';
import remarkGfm from 'remark-gfm';
import rehypeKatex from 'rehype-katex';
import MermaidDiagram from '../components/MermaidDiagram';

/**
 * Shared markdown plugins configuration
 */
export const markdownPlugins = {
    remarkPlugins: [remarkMath, remarkGfm],
    rehypePlugins: [rehypeKatex],
};

/**
 * Get markdown components configuration for ReactMarkdown
 * @param isDarkMode - Whether dark mode is enabled
 * @param isStreaming - Whether content is being streamed
 * @param onMermaidRenderComplete - Callback for when mermaid rendering completes
 */
export const getMarkdownComponents = (
    isDarkMode: boolean,
    isStreaming?: boolean,
    onMermaidRenderComplete?: () => void
) => ({
    code ({ className, children, ...props }: any) {
        const match = /language-(\w+)/.exec(className || '');
        const codeString = String(children).replace(/\n$/, '');

        const CodeBlockWithCopyButton = ({ language, code }: { language: string; code: string }) => {
            return (
                <div style={{ position: 'relative' }}>
                    <div
                        style={{
                            position: 'absolute',
                            top: '5px',
                            right: '5px',
                            zIndex: 10,
                        }}
                    >
                        <ButtonGroup
                            onItemClick={() => navigator.clipboard.writeText(code)}
                            ariaLabel='Chat actions'
                            dropdownExpandToViewport
                            items={[
                                {
                                    type: 'icon-button',
                                    id: 'copy code',
                                    iconName: 'copy',
                                    text: 'Copy Code',
                                    popoverFeedback: (
                                        <StatusIndicator type='success'>Code copied</StatusIndicator>
                                    ),
                                },
                            ]}
                            variant='icon'
                        />
                    </div>
                    <SyntaxHighlighter
                        style={isDarkMode ? oneDark : oneLight}
                        language={language}
                        PreTag='div'
                        {...props}
                    >
                        {code}
                    </SyntaxHighlighter>
                </div>
            );
        };

        const CodeBlockWithoutLanguage = ({ code }: { code: string }) => {
            return (
                <div style={{ position: 'relative' }}>
                    <div
                        style={{
                            position: 'absolute',
                            top: '5px',
                            right: '5px',
                            zIndex: 10,
                        }}
                    >
                        <ButtonGroup
                            onItemClick={() => navigator.clipboard.writeText(code)}
                            ariaLabel='Chat actions'
                            dropdownExpandToViewport
                            items={[
                                {
                                    type: 'icon-button',
                                    id: 'copy code',
                                    iconName: 'copy',
                                    text: 'Copy Code',
                                    popoverFeedback: (
                                        <StatusIndicator type='success'>Code copied</StatusIndicator>
                                    ),
                                },
                            ]}
                            variant='icon'
                        />
                    </div>
                    <pre
                        style={{
                            backgroundColor: isDarkMode ? '#1e1e1e' : '#f5f5f5',
                            color: isDarkMode ? '#d4d4d4' : '#333333',
                            padding: '16px',
                            borderRadius: '6px',
                            overflow: 'auto',
                            fontFamily: 'Consolas, Monaco, "Courier New", monospace',
                            fontSize: '14px',
                            lineHeight: '1.45',
                            margin: '0',
                            textWrap: 'wrap',
                        }}
                    >
                        <code style={{ backgroundColor: 'transparent', padding: '0', color: 'inherit' }}>
                            {code}
                        </code>
                    </pre>
                </div>
            );
        };

        // Check if this is inline code by examining the props
        const isInlineCode = !props.node || props.node.position?.start?.line === props.node.position?.end?.line;

        if (isInlineCode) {
            return (
                <code
                    className='bg-zinc-300/25 border-zinc-500/25 border-solid text-red-600 px-1 py-0.5 rounded text-sm font-mono'
                    style={{
                        backgroundColor: 'rgba(209, 213, 219, 0.25)',
                        border: '1px solid rgba(107, 114, 128, 0.25)',
                        color: '#dc2626',
                        padding: '2px 4px',
                        borderRadius: '4px',
                        fontSize: '0.875rem',
                        fontFamily:
                            'ui-monospace, SFMono-Regular, "SF Mono", Consolas, "Liberation Mono", Menlo, monospace',
                    }}
                    {...props}
                >
                    {children}
                </code>
            );
        }

        return match ? (
            match[1] === 'mermaid' ? (
                <MermaidDiagram
                    chart={codeString}
                    isStreaming={isStreaming}
                    onRenderComplete={onMermaidRenderComplete}
                />
            ) : (
                <CodeBlockWithCopyButton language={match[1]} code={codeString} />
            )
        ) : (
            <CodeBlockWithoutLanguage code={codeString} />
        );
    },
});

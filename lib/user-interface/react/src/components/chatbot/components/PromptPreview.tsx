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

import React, { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import Box from '@cloudscape-design/components/box';
import { getMarkdownComponents, markdownPlugins } from '../utils/markdownRenderer';
import { useDynamicMaxRows } from '../hooks/useDynamicMaxRows';
import remarkBreaks from 'remark-breaks';
import 'katex/dist/katex.min.css';
import styles from './Message.module.css';

type PromptPreviewProps = {
    content: string;
    isDarkMode: boolean;
};

export const PromptPreview: React.FC<PromptPreviewProps> = ({ content, isDarkMode }) => {
    // Use the same hook as Chat.tsx to ensure identical sizing
    const { dynamicMaxRows, LINE_HEIGHT, PADDING } = useDynamicMaxRows();

    // Memoize markdown components to prevent re-creation on every render
    const markdownComponents = useMemo(
        () => getMarkdownComponents(isDarkMode, false),
        [isDarkMode]
    );

    // Calculate max height based on dynamicMaxRows (matching PromptInput behavior)
    const maxHeight = (dynamicMaxRows * LINE_HEIGHT) + PADDING;

    return (
        <div
            style={{
                backgroundColor: isDarkMode ? '#1f2934' : '#ebebf0',
                borderRadius: '8px',
                padding: '8px',
                maxHeight: `${maxHeight}px`,
                overflowY: 'auto',
                border: `1px solid ${isDarkMode ? '#414d5c' : '#d1d5db'}`,
            }}
        >
            {content.trim() ? (
                <div className={styles.messageContent} style={{ maxWidth: '100%' }}>
                    <ReactMarkdown
                        remarkPlugins={[...markdownPlugins.remarkPlugins, remarkBreaks]}
                        rehypePlugins={markdownPlugins.rehypePlugins}
                        components={markdownComponents}
                    >
                        {content}
                    </ReactMarkdown>
                </div>
            ) : (
                <Box color='text-status-inactive' variant='p'>
                    Preview will appear here as you type...
                </Box>
            )}
        </div>
    );
};

export default PromptPreview;

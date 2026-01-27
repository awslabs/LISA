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

import ReactMarkdown from 'react-markdown';
import Box from '@cloudscape-design/components/box';
import ExpandableSection from '@cloudscape-design/components/expandable-section';
import { ButtonDropdown, ButtonGroup, Grid, SpaceBetween, StatusIndicator } from '@cloudscape-design/components';
import { JsonView, darkStyles, defaultStyles } from 'react-json-view-lite';
import 'react-json-view-lite/dist/index.css';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark, oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { LisaChatMessage, LisaChatMessageMetadata, MessageTypes } from '../../types';
import { useAppSelector } from '@/config/store';
import { selectCurrentUsername } from '@/shared/reducers/user.reducer';
import ChatBubble from '@cloudscape-design/chat-components/chat-bubble';
import Avatar from '@cloudscape-design/chat-components/avatar';

import remarkMath from 'remark-math';
import remarkGfm from 'remark-gfm';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import styles from './Message.module.css';

import { MessageContent } from '@langchain/core/messages';
import { base64ToBlob, fetchImage, getDisplayableMessage, messageContainsImage } from '@/components/utils';
import React, { useEffect, useState, useMemo } from 'react';
import { IChatConfiguration } from '@/shared/model/chat.configurations.model';
import { downloadFile } from '@/shared/util/downloader';
import Link from '@cloudscape-design/components/link';
import ImageViewer from '@/components/chatbot/components/ImageViewer';
import MermaidDiagram from '@/components/chatbot/components/MermaidDiagram';
import UsageInfo from '@/components/chatbot/components/UsageInfo';
import { merge } from 'lodash';
import { useContext } from 'react';
import { Mode } from '@cloudscape-design/global-styles';
import ColorSchemeContext from '@/shared/color-scheme.provider';

type MessageProps = {
    message?: LisaChatMessage;
    isRunning: boolean;
    callingToolName: string;
    showMetadata?: boolean;
    isStreaming?: boolean;
    markdownDisplay?: boolean;
    setChatConfiguration: (state: IChatConfiguration) => void;
    handleSendGenerateRequest: () => void;
    setUserPrompt: (state: string) => void;
    chatConfiguration: IChatConfiguration;
    showUsage?: boolean;
    onMermaidRenderComplete?: () => void;
};

export const Message = React.memo(({ message, isRunning, showMetadata, isStreaming, markdownDisplay, setUserPrompt, setChatConfiguration, handleSendGenerateRequest, chatConfiguration, callingToolName, showUsage = false, onMermaidRenderComplete }: MessageProps) => {
    const currentUser = useAppSelector(selectCurrentUsername);
    const ragCitations = !isStreaming && message?.metadata?.ragDocuments ? message?.metadata.ragDocuments : undefined;
    const [resend, setResend] = useState(false);
    const [showImageViewer, setShowImageViewer] = useState(false);
    const [selectedImage, setSelectedImage] = useState(undefined);
    const [selectedMetadata, setSelectedMetadata] = useState(undefined);
    const [reasoningExpanded, setReasoningExpanded] = useState(true);
    const { colorScheme } = useContext(ColorSchemeContext);
    const isDarkMode = colorScheme === Mode.Dark;
    const hasMessageContent = message?.content && typeof message.content === 'string' && message.content.trim() && message.content.trim() !== '\u00A0';

    // Auto-expand reasoning when it first appears, then auto-collapse when message content starts arriving
    useEffect(() => {
        if (hasMessageContent) {
            setReasoningExpanded(false);
        } else if (!hasMessageContent && message?.reasoningContent) {
            setReasoningExpanded(true);
        }
    }, [hasMessageContent, message?.reasoningContent]);

    useEffect(() => {
        if (resend) {
            handleSendGenerateRequest();
            setResend(false);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [resend]);

    // Memoize the ReactMarkdown components to prevent re-creation on every render
    const markdownComponents = useMemo(() => ({
        code ({ className, children, ...props }: any) {
            const match = /language-(\w+)/.exec(className || '');
            const codeString = String(children).replace(/\n$/, '');

            const CodeBlockWithCopyButton = ({ language, code }: { language: string, code: string }) => {
                return (
                    <div style={{ position: 'relative' }}>
                        <div
                            style={{
                                position: 'absolute',
                                top: '5px',
                                right: '5px',
                                zIndex: 10
                            }}
                        >
                            <ButtonGroup
                                onItemClick={() =>
                                    navigator.clipboard.writeText(code)
                                }
                                ariaLabel='Chat actions'
                                dropdownExpandToViewport
                                items={[
                                    {
                                        type: 'icon-button',
                                        id: 'copy code',
                                        iconName: 'copy',
                                        text: 'Copy Code',
                                        popoverFeedback: (
                                            <StatusIndicator type='success'>
                                                Code copied
                                            </StatusIndicator>
                                        )
                                    }
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
                                onItemClick={() =>
                                    navigator.clipboard.writeText(code)
                                }
                                ariaLabel='Chat actions'
                                dropdownExpandToViewport
                                items={[
                                    {
                                        type: 'icon-button',
                                        id: 'copy code',
                                        iconName: 'copy',
                                        text: 'Copy Code',
                                        popoverFeedback: (
                                            <StatusIndicator type='success'>
                                                Code copied
                                            </StatusIndicator>
                                        )
                                    }
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
                                textWrap: 'wrap'
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
                            fontFamily: 'ui-monospace, SFMono-Regular, "SF Mono", Consolas, "Liberation Mono", Menlo, monospace'
                        }}
                        {...props}
                    >
                        {children}
                    </code>
                );
            }
            return match ? (
                match[1] === 'mermaid' ? (
                    <MermaidDiagram chart={codeString} isStreaming={isStreaming} onRenderComplete={onMermaidRenderComplete} />
                ) : (
                    <CodeBlockWithCopyButton
                        language={match[1]}
                        code={codeString}
                    />
                )
            ) : (
                <CodeBlockWithoutLanguage code={codeString} />
            );
        },
    }), [isStreaming, onMermaidRenderComplete, isDarkMode]);

    const renderContent = (content: MessageContent, metadata?: LisaChatMessageMetadata) => {
        if (Array.isArray(content)) {
            return content.map((item: any, index) => {
                if (item.type === 'text' && typeof item.text === 'string') {
                    if (item.text.startsWith('File context:')) return null;

                    const displayableText = getDisplayableMessage(item.text, message.type === MessageTypes.AI ? ragCitations : undefined);

                    return (
                        <div key={index} className={styles.messageContent} style={{ maxWidth: '60em' }}>
                            {markdownDisplay ? (
                                <ReactMarkdown
                                    remarkPlugins={[remarkMath, remarkGfm]}
                                    rehypePlugins={[rehypeKatex]}
                                    children={displayableText}
                                    components={markdownComponents}
                                />
                            ) : (
                                <div style={{ whiteSpace: 'pre-line' }}>{displayableText}</div>
                            )}
                        </div>
                    );
                } else if (item.type === 'image_url' && item.image_url?.url) {
                    return message.type === MessageTypes.HUMAN ?
                        <img key={index} src={item.image_url.url} alt='User provided' style={{ maxWidth: '50%', maxHeight: '30em', marginTop: '8px' }} /> :
                        <Grid key={`${index}-Grid`} gridDefinition={[{ colspan: 11 }, { colspan: 1 }]}>
                            <Link onClick={() => {
                                setSelectedImage(item);
                                setSelectedMetadata(metadata);
                                setShowImageViewer(true);
                            }}>
                                <img key={`${index}-Image`} src={item.image_url.url} alt='AI Generated' style={{ maxWidth: '100%', maxHeight: '30em', marginTop: '8px' }} />
                            </Link>
                            <ButtonDropdown
                                items={[
                                    { id: 'download-image', text: 'Download Image', iconName: 'download' },
                                    { id: 'copy-image', text: 'Copy Image', iconName: 'copy' },
                                    { id: 'regenerate', text: 'Regenerate Image(s)', iconName: 'refresh' }
                                ]}
                                ariaLabel='Control instance'
                                variant='icon'
                                onItemClick={async (e) => {
                                    if (e.detail.id === 'download-image') {
                                        const file = item.image_url.url.startsWith('https://') ?
                                            await fetchImage(item.image_url.url)
                                            : base64ToBlob(item.image_url.url.split(',')[1], 'image/png');
                                        downloadFile(URL.createObjectURL(file), `${metadata?.imageGenerationParams?.prompt}.png`);
                                    } else if (e.detail.id === 'copy-image') {
                                        const copy = new ClipboardItem({
                                            'image/png': item.image_url.url.startsWith('https://') ?
                                                await fetchImage(item.image_url.url) : base64ToBlob(item.image_url.url.split(',')[1], 'image/png')
                                        });
                                        await navigator.clipboard.write([copy]);
                                    } else if (e.detail.id === 'regenerate') {
                                        setChatConfiguration(
                                            merge({}, chatConfiguration, {
                                                sessionConfiguration: {
                                                    imageGenerationArgs: {
                                                        size: metadata?.imageGenerationParams?.size,
                                                        numberOfImages: metadata?.imageGenerationParams?.n,
                                                        quality: metadata?.imageGenerationParams?.quality
                                                    }
                                                }
                                            })
                                        );
                                        setUserPrompt(metadata?.imageGenerationParams?.prompt ?? '');
                                        setResend(true);
                                    }
                                }}
                            />
                        </Grid>;
                } else if (item.type === 'video_url' && item.video_url?.url) {
                    return (
                        <Grid key={`${index}-Grid`} gridDefinition={[{ colspan: 11 }, { colspan: 1 }]}>
                            <video 
                                key={`${index}-Video`} 
                                controls 
                                style={{ maxWidth: '100%', maxHeight: '30em', marginTop: '8px' }}
                            >
                                <source src={item.video_url.url} type="video/mp4" />
                                Your browser does not support the video tag.
                            </video>
                            <ButtonDropdown
                                items={[
                                    { id: 'download-video', text: 'Download Video', iconName: 'download' },
                                    { id: 'regenerate', text: 'Regenerate Video', iconName: 'refresh' }
                                ]}
                                ariaLabel='Video actions'
                                variant='icon'
                                onItemClick={async (e) => {
                                    if (e.detail.id === 'download-video') {
                                        const videoUrl = item.video_url.url;
                                        const videoBlob = await fetch(videoUrl).then(r => r.blob());
                                        const filename = `${metadata?.videoGenerationParams?.prompt || 'video'}.mp4`;
                                        downloadFile(URL.createObjectURL(videoBlob), filename);
                                    } else if (e.detail.id === 'regenerate') {
                                        setUserPrompt(metadata?.videoGenerationParams?.prompt ?? '');
                                        setResend(true);
                                    }
                                }}
                            />
                        </Grid>
                    );
                }
                return null;
            });
        }
        return (
            <div className={styles.messageContent} style={{ maxWidth: '60em' }}>
                {markdownDisplay ? (
                    <ReactMarkdown
                        remarkPlugins={[remarkMath, remarkGfm]}
                        rehypePlugins={[rehypeKatex]}
                        children={getDisplayableMessage(content, message.type === MessageTypes.AI ? ragCitations : undefined)}
                        components={markdownComponents}
                    />
                ) : (
                    <div style={{ whiteSpace: 'pre-line' }}>{getDisplayableMessage(content, message.type === MessageTypes.AI ? ragCitations : undefined)}</div>
                )}
            </div>);
    };

    return (
        (message.type === MessageTypes.HUMAN || message.type === MessageTypes.AI || message.type === MessageTypes.TOOL) &&
        <div className='mt-2' style={{ overflow: 'hidden' }} data-testid={`chat-message-${message.type}`}>
            <ImageViewer setVisible={setShowImageViewer} visible={showImageViewer} selectedImage={selectedImage} metadata={selectedMetadata} />
            {(isRunning && !callingToolName) && (
                <ChatBubble
                    ariaLabel='Generative AI assistant'
                    type='incoming'
                    avatar={
                        <Avatar
                            loading={true}
                            color='gen-ai'
                            iconName='gen-ai'
                            ariaLabel='Generative AI assistant'
                            tooltipText='Generative AI assistant'
                        />
                    }
                    actions={showUsage ? <UsageInfo usage={message.usage} /> : undefined}
                >
                    <Box color='text-status-inactive' data-testid='generating-response-box'>
                        Generating response
                    </Box>
                </ChatBubble>
            )}
            {callingToolName && (
                <ChatBubble
                    ariaLabel='Generative AI assistant'
                    type='incoming'
                    avatar={
                        <Avatar
                            loading={true}
                            color='gen-ai'
                            iconName='gen-ai'
                            ariaLabel='Generative AI assistant'
                            tooltipText='Generative AI assistant'
                        />
                    }
                    actions={showUsage ? <UsageInfo usage={message.usage} /> : undefined}
                >
                    <Box color='text-status-inactive'>
                        🔨Calling {callingToolName} tool 🔨
                    </Box>
                </ChatBubble>
            )}
            {message?.type === 'ai' && !isRunning && !callingToolName && (message?.content || message?.reasoningContent) && (
                <SpaceBetween direction='horizontal' size='m'>
                    <ChatBubble
                        ariaLabel='Generative AI assistant'
                        type='incoming'
                        showLoadingBar={isStreaming}
                        avatar={
                            <Avatar
                                color='gen-ai'
                                iconName='gen-ai'
                                ariaLabel='Generative AI assistant'
                                tooltipText='Generative AI assistant'
                            />
                        }
                        actions={showUsage ? <UsageInfo usage={message.usage} /> : undefined}
                    >
                        {message?.reasoningContent && chatConfiguration.sessionConfiguration.showReasoningContent && (
                            <Box margin={{ bottom: 's' }}>
                                <ExpandableSection
                                    variant='footer'
                                    headerText='Reasoning'
                                    expanded={reasoningExpanded}
                                    onChange={({ detail }) => {
                                        setReasoningExpanded(detail.expanded);
                                    }}
                                >
                                    <SpaceBetween direction='vertical' size='s'>
                                        <Grid gridDefinition={[{ colspan: 11 }, { colspan: 1 }]}>
                                            <Box color='text-status-inactive' variant='small' padding={{ right: 'xl' }}>
                                                <SpaceBetween direction='vertical' size='s'>
                                                    <div style={{ whiteSpace: 'pre-line' }}>{message.reasoningContent}</div>
                                                    <hr/>
                                                </SpaceBetween>
                                            </Box>
                                            <ButtonGroup
                                                onItemClick={({ detail }) => {
                                                    if (detail.id === 'copy-reasoning') {
                                                        navigator.clipboard.writeText(message.reasoningContent || '');
                                                    }
                                                }}
                                                ariaLabel='Copy reasoning content'
                                                dropdownExpandToViewport
                                                items={[
                                                    {
                                                        type: 'icon-button',
                                                        id: 'copy-reasoning',
                                                        iconName: 'copy',
                                                        text: 'Copy Reasoning',
                                                        popoverFeedback: (
                                                            <StatusIndicator type='success'>
                                                                Reasoning copied
                                                            </StatusIndicator>
                                                        )
                                                    }
                                                ]}
                                                variant='icon'
                                            />
                                        </Grid>
                                    </SpaceBetween>
                                </ExpandableSection>
                            </Box>
                        )}
                        {message?.content && (typeof message.content === 'string' ? (message.content.trim() && message.content.trim() !== '\u00A0') : true) && renderContent(message.content, message.metadata)}
                        {showMetadata && !isStreaming &&
                            <ExpandableSection
                                variant='footer'
                                headerText='Metadata'
                            >
                                <JsonView data={{
                                    ...message.metadata,
                                    ...(message.usage && { usage: message.usage })
                                }} style={isDarkMode ? darkStyles : defaultStyles} />
                            </ExpandableSection>}
                    </ChatBubble>
                    {!isStreaming && !messageContainsImage(message.content) && <div
                        style={{ display: 'flex', alignItems: 'center', height: '100%', justifyContent: 'flex-end' }}>
                        <ButtonGroup
                            onItemClick={({ detail }) =>
                                ['copy'].includes(detail.id) &&
                                navigator.clipboard.writeText(getDisplayableMessage(message.content))
                            }
                            ariaLabel='Chat actions'
                            dropdownExpandToViewport
                            items={[
                                {
                                    type: 'icon-button',
                                    id: 'copy',
                                    iconName: 'copy',
                                    text: 'Copy Message',
                                    popoverFeedback: (
                                        <StatusIndicator type='success'>
                                            Message copied
                                        </StatusIndicator>
                                    )
                                }
                            ]}
                            variant='icon'
                        />
                    </div>}
                </SpaceBetween>
            )}
            {message?.type === 'human' && (
                <SpaceBetween direction='horizontal' size='m'>
                    <div style={{ display: 'flex', alignItems: 'center', height: '100%', justifyContent: 'flex-end' }}>
                        <ChatBubble
                            ariaLabel={currentUser}
                            type='outgoing'
                            avatar={
                                <Avatar
                                    ariaLabel={currentUser}
                                    tooltipText={currentUser}
                                    initials={currentUser?.charAt(0).toUpperCase()}
                                />
                            }
                        >
                            <div className='message-content' style={{ maxWidth: '60em' }}>
                                {renderContent(message.content)}
                            </div>
                        </ChatBubble>
                        <ButtonGroup
                            onItemClick={({ detail }) =>
                                ['copy'].includes(detail.id) &&
                                navigator.clipboard.writeText(getDisplayableMessage(message.content))
                            }
                            ariaLabel='Chat actions'
                            dropdownExpandToViewport
                            items={[
                                {
                                    type: 'icon-button',
                                    id: 'copy',
                                    iconName: 'copy',
                                    text: 'Copy Input',
                                    popoverFeedback: (
                                        <StatusIndicator type='success'>
                                            Input copied
                                        </StatusIndicator>
                                    )
                                }
                            ]}
                            variant='icon'
                        />
                    </div>
                </SpaceBetween>
            )}
            {message?.type === MessageTypes.TOOL && (
                <ExpandableSection variant='footer' headerText={`🔨Called Tool - ${(message?.metadata as any)?.toolName || 'Unknown'} 🔨`}>
                    <JsonView data={{
                        arguments: (message?.metadata as any)?.args,
                        result: message?.content,
                    }} style={isDarkMode ? darkStyles : defaultStyles} />
                </ExpandableSection>
            )}
        </div>
    );
});

export default Message;

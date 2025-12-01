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
import { JsonView, darkStyles } from 'react-json-view-lite';
import 'react-json-view-lite/dist/index.css';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { LisaChatMessage, LisaChatMessageMetadata, MessageTypes } from '../../types';
import { useAppSelector } from '@/config/store';
import { selectCurrentUsername } from '@/shared/reducers/user.reducer';
import ChatBubble from '@cloudscape-design/chat-components/chat-bubble';
import Avatar from '@cloudscape-design/chat-components/avatar';
import remarkBreaks from 'remark-breaks';
import remarkMath from 'remark-math';
import rehypeMathjax from 'rehype-mathjax/browser';
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
                            style={vscDarkPlus}
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
                                backgroundColor: '#1e1e1e',
                                color: '#d4d4d4',
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
                        className='bg-gray-300 bg-opacity-25 border-opacity-25 border-gray-500 border-solid text-red-600 px-1 py-0.5 rounded text-sm font-mono'
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
    }), [isStreaming, onMermaidRenderComplete]); // Include isStreaming and onMermaidRenderComplete so the component can access them

    const renderContent = (messageType: string, content: MessageContent, metadata?: LisaChatMessageMetadata) => {
        if (Array.isArray(content)) {
            return content.map((item, index) => {
                if (item.type === 'text') {
                    return item.text.startsWith('File context:') ? <></> : <div key={index}>{getDisplayableMessage(item.text, message.type === MessageTypes.AI ? ragCitations : undefined)}</div>;
                } else if (item.type === 'image_url') {
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
                }
                return null;
            });
        }
        return (
            <div style={{ maxWidth: '60em' }}>
                {markdownDisplay ? (
                    <ReactMarkdown
                        remarkPlugins={[remarkBreaks, remarkMath]}
                        rehypePlugins={[rehypeMathjax]}
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
        <div className='mt-2' style={{ overflow: 'hidden' }}>
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
                    <Box color='text-status-inactive'>
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
            {message?.type === 'ai' && !isRunning && !callingToolName && message?.content && (
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
                        {renderContent(message.type, message.content, message.metadata)}
                        {showMetadata && !isStreaming &&
                            <ExpandableSection
                                variant='footer'
                                headerText='Metadata'
                            >
                                <JsonView data={{
                                    ...message.metadata,
                                    ...(message.usage && { usage: message.usage })
                                }} style={darkStyles} />
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
                            <div style={{ maxWidth: '60em' }}>
                                {renderContent(message.type, message.content)}
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
                <ExpandableSection variant='footer' headerText={`🔨Called Tool - ${message?.metadata?.toolName} 🔨`}>
                    <JsonView data={{
                        arguments: message?.metadata?.args,
                        result: message?.content,
                    }} style={darkStyles} />
                </ExpandableSection>
            )}
        </div>
    );
});

export default Message;

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
import { LisaChatMessage, LisaChatMessageMetadata, MessageTypes } from '../../types';
import { useAppSelector } from '@/config/store';
import { selectCurrentUsername } from '@/shared/reducers/user.reducer';
import ChatBubble from '@cloudscape-design/chat-components/chat-bubble';
import Avatar from '@cloudscape-design/chat-components/avatar';

import 'katex/dist/katex.min.css';
import styles from './Message.module.css';
import { getMarkdownComponents, markdownPlugins } from '../utils/markdownRenderer';

import { MessageContent } from '@langchain/core/messages';
import { base64ToBlob, fetchImage, getDisplayableMessage } from '@/components/utils';
import React, { useEffect, useState, useMemo } from 'react';
import { IChatConfiguration } from '@/shared/model/chat.configurations.model';
import { downloadFile } from '@/shared/util/downloader';
import Link from '@cloudscape-design/components/link';
import ImageViewer from '@/components/chatbot/components/ImageViewer';
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
    onVideoLoadComplete?: () => void;
    onImageLoadComplete?: () => void;
    retryResponse?: () => Promise<void>
    errorState?: boolean;
    onOpenDocument?: (document: any) => void;
};

export const Message = React.memo(({ message, isRunning, showMetadata, isStreaming, markdownDisplay, setUserPrompt, setChatConfiguration, handleSendGenerateRequest, chatConfiguration, callingToolName, showUsage = false, onMermaidRenderComplete, onVideoLoadComplete, onImageLoadComplete, retryResponse, errorState, onOpenDocument }: MessageProps) => {
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

    // Check if ragDocuments is an array (new format with structured data)
    const ragDocuments = Array.isArray(ragCitations) ? ragCitations : undefined;

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
    const markdownComponents = useMemo(
        () => getMarkdownComponents(isDarkMode, isStreaming, onMermaidRenderComplete),
        [isDarkMode, isStreaming, onMermaidRenderComplete]
    );

    const renderContent = (content: MessageContent, metadata?: LisaChatMessageMetadata) => {
        if (Array.isArray(content)) {
            return content.map((item: any, index) => {
                if (item.type === 'text' && typeof item.text === 'string') {
                    if (item.text.startsWith('File context:')) return null;

                    const displayableText = getDisplayableMessage(item.text);

                    return (
                        <div key={index} className={styles.messageContent} style={{ maxWidth: '60em' }}>
                            {markdownDisplay ? (
                                <ReactMarkdown
                                    remarkPlugins={markdownPlugins.remarkPlugins}
                                    rehypePlugins={markdownPlugins.rehypePlugins}
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
                        <img key={index} src={item.image_url.url} alt='User provided' style={{ maxWidth: '50%', maxHeight: '30em', marginTop: '8px' }} onLoad={() => onImageLoadComplete?.()} /> :
                        <Grid key={`${index}-Grid`} gridDefinition={[{ colspan: 11 }, { colspan: 1 }]}>
                            <Link onClick={() => {
                                setSelectedImage(item);
                                setSelectedMetadata(metadata);
                                setShowImageViewer(true);
                            }}>
                                <img key={`${index}-Image`} src={item.image_url.url} alt='AI Generated' style={{ maxWidth: '100%', maxHeight: '30em', marginTop: '8px' }} onLoad={() => onImageLoadComplete?.()} />
                            </Link>
                            <ButtonDropdown
                                items={[
                                    { id: 'download-image', text: 'Download Image', iconName: 'download' },
                                    { id: 'share-image', text: 'Share Image Link', iconName: 'share' },
                                    { id: 'copy-image', text: 'Copy Image', iconName: 'copy' },
                                    { id: 'regenerate', text: 'Regenerate Image(s)', iconName: 'refresh' }
                                ]}
                                ariaLabel='Image actions'
                                variant='icon'
                                onItemClick={async (e) => {
                                    if (e.detail.id === 'download-image') {
                                        const file = item.image_url.url.startsWith('https://') ?
                                            await fetchImage(item.image_url.url)
                                            : base64ToBlob(item.image_url.url.split(',')[1], 'image/png');
                                        downloadFile(URL.createObjectURL(file), `${metadata?.imageGenerationParams?.prompt}.png`);
                                    } else if (e.detail.id === 'share-image') {
                                        navigator.clipboard.writeText(item.image_url.url);
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
                    const videoId = item.video_url.video_id;
                    return (
                        <div key={index} style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', marginTop: '8px', maxWidth: '100%' }}>
                            <video
                                controls
                                style={{ flex: 1, maxHeight: '30em', minWidth: 0 }}
                                onLoadedData={() => onVideoLoadComplete?.()}
                            >
                                <source src={item.video_url.url} type='video/mp4' />
                                Your browser does not support the video tag.
                            </video>
                            <ButtonDropdown
                                items={[
                                    { id: 'download-video', text: 'Download Video', iconName: 'download' },
                                    { id: 'share-video', text: 'Share Video Link', iconName: 'share' },
                                    { id: 'remix-video', text: 'Remix Video', iconName: 'refresh' }
                                ]}
                                ariaLabel='Video actions'
                                variant='icon'
                                onItemClick={async (e) => {
                                    if (e.detail.id === 'download-video') {
                                        const videoUrl = item.video_url.url;
                                        const videoBlob = await fetch(videoUrl).then((r) => r.blob());
                                        const filename = `${metadata?.videoGenerationParams?.prompt || 'video'}.mp4`;
                                        downloadFile(URL.createObjectURL(videoBlob), filename);
                                    } else if (e.detail.id === 'share-video') {
                                        navigator.clipboard.writeText(item.video_url.url);
                                    } else if (e.detail.id === 'remix-video' && videoId) {
                                        // Call the remix endpoint to create a new variation
                                        setUserPrompt(`Remix video: ${metadata?.videoGenerationParams?.prompt ?? ''}`);
                                        // Store the video_id for the remix call
                                        setChatConfiguration(
                                            merge({}, chatConfiguration, {
                                                sessionConfiguration: {
                                                    remixVideoId: videoId
                                                }
                                            })
                                        );
                                        setResend(true);
                                    }
                                }}
                            />
                        </div>
                    );
                }
                return null;
            });
        }
        return (
            <div className={styles.messageContent} style={{ maxWidth: '60em' }}>
                {markdownDisplay ? (
                    <ReactMarkdown
                        remarkPlugins={markdownPlugins.remarkPlugins}
                        rehypePlugins={markdownPlugins.rehypePlugins}
                        children={getDisplayableMessage(content)}
                        components={markdownComponents}
                    />
                ) : (
                    <div style={{ whiteSpace: 'pre-line' }}>{getDisplayableMessage(content)}</div>
                )}
            </div>);
    };

    return (
        (message.type === MessageTypes.HUMAN || message.type === MessageTypes.AI || message.type === MessageTypes.TOOL) &&
        <div className='mt-2' style={{ overflow: 'hidden' }} data-testid={`chat-message-${message.type}`}>
            <ImageViewer setVisible={setShowImageViewer} visible={showImageViewer} selectedImage={selectedImage} metadata={selectedMetadata} />
            {(isRunning && !callingToolName && !message?.metadata?.videoGeneration) && (
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
                        showLoadingBar={isStreaming || (message?.metadata?.imageGeneration && message?.metadata?.imageGenerationStatus === 'processing')}
                        avatar={
                            <Avatar
                                loading={message?.metadata?.imageGeneration && message?.metadata?.imageGenerationStatus === 'processing'}
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
                                                    <hr />
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
                        {ragDocuments && ragDocuments.length > 0 && !isStreaming && (
                            <Box margin={{ top: 's' }}>
                                <ExpandableSection
                                    variant='footer'
                                    headerText={`Citations (${ragDocuments.length})`}
                                >
                                    <SpaceBetween direction='vertical' size='xs'>
                                        {ragDocuments.map((doc, index) => (
                                            <Box key={doc.documentId || index}>
                                                {doc.documentId && onOpenDocument ? (
                                                    <Link
                                                        onFollow={() => onOpenDocument(doc)}
                                                    >
                                                        [{index + 1}] {doc.name}
                                                    </Link>
                                                ) : (
                                                    <Box variant='span' color='text-status-inactive'>
                                                        [{index + 1}] {doc.name} (preview unavailable)
                                                    </Box>
                                                )}
                                            </Box>
                                        ))}
                                    </SpaceBetween>
                                </ExpandableSection>
                            </Box>
                        )}
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
                        {!isStreaming && !isRunning && !message?.metadata?.imageGeneration && !message?.metadata?.videoGeneration &&
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
                        />}
                    </ChatBubble>
                </SpaceBetween>
            )}
            {message?.type === 'human' && (
                <SpaceBetween direction='horizontal' size='m'>
                    <div style={{ display: 'flex', alignItems: 'center', height: '100%', justifyContent: 'flex-end' }}>
                        <ChatBubble
                            ariaLabel={currentUser}
                            type='outgoing'
                            style={{
                                bubble: {
                                    background: isDarkMode ? '#1f2934' : '#ebebf0',
                                    borderColor: errorState ? '#ff7a7a' : '',
                                    borderWidth: errorState ? '1px' : '',
                                }
                            }}
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
                            <ButtonGroup
                                onItemClick={async ({ detail }) => {
                                    if (detail.id === 'copy') {
                                        navigator.clipboard.writeText(getDisplayableMessage(message.content));
                                    } else if (detail.id === 'retry') {
                                        await retryResponse();
                                    }
                                }
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
                                    },
                                    ...(errorState ? [
                                        {
                                            type: 'icon-button' as const,
                                            id: 'retry' as const,
                                            iconName: 'refresh' as const,
                                            text: 'Retry Message' as const,
                                            popoverFeedback: (
                                                <StatusIndicator type='success'>
                                                    Retrying Message
                                                </StatusIndicator>
                                            )
                                        }] : [])
                                ]}
                                variant='icon'
                            />
                        </ChatBubble>
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

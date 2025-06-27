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
import { MessageContent } from '@langchain/core/messages';
import { base64ToBlob, fetchImage, getDisplayableMessage, messageContainsImage } from '@/components/utils';
import React, { useEffect, useState } from 'react';
import { IChatConfiguration } from '@/shared/model/chat.configurations.model';
import { downloadFile } from '@/shared/util/downloader';
import Link from '@cloudscape-design/components/link';
import ImageViewer from '@/components/chatbot/components/ImageViewer';
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
};

export default function Message ({ message, isRunning, showMetadata, isStreaming, markdownDisplay, setUserPrompt, setChatConfiguration, handleSendGenerateRequest, chatConfiguration, callingToolName }: MessageProps) {
    const currentUser = useAppSelector(selectCurrentUsername);
    const ragCitations = !isStreaming && message?.metadata?.ragDocuments ? message?.metadata.ragDocuments : undefined;
    const [resend, setResend] = useState(false);
    const [showImageViewer, setShowImageViewer] = useState(false);
    const [selectedImage, setSelectedImage] = useState(undefined);
    const [selectedMetadata, setSelectedMetadata] = useState(undefined);

    useEffect(() => {
        if (resend){
            handleSendGenerateRequest();
            setResend(false);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [resend]);

    const renderContent = (messageType: string, content: MessageContent, metadata?: LisaChatMessageMetadata) => {
        if (Array.isArray(content)) {
            return content.map((item, index) => {
                if (item.type === 'text') {
                    return item.text.startsWith('File context:') ? <></> : <div key={index}>{getDisplayableMessage(item.text, message.type === MessageTypes.AI ? ragCitations : undefined)}</div>;
                } else if (item.type === 'image_url') {
                    return message.type === MessageTypes.HUMAN ?
                        <img key={index} src={item.image_url.url} alt='User provided' style={{ maxWidth:  '50%',  maxHeight: '30em', marginTop: '8px' }} /> :
                        <Grid key={`${index}-Grid`} gridDefinition={[{ colspan: 11 }, { colspan: 1 }]}>
                            <Link onClick={() => {
                                setSelectedImage(item);
                                setSelectedMetadata(metadata);
                                setShowImageViewer(true);
                            }}>
                                <img key={`${index}-Image`} src={item.image_url.url} alt='AI Generated' style={{ maxWidth:  '100%',  maxHeight: '30em', marginTop: '8px' }} />
                            </Link>
                            <ButtonDropdown
                                items={[
                                    { id: 'download-image', text: 'Download Image', iconName: 'download'},
                                    { id: 'copy-image', text: 'Copy Image', iconName: 'copy'},
                                    { id: 'regenerate', text: 'Regenerate Image(s)', iconName: 'refresh'}
                                ]}
                                ariaLabel='Control instance'
                                variant='icon'
                                onItemClick={async (e) => {
                                    if (e.detail.id === 'download-image'){
                                        const file = item.image_url.url.startsWith('https://') ?
                                            await fetchImage(item.image_url.url)
                                            : base64ToBlob(item.image_url.url.split(',')[1], 'image/png');
                                        downloadFile(URL.createObjectURL(file), `${metadata?.imageGenerationParams?.prompt}.png`);
                                    } else if (e.detail.id === 'copy-image') {
                                        const copy = new ClipboardItem({ 'image/png':item.image_url.url.startsWith('https://') ?
                                            await fetchImage(item.image_url.url) : base64ToBlob(item.image_url.url.split(',')[1], 'image/png') });
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
                        remarkPlugins={[remarkBreaks]}
                        children={getDisplayableMessage(content, message.type === MessageTypes.AI ? ragCitations : undefined)}
                        components={{
                            code ({className, children, ...props}: any) {
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
                                                    onItemClick={( ) =>
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

                                return match ? (
                                    <CodeBlockWithCopyButton
                                        language={match[1]}
                                        code={codeString}
                                    />
                                ) : (
                                    <code className={className} {...props}>
                                        {children}
                                    </code>
                                );
                            },
                            ul ({...props}: any) {
                                return <ul style={{ paddingLeft: '20px', marginTop: '8px', marginBottom: '8px', listStyleType: 'disc' }} {...props} />;
                            },
                            ol ({...props}: any) {
                                return <ol style={{ paddingLeft: '20px', marginTop: '8px', marginBottom: '8px' }} {...props} />;
                            },
                            li ({...props}: any) {
                                return <li style={{ marginBottom: '4px', display: 'list-item' }} {...props} />;
                            },
                        }}
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
                >
                    <Box color='text-status-inactive'>
                        🔨Calling {callingToolName} tool 🔨
                    </Box>
                </ChatBubble>
            )}
            {message?.type === 'ai' && !isRunning && !callingToolName && (
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
                    >
                        {renderContent(message.type, message.content, message.metadata)}
                        {showMetadata && !isStreaming && <ExpandableSection variant='footer' headerText='Metadata'>
                            <JsonView data={message.metadata} style={darkStyles} />
                        </ExpandableSection>}
                    </ChatBubble>
                    {!isStreaming  && !messageContainsImage(message.content) && <div
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
            )}
            {message?.type === MessageTypes.TOOL && (
                <ChatBubble
                    ariaLabel={currentUser}
                    type='incoming'
                    avatar={
                        <Avatar
                            ariaLabel={currentUser}
                            tooltipText={currentUser}
                            initials={currentUser?.charAt(0).toUpperCase()}
                        />
                    }
                >
                    <div style={{ maxWidth: '60em' }}>
                        {JSON.stringify(message)}
                    </div>
                </ChatBubble>
            )}
        </div>
    );
}

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
import { ButtonGroup, SpaceBetween, StatusIndicator } from '@cloudscape-design/components';
import { JsonView, darkStyles } from 'react-json-view-lite';
import 'react-json-view-lite/dist/index.css';
import { LisaChatMessage, LisaChatMessageMetadata } from '../types';
import { useAppSelector } from '../../config/store';
import { selectCurrentUsername } from '../../shared/reducers/user.reducer';
import ChatBubble from '@cloudscape-design/chat-components/chat-bubble';
import Avatar from '@cloudscape-design/chat-components/avatar';
import remarkBreaks from 'remark-breaks';
import { MessageContent } from '@langchain/core/messages';

type MessageProps = {
    message?: LisaChatMessage;
    isRunning: boolean;
    showMetadata?: boolean;
    isStreaming?: boolean;
    markdownDisplay?: boolean;
};

export default function Message ({ message, isRunning, showMetadata, isStreaming, markdownDisplay }: MessageProps) {
    const currentUser = useAppSelector(selectCurrentUsername);
    
    const getDisplayableMessage = (content: MessageContent, metadata?: LisaChatMessageMetadata) => {
        if (Array.isArray(content)) {
            return content.find(item => item.type === 'text')?.text || '';
        }
        return content + (!isStreaming && metadata?.ragDocuments ? metadata.ragDocuments : '');
    };

    const renderContent = (content: MessageContent) => {
        if (Array.isArray(content)) {
            return content.map((item, index) => {
                if (item.type === 'text') {
                    return <div key={index}>{item.text}</div>;
                } else if (item.type === 'image_url') {
                    return <img key={index} src={item.image_url.url} alt="User provided" style={{ maxWidth: '50%',  maxHeight: '30em', marginTop: '8px' }} />;
                }
                return null;
            });
        }
        return <div>{content}</div>;
    };

    return (
        <div className='mt-2' style={{ overflow: 'hidden' }}>
            {isRunning && (
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
            {message?.type !== 'human' && !isRunning && (
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
                        <div style={{ maxWidth: '60em' }}>
                            {markdownDisplay ? <ReactMarkdown
                                remarkPlugins={[remarkBreaks]}
                                children={getDisplayableMessage(message.content, message.metadata)}
                            /> : <div style={{ whiteSpace: 'pre-line' }}>{getDisplayableMessage(message.content, message.metadata)}</div>}
                        </div>
                        {showMetadata && !isStreaming && <ExpandableSection variant='footer' headerText='Metadata'>
                            <JsonView data={message.metadata} style={darkStyles} />
                        </ExpandableSection>}
                    </ChatBubble>
                    {!isStreaming && <div
                        style={{ display: 'flex', alignItems: 'center', height: '100%', justifyContent: 'flex-end' }}>
                        <ButtonGroup
                            onItemClick={({ detail }) =>
                                ['copy'].includes(detail.id) &&
                                navigator.clipboard.writeText(typeof message.content === 'string' ? message.content : JSON.stringify(message.content))
                            }
                            ariaLabel='Chat actions'
                            dropdownExpandToViewport
                            items={[
                                {
                                    type: 'icon-button',
                                    id: 'copy',
                                    iconName: 'copy',
                                    text: 'Copy',
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
                        {renderContent(message.content)}
                    </div>
                </ChatBubble>
            )}
        </div>
    );
}

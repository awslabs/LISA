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
import { PromptInput, ButtonGroup, FileTokenGroup, Box } from '@cloudscape-design/components';
import { IConfiguration } from '@/shared/model/configuration.model';

type ChatPromptInputProps = {
    userPrompt: string;
    shouldShowStopButton: boolean;
    dynamicMaxRows: number;
    isModelDeleted: boolean;
    isConnected: boolean;
    selectedModel: any;
    loadingSession: boolean;
    isImageGenerationMode: boolean;
    isVideoGenerationMode: boolean;
    fileContext: string;
    fileContextName: string;
    config: IConfiguration;
    useRag: boolean;
    showMarkdownPreview: boolean;
    setUserPrompt: (value: string) => void;
    setFileContext: (value: string) => void;
    setFileContextName: (value: string) => void;
    handleAction: () => void;
    handleKeyPress: (event: any) => void;
    handleButtonClick: (event: { detail: { id: string } }) => void;
    getButtonItems: (
        config: IConfiguration,
        useRag: boolean,
        isImageGenerationMode: boolean,
        isVideoGenerationMode: boolean,
        isConnected: boolean,
        isModelDeleted: boolean,
        showMarkdownPreview: boolean
    ) => any[];
};

export const ChatPromptInput: React.FC<ChatPromptInputProps> = ({
    userPrompt,
    shouldShowStopButton,
    dynamicMaxRows,
    isModelDeleted,
    isConnected,
    selectedModel,
    loadingSession,
    isImageGenerationMode,
    isVideoGenerationMode,
    fileContext,
    fileContextName,
    config,
    useRag,
    showMarkdownPreview,
    setUserPrompt,
    setFileContext,
    setFileContextName,
    handleAction,
    handleKeyPress,
    handleButtonClick,
    getButtonItems,
}) => {
    return (
        <PromptInput
            value={userPrompt}
            actionButtonAriaLabel={shouldShowStopButton ? 'Stop generation' : 'Send message'}
            actionButtonIconName={shouldShowStopButton ? 'status-negative' : 'send'}
            maxRows={dynamicMaxRows}
            minRows={2}
            spellcheck={true}
            style={
                {
                    root: {
                        borderColor: {
                            disabled: isModelDeleted ? '#ffe347' : isConnected ? '' : '#ff7a7a'
                        }
                    }
                }
            }
            placeholder={
                !selectedModel ? 'You must select a model before sending a message' :
                    isModelDeleted ? 'The model used in this session is no longer available.' :
                        isImageGenerationMode ? 'Describe the image you want to generate...' :
                            'Send a message'
            }
            disabled={!selectedModel || loadingSession || !isConnected || isModelDeleted}
            onChange={({ detail }) => setUserPrompt(detail.value)}
            onAction={handleAction}
            onKeyDown={handleKeyPress}
            controlId='chat-prompt-input'
            secondaryActions={
                <Box padding={{ left: 'xxs', top: 'xs' }}>
                    <ButtonGroup
                        ariaLabel='Chat actions'
                        onItemClick={handleButtonClick}
                        items={getButtonItems(config, useRag, isImageGenerationMode, isVideoGenerationMode, isConnected, isModelDeleted, showMarkdownPreview)}
                        variant='icon'
                        dropdownExpandToViewport={true}
                    />
                </Box>
            }
            secondaryContent={
                fileContext && (
                    <FileTokenGroup
                        items={[{ file: new File([fileContext], fileContextName) }]}
                        onDismiss={() => {
                            setFileContext('');
                            setFileContextName('');
                        }}
                        alignment='horizontal'
                        showFileSize={false}
                        showFileLastModified={false}
                        showFileThumbnail={false}
                        i18nStrings={{
                            removeFileAriaLabel: () => 'Remove file',
                            limitShowFewer: 'Show fewer files',
                            limitShowMore: 'Show more files',
                            errorIconAriaLabel: 'Error',
                            warningIconAriaLabel: 'Warning'
                        }}
                    />
                )
            }
        />
    );
};

export default ChatPromptInput;

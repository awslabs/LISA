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

import { useEffect, useState } from 'react';
import { useAuth } from '../../../auth/useAuth';
import { LisaChatMessageMetadata, LisaChatSession } from '@/components/types';
import { IChatConfiguration } from '@/shared/model/chat.configurations.model';
import { IModel } from '@/shared/model/model-management.model';
import { extractImageDataUrlFromFileContext } from '../utils/fileContext.utils';

export const useMemory = (
    session: LisaChatSession,
    chatConfiguration: IChatConfiguration,
    selectedModel: IModel | undefined,
    userPrompt: string,
    fileContext: string,
    notificationService: any
) => {
    void session;
    void userPrompt;
    const auth = useAuth();
    const [metadata, setMetadata] = useState<LisaChatMessageMetadata>({});

    // Update metadata when model or configuration changes
    useEffect(() => {
        if (selectedModel && auth.isAuthenticated) {
            const newMetadata: LisaChatMessageMetadata = {
                modelName: selectedModel.modelId,
                modelKwargs: {
                    max_tokens: chatConfiguration.sessionConfiguration.max_tokens,
                    modelKwargs: chatConfiguration.sessionConfiguration.modelArgs,
                },
            };
            setMetadata(newMetadata);
        }
    }, [selectedModel, chatConfiguration.sessionConfiguration.max_tokens, chatConfiguration.sessionConfiguration.modelArgs, auth.isAuthenticated]);

    // Handle image input validation
    useEffect(() => {
        if (selectedModel &&
            selectedModel?.features?.filter((feature) => feature.name === 'imageInput')?.length === 0 &&
            extractImageDataUrlFromFileContext(fileContext)) {
            notificationService.generateNotification(
                'Removed file from context as new model doesn\'t support image input',
                'info'
            );
        }
    }, [selectedModel, fileContext, notificationService]);

    return {
        metadata,
    };
};

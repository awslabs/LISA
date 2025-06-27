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
import { LisaChatMessage } from '../../components/types';
import { IModel } from '@/shared/model/model-management.model';
import { RagConfig } from '@/components/chatbot/components/RagOptions';

export type IChatConfiguration = {
    promptConfiguration: IPromptConfiguration,
    sessionConfiguration: ISessionConfiguration,
};

export type IModelConfiguration = {
    selectedModel: IModel;
    ragConfig: RagConfig;
};

export type IPromptConfiguration = {
    promptTemplate: string;
};

export type ISessionConfiguration = {
    markdownDisplay: boolean
    streaming: boolean,
    showMetadata: boolean,
    max_tokens: number,
    chatHistoryBufferSize: number,
    ragTopK: number,
    modelArgs: {
        n: number;
        top_p: number;
        frequency_penalty: number;
        presence_penalty: number;
        temperature: number;
        seed: number;
        stop: string[];
    },
    imageGenerationArgs: {
        size: string,
        numberOfImages: number,
        quality: string,
    }
};

export type GenerateLLMRequestParams = {
    input: string,
    message: LisaChatMessage[]
};

export const DEFAULT_PROMPT_TEMPLATE = 'The following is a friendly conversation between a human and an AI. The AI is talkative and provides lots of specific details from its context. If the AI does not know the answer to a question, it truthfully says it does not know.';

export const baseConfig: IChatConfiguration = {
    promptConfiguration: {
        promptTemplate: DEFAULT_PROMPT_TEMPLATE,
    },
    sessionConfiguration: {
        streaming: false,
        markdownDisplay: true,
        showMetadata: false,
        max_tokens: null,
        chatHistoryBufferSize: 3,
        ragTopK: 3,
        modelArgs: {
            n: null,
            top_p: 0.01,
            frequency_penalty: null,
            presence_penalty: null,
            temperature: null,
            seed: null,
            stop: ['\nUser:', '\n User:', 'User:', 'User'],
        },
        imageGenerationArgs: {
            size: '1024x1024',
            numberOfImages: 1,
            quality: 'standard',
        }
    }
};

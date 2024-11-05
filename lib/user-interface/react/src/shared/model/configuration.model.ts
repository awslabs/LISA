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
import { z } from 'zod';

export type SystemConfiguration = {
    systemBanner: ISystemBannerConfiguration,
    enabledComponents: IEnabledComponents
};

export type IEnabledComponents = {
    deleteSessionHistory: boolean;
    viewMetaData: boolean;
    editKwargs: boolean;
    editPromptTemplate: boolean;
    editNumOfRagDocument: boolean;
    editChatHistoryBuffer: boolean;
    uploadRagDocs: boolean;
    uploadContextDocs: boolean;
};

export type ISystemBannerConfiguration = {
    isEnabled: boolean;
    text: string;
    textColor: string;
    backgroundColor: string;
};

export type BaseConfiguration = {
    configScope: string;
    versionId: number;
    createdAt?: number;
    changedBy: string;
    changeReason: string;
};

export type IConfiguration = BaseConfiguration & {
    configuration: SystemConfiguration;
};

export const systemBannerConfigSchema = z.object({
    isEnabled: z.boolean().default(false),
    text: z.string().default(''),
    textColor: z.string().default(''),
    backgroundColor: z.string().default(''),
}).refine((data) => !data.isEnabled || (data.isEnabled && data.text.length >= 1), {
    message: 'Text is required when banner is activated.',
    path: ['text']
});

export const enabledComponentsSchema = z.object({
    deleteSessionHistory: z.boolean().default(true),
    viewMetaData: z.boolean().default(true),
    editKwargs: z.boolean().default(true),
    editPromptTemplate: z.boolean().default(true),
    editChatHistoryBuffer: z.boolean().default(true),
    editNumOfRagDocument: z.boolean().default(true),
    uploadRagDocs: z.boolean().default(true),
    uploadContextDocs: z.boolean().default(true),
});

export const SystemConfigurationSchema = z.object({
    systemBanner: systemBannerConfigSchema.default(systemBannerConfigSchema.parse({})),
    enabledComponents: enabledComponentsSchema.default(enabledComponentsSchema.parse({})),
});

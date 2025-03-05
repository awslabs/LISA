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
import { RawConfigObject, RawConfigSchema } from './configSchema';

/**
 * Apply transformations to the raw application configuration schema.
 *
 * @param {Object} rawConfig - .describe('The raw application configuration.')
 * @returns {Object} The transformed application configuration.
 */
export const ConfigSchema = RawConfigSchema.transform((rawConfig) => {
    let deploymentPrefix = rawConfig.deploymentPrefix;

    if (!deploymentPrefix && rawConfig.appName && rawConfig.deploymentStage && rawConfig.deploymentName) {
        deploymentPrefix = `/${rawConfig.deploymentStage}/${rawConfig.deploymentName}/${rawConfig.appName}`;
    }

    let tags = rawConfig.tags;

    if (!tags && deploymentPrefix) {
        tags = [
            { Key: 'deploymentPrefix', Value: deploymentPrefix },
            { Key: 'deploymentName', Value: rawConfig.deploymentName },
            { Key: 'deploymentStage', Value: rawConfig.deploymentStage },
            { Key: 'region', Value: rawConfig.region }
        ];
    }

    let awsRegionArn;
    if (rawConfig.region.includes('iso-b')) {
        awsRegionArn = 'aws-iso-b';
    } else if (rawConfig.region.includes('iso')) {
        awsRegionArn = 'aws-iso';
    } else if (rawConfig.region.includes('gov')) {
        awsRegionArn = 'aws-gov';
    } else {
        awsRegionArn = 'aws';
    }

    return {
        ...rawConfig,
        deploymentPrefix: deploymentPrefix,
        tags: tags,
        awsRegionArn,
    };
});

/**
 * Application configuration type.
 */
export type Config = z.infer<typeof ConfigSchema>;

/**
 * Basic properties required for a stack definition in CDK.
 *
 * @property {Config} config - .describe('The application configuration.')
 */
export type BaseProps = {
    config: Config;
};

export type ConfigFile = Record<string, any>;

export const PartialConfigSchema = RawConfigObject.partial().transform((rawConfig) => {
    let deploymentPrefix = rawConfig.deploymentPrefix;

    if (!deploymentPrefix && rawConfig.appName && rawConfig.deploymentStage && rawConfig.deploymentName) {
        deploymentPrefix = `/${rawConfig.deploymentStage}/${rawConfig.deploymentName}/${rawConfig.appName}`;
    }

    let tags = rawConfig.tags;

    if (!tags && deploymentPrefix) {
        tags = [
            { Key: 'deploymentPrefix', Value: deploymentPrefix },
            { Key: 'deploymentName', Value: rawConfig.deploymentName! },
            { Key: 'deploymentStage', Value: rawConfig.deploymentStage! },
            { Key: 'region', Value: rawConfig.region! }
        ];
    }

    return {
        ...rawConfig,
        deploymentPrefix: deploymentPrefix,
        tags: tags,
    };
});

export type PartialConfig = z.infer<typeof PartialConfigSchema>;

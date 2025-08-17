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
import { SSMClient, GetParameterCommand, SSMServiceException } from '@aws-sdk/client-ssm';
import { EC2Client, DescribeSubnetsCommand } from '@aws-sdk/client-ec2';

async function resolveSSMParameter (name: string | undefined, region: string): Promise<string | undefined> {
    if (!name) return undefined;
    if (!name.startsWith('ssm:')) return undefined;

    const client = new SSMClient({ region: region });
    const command = new GetParameterCommand({ Name: name.split(':')[1] });
    return await client.send(command)
        .then((response) => {
            console.log('SSM Parameter Value:', response.Parameter?.Value);
            return response.Parameter?.Value;
        })
        .catch((error: SSMServiceException) => {
            console.error('Error fetching SSM parameter:', error);
            throw error;
        });
}

async function getSubnetData (subnetId: string, region: string) {
    const client = new EC2Client({ region: region });
    const command = new DescribeSubnetsCommand({ SubnetIds: [subnetId] });

    return await client.send(command)
        .then((response) => {
            return {
                subnetId: response.Subnets?.[0]?.SubnetId,
                ipv4CidrBlock: response.Subnets?.[0]?.CidrBlock,
                availabilityZone: response.Subnets?.[0]?.AvailabilityZone
            };
        })
        .catch((error) => {
            console.error('Error fetching subnet data:', error);
            throw error;
        });
}

async function resolveSubnets (name: string | { subnetId: string; ipv4CidrBlock: string; availabilityZone: string; }[] | undefined,
    region: string): Promise<{ subnetId: string; ipv4CidrBlock: string; availabilityZone: string; }[] | undefined> {
    if (typeof name === 'string') {
        const subnetList = (await resolveSSMParameter(name, region))?.split(',');
        if (subnetList && subnetList.length > 0) {
            const subnets = await Promise.all(
                subnetList.map(async (subnetId) => {
                    const subnet = await getSubnetData(subnetId, region);
                    if (!subnet.subnetId || !subnet.ipv4CidrBlock || !subnet.availabilityZone) {
                        throw new Error(`Incomplete subnet data for subnet ID ${subnetId}`);
                    }
                    return subnet as { subnetId: string; ipv4CidrBlock: string; availabilityZone: string; };
                })
            );
            return subnets;
        }
    }
    return undefined;
}

async function resolveSecurityGroups (
    securityGroupConfig: z.infer<typeof RawConfigSchema>['securityGroupConfig'],
    region: string
) {
    if (!securityGroupConfig) return undefined;

    const resolvedConfig = { ...securityGroupConfig };

    await Promise.all(
        Object.keys(securityGroupConfig).map(async (key) => {
            const typedKey = key as keyof typeof securityGroupConfig;
            const value = securityGroupConfig[typedKey];

            if (value) {
                const resolved = await resolveSSMParameter(value, region);
                if (resolved) {
                    resolvedConfig[typedKey] = resolved;
                }
            }
        })
    );

    return resolvedConfig;
}

/**
 * Apply transformations to the raw application configuration schema.
 *
 * @param {Object} rawConfig - .describe('The raw application configuration.')
 * @returns {Object} The transformed application configuration.
 */
export const ConfigSchema = RawConfigSchema.transform(async (rawConfig) => {
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

    const vpcId = await resolveSSMParameter(rawConfig.vpcId, rawConfig.region);
    const subnets = await resolveSubnets(rawConfig.subnets, rawConfig.region);
    const securityGroupConfig = await resolveSecurityGroups(rawConfig.securityGroupConfig, rawConfig.region);
    const webProxy = await resolveSSMParameter(rawConfig.webProxy, rawConfig.region);

    return {
        ...rawConfig,
        deploymentPrefix: deploymentPrefix,
        tags: tags,
        awsRegionArn,
        ...(vpcId && { vpcId }),
        ...(subnets && { subnets }),
        ...(securityGroupConfig && { securityGroupConfig }),
        ...(webProxy && { webProxy }),
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

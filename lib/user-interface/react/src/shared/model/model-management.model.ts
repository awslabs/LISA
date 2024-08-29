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
import { AttributeEditorSchema } from '../form/environment-variables';

export enum ModelStatus {
    Creating = 'Creating',
    InService = 'InService',
    Stopping = 'Stopping',
    Stopped = 'Stopped',
    Updating = 'Updating',
    Deleting = 'Deleting',
    Failed = 'Failed',
}

export enum ModelType {
    textgen = 'textgen',
    embedding = 'embedding',
}

export enum InferenceContainer {
    TGI = 'tgi',
    TEI = 'tei',
    VLLM = 'vllm',
    INSTRUCTOR = 'instructor',
}

export type IContainerHealthCheckConfig = {
    Command: string[];
    Interval: number;
    StartPeriod: number;
    Timeout: number;
    Retries: number;
};

export type IContainerConfigImage = {
    BaseImage: string;
    Path: string;
    Type: string;
};

export type IMetricConfig = {
    AlbMetricName: string;
    TargetValue: number;
    Duration: number;
    EstimatedInstanceWarmup: number;
};

export type ILoadBalancerHealthCheckConfig = {
    Path: string;
    Interval: number;
    Timeout: number;
    HealthyThresholdCount: number;
    UnhealthyThresholdCount: number;
};

export type ILoadBalancerConfig = {
    HealthCheckConfig: ILoadBalancerHealthCheckConfig
};

export type IAutoScalingConfig = {
    MinCapacity: number;
    MaxCapacity: number;
    Cooldown: number;
    DefaultInstanceWarmup: number;
    MetricConfig: IMetricConfig;
};

export type IContainerConfig = {
    BaseImage: IContainerConfigImage;
    SharedMemorySize: number;
    HealthCheckConfig: IContainerHealthCheckConfig;
    Environment?: Record<string, string>[];
};

export type IModel = {
    UniqueId: string;
    ModelId: string;
    ModelName: string;
    ModelUrl: string;
    Streaming: boolean;
    ModelType: ModelType;
    InstanceType: string;
    InferenceContainer: InferenceContainer;
    ContainerConfig: IContainerConfig;
    AutoScalingConfig: IAutoScalingConfig;
    LoadBalancerConfig: ILoadBalancerConfig;
};

export type IModelListResponse = {
    Models: IModel[];
};

export type IModelRequest = {
    UniqueId: string;
    ModelId: string;
    ModelName: string;
    ModelUrl: string;
    Streaming: boolean;
    ModelType: ModelType;
    InstanceType: string;
    InferenceContainer: InferenceContainer;
    ContainerConfig: IContainerConfig;
    AutoScalingConfig: IAutoScalingConfig;
    LoadBalancerConfig: ILoadBalancerConfig;
};

const containerHealthCheckConfigSchema = z.object({
    Command: z.array(z.string()).default(['CMD-SHELL', 'exit 0']),
    Interval: z.number().default(10),
    StartPeriod: z.number().default(30),
    Timeout: z.number().default(5),
    Retries: z.number().default(2),
});


const containerConfigImageSchema = z.object({
    BaseImage: z.string().default(''),
    Path: z.string().default(''),
    Type: z.string().default(''),
});

export const metricConfigSchema = z.object({
    AlbMetricName: z.string().default(''),
    TargetValue: z.number().default(0),
    Duration: z.number().default(60),
    EstimatedInstanceWarmup: z.number().default(180),
});

export const loadBalancerHealthCheckConfigSchema = z.object({
    Path: z.string().default(''),
    Interval: z.number().default(10),
    Timeout: z.number().default(5),
    HealthyThresholdCount: z.number().default(1),
    UnhealthyThresholdCount: z.number().default(1),
});

export const loadBalancerConfigSchema = z.object({
    HealthCheckConfig: loadBalancerHealthCheckConfigSchema.default(loadBalancerHealthCheckConfigSchema.parse({})),
});

export const autoScalingConfigSchema = z.object({
    MinCapacity: z.number().min(1).default(1),
    MaxCapacity: z.number().min(1).default(2),
    Cooldown: z.number().min(1).default(420),
    DefaultInstanceWarmup: z.number().default(180),
    MetricConfig: metricConfigSchema.default(metricConfigSchema.parse({})),
});

export const containerConfigSchema = z.object({
    BaseImage: containerConfigImageSchema.default(containerConfigImageSchema.parse({})),
    SharedMemorySize: z.number().min(0).default(0),
    HealthCheckConfig: containerHealthCheckConfigSchema.default(containerHealthCheckConfigSchema.parse({})),
    Environment: AttributeEditorSchema,
});

export const ModelRequestSchema = z.object({
    ModelId: z.string().default(''),
    ModelName: z.string().default(''),
    ModelUrl: z.string().default(''),
    Streaming: z.boolean().default(true),
    ModelType: z.nativeEnum(ModelType).default(ModelType.textgen),
    InstanceType: z.string().default(''),
    InferenceContainer: z.nativeEnum(InferenceContainer).optional(),
    ContainerConfig: containerConfigSchema.default(containerConfigSchema.parse({})),
    AutoScalingConfig: autoScalingConfigSchema.default(autoScalingConfigSchema.parse({})),
    LoadBalancerConfig: loadBalancerConfigSchema.default(loadBalancerConfigSchema.parse({})),
});

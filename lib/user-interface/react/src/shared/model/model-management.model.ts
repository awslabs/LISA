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
import { IChatConfiguration } from './chat.configurations.model';

export enum ModelStatus {
    Creating = 'Creating',
    InService = 'InService',
    Stopping = 'Stopping',
    Starting = 'Starting',
    Stopped = 'Stopped',
    Updating = 'Updating',
    Deleting = 'Deleting',
    Failed = 'Failed',
}

export enum ModelType {
    textgen = 'textgen',
    embedding = 'embedding',
    imagegen = 'imagegen'
}

export enum InferenceContainer {
    TGI = 'tgi',
    TEI = 'tei',
    VLLM = 'vllm',
    INSTRUCTOR = 'instructor',
}

export type IContainerHealthCheckConfig = {
    command: string[];
    interval: number;
    startPeriod: number;
    timeout: number;
    retries: number;
};

export type IContainerConfigImage = {
    baseImage: string;
    type: string;
};

export type IMetricConfig = {
    albMetricName: string;
    targetValue: number;
    duration: number;
    estimatedInstanceWarmup: number;
};

export type ILoadBalancerHealthCheckConfig = {
    path: string;
    interval: number;
    timeout: number;
    healthyThresholdCount: number;
    unhealthyThresholdCount: number;
};

export type ILoadBalancerConfig = {
    healthCheckConfig: ILoadBalancerHealthCheckConfig
};

export type IAutoScalingConfig = {
    blockDeviceVolumeSize: number;
    minCapacity: number;
    maxCapacity: number;
    desiredCapacity?: number;
    cooldown: number;
    defaultInstanceWarmup: number;
    metricConfig: IMetricConfig;
};

export type IContainerConfig = {
    image: IContainerConfigImage;
    sharedMemorySize: number;
    healthCheckConfig: IContainerHealthCheckConfig;
    environment?: Record<string, string>[];
};

export type IModel = {
    status?: ModelStatus;
    features?: ModelFeature[];
    modelId: string;
    modelName: string;
    modelUrl: string;
    modelConfig: IChatConfiguration;
    streaming: boolean;
    modelType: ModelType;
    instanceType: string;
    inferenceContainer: InferenceContainer;
    containerConfig: IContainerConfig;
    autoScalingConfig: IAutoScalingConfig;
    loadBalancerConfig: ILoadBalancerConfig;
};

export type IModelListResponse = {
    models: IModel[];
};

export type IModelRequest = {
    features: ModelFeature[];
    modelId: string;
    modelName: string;
    modelUrl: string;
    streaming: boolean;
    multiModal: boolean;
    modelType: ModelType;
    instanceType: string;
    inferenceContainer: InferenceContainer;
    containerConfig: IContainerConfig;
    autoScalingConfig: IAutoScalingConfig;
    loadBalancerConfig: ILoadBalancerConfig;
    lisaHostedModel: boolean;
};

export type ModelFeature = {
    name: string;
    overview: string;
};

export type IModelUpdateRequest = {
    modelId: string;
    streaming?: boolean;
    enabled?: boolean;
    modelType?: ModelType;
    autoScalingInstanceConfig?: IAutoScalingConfig;
};

const containerHealthCheckConfigSchema = z.object({
    command: z.array(z.string()).default(['CMD-SHELL', 'exit 0']),
    interval: z.number().default(10),
    startPeriod: z.number().default(30),
    timeout: z.number().default(5),
    retries: z.number().default(3),
});


const containerConfigImageSchema = z.object({
    baseImage: z.string().default(''),
    type: z.string().default('asset'),
});

export const metricConfigSchema = z.object({
    albMetricName: z.string().default('RequestCountPerTarget'),
    targetValue: z.number().default(30),
    duration: z.number().default(60),
    estimatedInstanceWarmup: z.number().default(330),
});

export const loadBalancerHealthCheckConfigSchema = z.object({
    path: z.string().default('/health'),
    interval: z.number().default(60),
    timeout: z.number().default(30),
    healthyThresholdCount: z.number().default(2),
    unhealthyThresholdCount: z.number().default(10),
});

export const loadBalancerConfigSchema = z.object({
    healthCheckConfig: loadBalancerHealthCheckConfigSchema.default(loadBalancerHealthCheckConfigSchema.parse({})),
});

export const autoScalingConfigSchema = z.object({
    blockDeviceVolumeSize: z.number().min(30).default(30),
    minCapacity: z.number().min(1).default(1),
    maxCapacity: z.number().min(1).default(1),
    desiredCapacity: z.number().optional(),
    cooldown: z.number().min(1).default(420),
    defaultInstanceWarmup: z.number().default(180),
    metricConfig: metricConfigSchema.default(metricConfigSchema.parse({})),
}).superRefine((value, context) => {
    // ensure the desired capacity stays between minCapacity/maxCapacity if not empty
    if (value.desiredCapacity !== undefined && String(value.desiredCapacity).trim().length) {
        const validator = z.number().min(Number(value.minCapacity)).max(Number(value.maxCapacity));
        const result = validator.safeParse(value.desiredCapacity);
        if (result.success === false) {
            for (const error of result.error.errors) {
                context.addIssue({
                    ...error,
                    path: ['desiredCapacity']
                });
            }
        }
    }
});

export const containerConfigSchema = z.object({
    image: containerConfigImageSchema.default(containerConfigImageSchema.parse({})),
    sharedMemorySize: z.number().min(0).default(2048),
    healthCheckConfig: containerHealthCheckConfigSchema.default(containerHealthCheckConfigSchema.parse({})),
    environment: AttributeEditorSchema,
});

export const ModelRequestSchema = z.object({
    modelId: z.string()
        .regex(/^[a-z\d-]+$/i, {message: 'Only alphanumeric characters and hyphens allowed'})
        .regex(/^[a-z0-9].*[a-z0-9]$/i, {message: 'Must start and end with an alphanumeric character.'})
        .default(''),
    modelName: z.string().min(1).default(''),
    modelUrl: z.string().default(''),
    streaming: z.boolean().default(false),
    features: z.array(z.object({
        name: z.string(),
        overview: z.string()
    })).default([]),
    lisaHostedModel: z.boolean().default(false),
    modelType: z.nativeEnum(ModelType).default(ModelType.textgen),
    instanceType: z.string().default(''),
    inferenceContainer: z.nativeEnum(InferenceContainer).optional(),
    containerConfig: containerConfigSchema.default(containerConfigSchema.parse({})),
    autoScalingConfig: autoScalingConfigSchema.default(autoScalingConfigSchema.parse({})),
    loadBalancerConfig: loadBalancerConfigSchema.default(loadBalancerConfigSchema.parse({})),
}).superRefine((value, context) => {
    if (value.lisaHostedModel) {
        const instanceTypeValidator = z.string().min(1, {message: 'Required for LISA hosted models.'});
        const instanceTypeResult = instanceTypeValidator.safeParse(value.instanceType);
        if (instanceTypeResult.success === false) {
            for (const error of instanceTypeResult.error.errors) {
                context.addIssue({
                    ...error,
                    path: ['instanceType']
                });
            }
        }

        const inferenceContainerValidator = z.nativeEnum(InferenceContainer, {required_error: 'Required for LISA hosted models.'});
        const inferenceContainerResult = inferenceContainerValidator.safeParse(value.inferenceContainer);
        if (inferenceContainerResult.success === false) {
            for (const error of inferenceContainerResult.error.errors) {
                context.addIssue({
                    ...error,
                    path: ['inferenceContainer']
                });
            }
        }

        const baseImageValidator = z.string().min(1, {message: 'Required for LISA hosted models.'});
        const baseImageResult = baseImageValidator.safeParse(value.containerConfig.image.baseImage);
        if (baseImageResult.success === false) {
            for (const error of baseImageResult.error.errors) {
                context.addIssue({
                    ...error,
                    path: ['containerConfig', 'image', 'baseImage']
                });
            }
        }
    }
});

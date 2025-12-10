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

export enum ScheduleType {
    NONE = 'NONE',
    DAILY = 'DAILY',
    RECURRING = 'RECURRING'
}

export enum GuardrailMode {
    PRE_CALL = 'pre_call',
    DURING_CALL = 'during_call',
    POST_CALL = 'post_call'
}

export type IGuardrailConfig = {
    guardrailName: string;
    guardrailIdentifier: string;
    guardrailVersion: string;
    mode: GuardrailMode;
    description?: string;
    allowedGroups: string[];
    markedForDeletion?: boolean;
};

export type IGuardrailsConfig = Record<string, IGuardrailConfig>;

export type IGuardrailResponse = {
    modelId: string;
    guardrailsConfig: IGuardrailsConfig;
    success: boolean;
    message: string;
};

export type IGuardrailRequest = {
    modelId: string;
    guardrailsConfig: IGuardrailsConfig;
};

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

export type IDaySchedule = {
    startTime: string;
    stopTime: string;
};

export type IWeeklySchedule = {
    monday?: IDaySchedule;
    tuesday?: IDaySchedule;
    wednesday?: IDaySchedule;
    thursday?: IDaySchedule;
    friday?: IDaySchedule;
    saturday?: IDaySchedule;
    sunday?: IDaySchedule;
};

// Base interface for common schedule fields
type IBaseScheduleConfig = {
    scheduleEnabled: boolean;
    timezone: string;
    nextScheduledAction?: string;
    lastScheduleUpdate?: string;
    scheduleStatus?: string;
    scheduleConfigured?: boolean;
    lastScheduleFailed?: boolean;
    scheduledActionArns?: string[];
};

// Discriminated union for schedule configurations
export type IScheduleConfig =
    | (IBaseScheduleConfig & {
        scheduleType: ScheduleType.DAILY;
        dailySchedule: IWeeklySchedule;
        recurringSchedule?: never;
    })
    | (IBaseScheduleConfig & {
        scheduleType: ScheduleType.RECURRING;
        recurringSchedule: IDaySchedule;
        dailySchedule?: never;
    })
    | (IBaseScheduleConfig & {
        scheduleType: ScheduleType.NONE;
        dailySchedule?: never;
        recurringSchedule?: never;
    });

export type IAutoScalingConfig = {
    blockDeviceVolumeSize: number;
    minCapacity: number;
    maxCapacity: number;
    desiredCapacity?: number;
    cooldown: number;
    defaultInstanceWarmup: number;
    metricConfig: IMetricConfig;
    scheduling?: IScheduleConfig;
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
    modelDescription?: string;
    modelUrl: string;
    modelConfig: IChatConfiguration;
    streaming: boolean;
    modelType: ModelType;
    instanceType: string;
    inferenceContainer: InferenceContainer;
    containerConfig: IContainerConfig;
    autoScalingConfig: IAutoScalingConfig;
    loadBalancerConfig: ILoadBalancerConfig;
    allowedGroups?: string[];
};

export type IModelListResponse = {
    models: IModel[];
};

export type IModelRequest = {
    features: ModelFeature[];
    modelId: string;
    modelName: string;
    modelDescription?: string;
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
    allowedGroups?: string[];
    apiKey?: string;
    guardrailsConfig?: IGuardrailsConfig;
};

export type ModelFeature = {
    name: string;
    overview: string;
};

export type IAutoScalingInstanceConfig = {
    minCapacity?: number;
    maxCapacity?: number;
    desiredCapacity?: number;
    cooldown?: number;
    defaultInstanceWarmup?: number;
};

export type IModelUpdateRequest = {
    modelId: string;
    streaming?: boolean;
    enabled?: boolean;
    modelType?: ModelType;
    modelDescription?: string;
    allowedGroups?: string[];
    features?: ModelFeature[];
    autoScalingInstanceConfig?: IAutoScalingInstanceConfig;
    containerConfig?: IContainerConfig;
    guardrailsConfig?: IGuardrailsConfig;
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

const dayScheduleSchema = z.object({
    startTime: z.string().regex(/^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$/, 'Must be in HH:MM format'),
    stopTime: z.string().regex(/^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$/, 'Must be in HH:MM format'),
}).superRefine((value, context) => {
    // Validate that start time is before stop time and at least 2 hours apart
    const [startHour, startMin] = value.startTime.split(':').map(Number);
    const [stopHour, stopMin] = value.stopTime.split(':').map(Number);
    const startMinutes = startHour * 60 + startMin;
    const stopMinutes = stopHour * 60 + stopMin;

    // Handle next day scenarios
    const actualStopMinutes = stopMinutes <= startMinutes ? stopMinutes + 24 * 60 : stopMinutes;
    const duration = actualStopMinutes - startMinutes;

    if (duration < 120) {
        context.addIssue({
            code: z.ZodIssueCode.custom,
            message: 'Suspension time must be at least 2 hours after start time',
            path: ['stopTime']
        });
    }
});

const weeklyScheduleSchema = z.object({
    monday: dayScheduleSchema.optional(),
    tuesday: dayScheduleSchema.optional(),
    wednesday: dayScheduleSchema.optional(),
    thursday: dayScheduleSchema.optional(),
    friday: dayScheduleSchema.optional(),
    saturday: dayScheduleSchema.optional(),
    sunday: dayScheduleSchema.optional(),
});

// Base schema for common schedule fields
const baseScheduleConfigSchema = z.object({
    scheduleEnabled: z.boolean().default(false),
    timezone: z.string().default('UTC'),
    nextScheduledAction: z.string().optional(),
    lastScheduleUpdate: z.string().optional(),
    scheduleStatus: z.string().optional(),
    scheduleConfigured: z.boolean().optional(),
    lastScheduleFailed: z.boolean().optional(),
    scheduledActionArns: z.array(z.string()).optional(),
});

// Discriminated union schema for schedule configurations
export const scheduleConfigSchema = z.discriminatedUnion('scheduleType', [
    // DAILY schedule type
    baseScheduleConfigSchema.extend({
        scheduleType: z.literal(ScheduleType.DAILY),
        dailySchedule: weeklyScheduleSchema.superRefine((value, context) => {
            // Check that at least one day has schedules
            const hasAnySchedule = Object.values(value).some(
                (daySchedule) => daySchedule && daySchedule.startTime && daySchedule.stopTime
            );
            if (!hasAnySchedule) {
                context.addIssue({
                    code: z.ZodIssueCode.custom,
                    message: 'At least one day must have a schedule configured',
                    path: []
                });
            }
        }),
    }),

    // RECURRING schedule type
    baseScheduleConfigSchema.extend({
        scheduleType: z.literal(ScheduleType.RECURRING),
        recurringSchedule: dayScheduleSchema,
    }),

    // NONE schedule type
    baseScheduleConfigSchema.extend({
        scheduleType: z.literal(ScheduleType.NONE),
    })
]).superRefine((value, context) => {
    // Validate timezone when scheduling is enabled
    if (value.scheduleEnabled && value.scheduleType !== ScheduleType.NONE) {
        if (!value.timezone || value.timezone === '') {
            context.addIssue({
                code: z.ZodIssueCode.custom,
                message: 'Timezone is required when auto scaling is enabled',
                path: ['timezone']
            });
        }
    }
});

export const autoScalingConfigSchema = z.object({
    blockDeviceVolumeSize: z.number().min(30).default(50),
    minCapacity: z.number().min(1).default(1),
    maxCapacity: z.number().min(1).default(1),
    desiredCapacity: z.number().optional(),
    cooldown: z.number().min(1).default(420),
    defaultInstanceWarmup: z.number().default(180),
    metricConfig: metricConfigSchema.default(metricConfigSchema.parse({})),
    scheduling: scheduleConfigSchema.optional(),
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

export const guardrailConfigSchema = z.object({
    guardrailName: z.string().min(1, {message: 'Guardrail name is required'}).default(''),
    guardrailIdentifier: z.string().min(1, {message: 'Guardrail identifier is required'}).default(''),
    guardrailVersion: z.string().default('DRAFT'),
    mode: z.nativeEnum(GuardrailMode).default(GuardrailMode.PRE_CALL),
    description: z.string().optional(),
    allowedGroups: z.array(z.string()).default([]),
});

export const guardrailsConfigSchema = z.record(z.string(), guardrailConfigSchema).default({});

export const containerConfigSchema = z.object({
    image: containerConfigImageSchema.default(containerConfigImageSchema.parse({})),
    sharedMemorySize: z.number().min(0).default(2048),
    healthCheckConfig: containerHealthCheckConfigSchema.default(containerHealthCheckConfigSchema.parse({})),
    environment: AttributeEditorSchema,
});

export const ModelRequestSchema = z.object({
    modelId: z.string()
        .regex(/^[a-z\d-]+$/, {message: 'Only lowercase alphanumeric characters and hyphens allowed'})
        .regex(/^[a-z0-9].*[a-z0-9]$/, {message: 'Must start and end with a lowercase alphanumeric character.'})
        .default(''),
    modelName: z.string().min(1).default(''),
    modelDescription: z.string().default(''),
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
    allowedGroups: z.array(z.string()).default([]),
    guardrailsConfig: guardrailsConfigSchema.optional(),
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

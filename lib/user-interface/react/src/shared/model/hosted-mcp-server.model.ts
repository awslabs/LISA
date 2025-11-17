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

export enum HostedMcpServerStatus {
    Creating = 'Creating',
    InService = 'InService',
    Starting = 'Starting',
    Stopping = 'Stopping',
    Stopped = 'Stopped',
    Updating = 'Updating',
    Deleting = 'Deleting',
    Failed = 'Failed',
}

export type HostedMcpAutoScalingConfig = {
    minCapacity: number;
    maxCapacity: number;
    targetValue?: number;
    metricName?: string;
    duration?: number;
    cooldown?: number;
};

export type HostedMcpLoadBalancerHealthCheckConfig = {
    path: string;
    interval: number;
    timeout: number;
    healthyThresholdCount: number;
    unhealthyThresholdCount: number;
};

export type HostedMcpLoadBalancerConfig = {
    healthCheckConfig: HostedMcpLoadBalancerHealthCheckConfig;
};

export type HostedMcpContainerHealthCheckConfig = {
    command: string | string[];
    interval: number;
    startPeriod: number;
    timeout: number;
    retries: number;
};

export type HostedMcpServer = {
    id: string;
    name: string;
    description?: string;
    owner: string;
    created?: string;
    status?: HostedMcpServerStatus;
    startCommand: string;
    serverType: 'stdio' | 'http' | 'sse';
    port?: number;
    autoScalingConfig: HostedMcpAutoScalingConfig;
    containerHealthCheckConfig?: HostedMcpContainerHealthCheckConfig;
    loadBalancerConfig?: HostedMcpLoadBalancerConfig;
    groups?: string[];
    environment?: Record<string, string>;
    image?: string;
    s3Path?: string;
    taskExecutionRoleArn?: string;
    taskRoleArn?: string;
    cpu?: number;
    memoryLimitMiB?: number;
    stack_name?: string;
};

export type HostedMcpServerRequest = Omit<HostedMcpServer, 'id' | 'owner' | 'created' | 'status' | 'stack_name'>;

export type HostedMcpServerListResponse = {
    Items: HostedMcpServer[];
};

// Zod Schemas
const hostedMcpContainerHealthCheckConfigSchema = z.object({
    command: z.union([z.string(), z.array(z.string())]).default('CMD-SHELL curl --fail http://localhost:{{PORT}}/status || exit 1'),
    interval: z.number().min(1).default(30),
    startPeriod: z.number().min(0).default(180),
    timeout: z.number().min(1).default(10),
    retries: z.number().min(1).default(3),
});

const hostedMcpLoadBalancerHealthCheckConfigSchema = z.object({
    path: z.string().min(1).default('/status'),
    interval: z.number().min(1).default(30),
    timeout: z.number().min(1).default(5),
    healthyThresholdCount: z.number().min(1).default(3),
    unhealthyThresholdCount: z.number().min(1).default(3),
});

const hostedMcpLoadBalancerConfigSchema = z.object({
    healthCheckConfig: hostedMcpLoadBalancerHealthCheckConfigSchema.default(hostedMcpLoadBalancerHealthCheckConfigSchema.parse({})),
});

const hostedMcpAutoScalingConfigSchema = z.object({
    minCapacity: z.number().min(1).default(1),
    maxCapacity: z.number().min(1).default(1),
    targetValue: z.number().optional().default(10),
    metricName: z.string().optional().default('RequestCountPerTarget'),
    duration: z.number().optional().default(60),
    cooldown: z.number().optional().default(60),
}).superRefine((value, context) => {
    if (value.minCapacity > value.maxCapacity) {
        context.addIssue({
            code: z.ZodIssueCode.custom,
            message: 'Minimum capacity must be less than or equal to maximum capacity',
            path: ['maxCapacity'],
        });
    }
});

export const HostedMcpServerRequestSchema = z.object({
    name: z.string().min(1, { message: 'Name is required' }).default(''),
    description: z.string().optional().default(''),
    startCommand: z.string().min(1, { message: 'Start command is required' }).default(''),
    serverType: z.enum(['stdio', 'http', 'sse']).default('stdio'),
    port: z.number().optional(),
    cpu: z.number().min(256).default(256),
    memoryLimitMiB: z.number().min(512).default(512),
    autoScalingConfig: hostedMcpAutoScalingConfigSchema.default(hostedMcpAutoScalingConfigSchema.parse({})),
    containerHealthCheckConfig: hostedMcpContainerHealthCheckConfigSchema.optional(),
    loadBalancerConfig: hostedMcpLoadBalancerConfigSchema.optional(),
    groups: z.array(z.string()).optional().default([]),
    environment: AttributeEditorSchema,
    image: z.string().optional(),
    s3Path: z.string().optional(),
    taskExecutionRoleArn: z.string().optional(),
    taskRoleArn: z.string().optional(),
});

export type HostedMcpServerRequestForm = z.infer<typeof HostedMcpServerRequestSchema>;

export const DEFAULT_HOSTED_MCP_SERVER_REQUEST: HostedMcpServerRequest = {
    name: '',
    description: '',
    startCommand: '',
    serverType: 'stdio',
    port: undefined,
    autoScalingConfig: {
        minCapacity: 1,
        maxCapacity: 1,
        targetValue: 10,
        metricName: 'RequestCountPerTarget',
        duration: 60,
        cooldown: 60,
    },
    containerHealthCheckConfig: undefined,
    loadBalancerConfig: undefined,
    groups: [],
    environment: undefined,
    image: undefined,
    s3Path: undefined,
    taskExecutionRoleArn: undefined,
    taskRoleArn: undefined,
    cpu: 256,
    memoryLimitMiB: 512,
};

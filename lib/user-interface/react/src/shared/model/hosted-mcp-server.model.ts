/**
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License").
 * You may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

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


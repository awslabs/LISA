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

import { HostedMcpServer, HostedMcpServerRequest, HostedMcpServerRequestForm } from '@/shared/model/hosted-mcp-server.model';

/**
 * Normalizes health check command to API format
 */
export function normalizeHealthCheckCommand (rawCommand: string): string | string[] {
    const trimmed = rawCommand.trim();
    if (!trimmed) return trimmed;
    const prefixRegex = /^cmd-shell\b/i;
    if (prefixRegex.test(trimmed)) {
        const remainder = trimmed.replace(prefixRegex, '').trim();
        return remainder ? ['CMD-SHELL', remainder] : ['CMD-SHELL'];
    }
    return trimmed;
}

/**
 * Converts form data to API payload for submission
 */
export function formToPayload (
    form: HostedMcpServerRequestForm,
    isEdit: boolean,
    selectedServer?: HostedMcpServer | null
): HostedMcpServerRequest {
    // Handle environment variables
    const environment = form.environment?.length
        ? form.environment.reduce((acc, { key, value }) => {
            if (key?.trim()) {
                acc[key.trim()] = value;
            }
            return acc;
        }, {} as Record<string, string>)
        : undefined;

    // For edit mode, mark deletions
    const finalEnvironment = isEdit && selectedServer ? (() => {
        const originalEnv = selectedServer.environment || {};
        const result: any = environment || {};
        const currentKeys = new Set(Object.keys(result));

        Object.keys(originalEnv).forEach((key) => {
            if (!currentKeys.has(key)) {
                result[key] = 'LISA_MARKED_FOR_DELETION';
            }
        });
        return result;
    })() : environment;

    // Replace {{PORT}} placeholder in health check command
    const resolvedPort = form.port || (form.serverType === 'stdio' ? 8080 : 8000);
    const healthCheckCommand = form.containerHealthCheckConfig?.command || '';
    const commandWithPort = typeof healthCheckCommand === 'string'
        ? healthCheckCommand.replace(/\{\{PORT\}\}/g, String(resolvedPort))
        : healthCheckCommand;

    return {
        name: form.name,
        description: form.description || undefined,
        startCommand: form.startCommand,
        serverType: form.serverType,
        port: form.port,
        cpu: form.cpu,
        memoryLimitMiB: form.memoryLimitMiB,
        autoScalingConfig: {
            minCapacity: form.autoScalingConfig.minCapacity,
            maxCapacity: form.autoScalingConfig.maxCapacity,
            targetValue: form.autoScalingConfig.targetValue,
            metricName: form.autoScalingConfig.metricName,
            duration: form.autoScalingConfig.duration,
            cooldown: form.autoScalingConfig.cooldown,
        },
        containerHealthCheckConfig: form.containerHealthCheckConfig
            ? {
                command: normalizeHealthCheckCommand(commandWithPort as string),
                interval: form.containerHealthCheckConfig.interval,
                timeout: form.containerHealthCheckConfig.timeout,
                retries: form.containerHealthCheckConfig.retries,
                startPeriod: form.containerHealthCheckConfig.startPeriod,
            }
            : undefined,
        loadBalancerConfig: form.loadBalancerConfig
            ? {
                healthCheckConfig: {
                    path: form.loadBalancerConfig.healthCheckConfig.path,
                    interval: form.loadBalancerConfig.healthCheckConfig.interval,
                    timeout: form.loadBalancerConfig.healthCheckConfig.timeout,
                    healthyThresholdCount: form.loadBalancerConfig.healthCheckConfig.healthyThresholdCount,
                    unhealthyThresholdCount: form.loadBalancerConfig.healthCheckConfig.unhealthyThresholdCount,
                }
            }
            : undefined,
        groups: form.groups,
        environment: finalEnvironment,
        image: form.image || undefined,
        s3Path: form.s3Path || undefined,
        taskExecutionRoleArn: form.taskExecutionRoleArn || undefined,
        taskRoleArn: form.taskRoleArn || undefined,
    };
}

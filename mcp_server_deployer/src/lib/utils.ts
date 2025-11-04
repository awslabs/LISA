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

/**
 * Load balancer health check configuration
 */
export type LoadBalancerHealthCheckConfig = {
    path: string;
    interval: number;
    timeout: number;
    healthyThresholdCount: number;
    unhealthyThresholdCount: number;
};

/**
 * Load balancer configuration
 */
export type LoadBalancerConfig = {
    healthCheckConfig: LoadBalancerHealthCheckConfig;
};

/**
 * Container health check configuration
 */
export type ContainerHealthCheckConfig = {
    command: string | string[];
    interval: number;
    startPeriod: number;
    timeout: number;
    retries: number;
};

/**
 * MCP Server Configuration from event payload
 */
export type McpServerConfig = {
    name: string;
    id: string;
    startCommand: string;
    port?: number;
    autoScalingConfig: {
        minCapacity: number;
        maxCapacity: number;
        targetValue?: number;
        metricName?: string;
        duration?: number;
        cooldown?: number;
    };
    loadBalancerConfig?: LoadBalancerConfig;
    containerHealthCheckConfig?: ContainerHealthCheckConfig;
    groups?: string[];
    s3Path?: string;
    serverType?: 'stdio' | 'http' | 'sse';
    image?: string;
    environment?: Record<string, string>;
    taskExecutionRoleArn?: string;
    taskRoleArn?: string;
};

/**
 * Creates a normalized identifier based on the provided MCP server config.
 * Strips all non-alphanumeric characters for use in CDK identifiers/resource names.
 *
 * @param {McpServerConfig} mcpServerConfig - MCP server configuration
 * @returns {string} normalized server identifier
 */
export function getMcpServerIdentifier (mcpServerConfig: McpServerConfig): string {
    return (mcpServerConfig.id || mcpServerConfig.name).replace(/[^a-zA-Z0-9]/g, '');
}

/**
 * Detects the server type from the configuration.
 * Priority: explicit serverType > port-based detection > command-based detection
 *
 * @param {McpServerConfig} mcpServerConfig - MCP server configuration
 * @returns {'stdio' | 'http' | 'sse'} detected server type
 */
export function detectServerType (mcpServerConfig: McpServerConfig): 'stdio' | 'http' | 'sse' {
    // If explicitly provided, use it
    if (mcpServerConfig.serverType) {
        return mcpServerConfig.serverType;
    }

    // If port is provided, assume HTTP
    if (mcpServerConfig.port) {
        return 'http';
    }

    // Check command for SSE keywords
    const command = mcpServerConfig.startCommand.toLowerCase();
    if (command.includes('sse') || command.includes('server-sent')) {
        return 'sse';
    }

    // Default to STDIO if no port and no explicit type
    return 'stdio';
}

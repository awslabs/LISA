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

import { McpServerConfig } from './utils';

/**
 * Utility class for generating entrypoint scripts for MCP server containers
 */
export class DockerfileBuilder {
    /**
     * Generates entrypoint script for STDIO servers with mcp-proxy
     */
    static generateStdioEntrypointScript (mcpServerConfig: McpServerConfig): string {
        const startCommand = mcpServerConfig.startCommand;
        // Use environment variables that will be set at runtime
        const s3Bucket = '${S3_BUCKET}';
        const s3Path = '${S3_PATH}';

        return `#!/bin/bash
set -e

# Download server files from S3 if configured
if [ -n "${s3Bucket}" ] && [ -n "${s3Path}" ]; then
    echo "Downloading server files from s3://${s3Bucket}/${s3Path}..."
    aws s3 sync "s3://${s3Bucket}/${s3Path}" /app/server/
    chmod +x /app/server/* 2>/dev/null || true
fi

# Change to server directory if files were downloaded
if [ -d /app/server ] && [ "$(ls -A /app/server)" ]; then
    cd /app/server
fi

# Start mcp-proxy with the server command
# mcp-proxy expects the command as a positional argument (after --port and --host)
# The command can contain spaces, so we execute it properly
exec /root/.local/bin/mcp-proxy \\
    --stateless \\
    --transport streamablehttp \\
    --allow-origins="*" \\
    --port=8080 \\
    --host=0.0.0.0 \\
    ${startCommand}
`;
    }

    /**
     * Generates entrypoint script for HTTP/SSE servers
     */
    static generateEntrypointScript (mcpServerConfig: McpServerConfig): string {
        const startCommand = mcpServerConfig.startCommand;
        // Use environment variables that will be set at runtime
        const s3Bucket = '${S3_BUCKET}';
        const s3Path = '${S3_PATH}';

        return `#!/bin/bash
set -e

# Download server files from S3 if configured
if [ -n "${s3Bucket}" ] && [ -n "${s3Path}" ]; then
    echo "Downloading server files from s3://${s3Bucket}/${s3Path}..."
    aws s3 sync "s3://${s3Bucket}/${s3Path}" /app/server/
    chmod +x /app/server/* 2>/dev/null || true

    # Add server directory to PATH
    export PATH="/app/server:$PATH"
fi

# Change to server directory if files were downloaded, otherwise stay in /app
if [ -d /app/server ] && [ "$(ls -A /app/server)" ]; then
    cd /app/server
else
    cd /app
fi

# Execute the start command
exec ${startCommand}
`;
    }
}

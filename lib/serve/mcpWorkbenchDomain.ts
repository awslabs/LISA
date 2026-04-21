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
 * When `restApiConfig.domainName` is set, MCP Workbench must not reuse that hostname: it runs on a
 * separate ALB, and DNS for the Serve API name targets the Serve load balancer only.
 *
 * If `mcpWorkbenchRestApiConfig.domainName` and `mcpWorkbenchEcsConfig.domainName` are omitted, derive a conventional workbench hostname so HTTPS
 * (shared ACM cert / wildcard) and SSM `…/mcpWorkbench/endpoint` stay consistent:
 * - First label ends with `-serve` → replace that suffix with `-mcp-workbench` (e.g. `lisa-serve.example` → `lisa-mcp-workbench.example`).
 * - First label is exactly `serve` → use `mcp-workbench` (e.g. `serve.alias.example` → `mcp-workbench.alias.example`).
 *
 * Otherwise returns null so the workbench ALB DNS name is used (operators should set `mcpWorkbenchRestApiConfig.domainName` or `mcpWorkbenchEcsConfig.domainName` if they need TLS on a custom name).
 */
export function defaultMcpWorkbenchHostnameFromServeApiDomain (restApiDomain: string | null | undefined): string | null {
    const trimmed = restApiDomain?.trim();
    if (!trimmed) {
        return null;
    }
    const parts = trimmed.split('.');
    const first = parts[0];
    if (!first) {
        return null;
    }

    let nextFirst: string | null = null;
    if (first.endsWith('-serve')) {
        nextFirst = `${first.slice(0, -'-serve'.length)}-mcp-workbench`;
    } else if (first === 'serve') {
        nextFirst = 'mcp-workbench';
    }

    if (!nextFirst) {
        return null;
    }
    parts[0] = nextFirst;
    return parts.join('.');
}

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

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useMcp } from 'use-mcp/react';
import { McpServer } from '@/shared/reducers/mcp-server.reducer';
import { McpPreferences } from '@/shared/reducers/user-preferences.reducer';
import { isWorkbenchMcpServer } from '@/components/utils';

/** Stable fingerprint so RTK Query's new object references do not restart useMcp on every render. */
function fingerprintHeaders (h: Record<string, string> | undefined): string {
    if (!h || Object.keys(h).length === 0) {
        return '';
    }
    const keys = Object.keys(h).sort();
    return keys.map((k) => `${k}=${h[k]}`).join('&');
}

type McpConnectionProps = {
    server: McpServer;
    /** When `isReady` is false, the parent clears tools and connection state for this server (disconnected / not ready). */
    onToolsChange: (tools: any[], server: McpServer, isReady: boolean) => void;
    onConnectionChange: (connection: any, clientName: string) => void;
    sessionId?: string;
    /**
     * When the workbench tool-file list refetches (RTK `dataUpdatedAt`), re-run tools/list on the
     * live MCP session. use-mcp does not refresh tools after connect, so this keeps the chat tool
     * count aligned with the server after S3 sync / rescan.
     */
    workbenchToolListDataUpdatedAt?: number;
};

// Individual MCP Connection Component
export const McpConnection = ({ server, onToolsChange, onConnectionChange, sessionId, workbenchToolListDataUpdatedAt }: McpConnectionProps) => {
    const headersFingerprint = fingerprintHeaders(server.customHeaders);
    const clientConfigKey = JSON.stringify(server.clientConfig ?? null);
    const serverUrl = server.url ?? ' ';
    const serverName = server.name;

    const mergedHeaders = useMemo(() => {
        const base: Record<string, string> = { ...(server.customHeaders ?? {}) };
        if (sessionId) {
            base['X-Session-Id'] = sessionId;
        }
        return Object.keys(base).length > 0 ? base : undefined;
        // headersFingerprint reflects header values; RTK often replaces customHeaders with a new object on refetch.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [headersFingerprint, sessionId]);

    const clientConfigForMcp = useMemo(
        () => server.clientConfig ?? undefined,
        // clientConfigKey reflects clientConfig; avoid reconnecting when RTK replaces the server object.
        // eslint-disable-next-line react-hooks/exhaustive-deps
        [clientConfigKey],
    );

    const callbackUrl = useMemo(
        () =>
            `${window.location.origin}${
                window.env.API_BASE_URL.includes('.') ? '/' : window.env.API_BASE_URL
            }oauth/callback`,
        [],
    );

    const mcpOptions = useMemo(
        () => ({
            url: serverUrl,
            clientName: serverName,
            autoReconnect: true,
            // Overlapping retries + streamable HTTP abort the previous fetch → ClientDisconnect / NetworkError on server
            autoRetry: false,
            debug: false,
            clientConfig: clientConfigForMcp,
            customHeaders: mergedHeaders,
            callbackUrl,
        }),
        [serverUrl, serverName, clientConfigForMcp, mergedHeaders, callbackUrl],
    );

    const connection = useMcp(mcpOptions);
    const listToolsRef = useRef<(() => Promise<void>) | undefined>(undefined);
    listToolsRef.current = (connection as { listTools?: () => Promise<void> }).listTools;

    const prevCallToolRef = useRef<any>(null);

    // Push tools when ready; clear aggregated state when the session is not ready (avoids stale banner/tools).
    useEffect(() => {
        if (connection.state === 'ready') {
            onToolsChange(connection.tools ?? [], server, true);
        } else {
            onToolsChange([], server, false);
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- server ref churns; id/name identify MCP server
    }, [connection.state, connection.tools, onToolsChange, server.id, server.name]);

    // Workbench: after tool-file metadata refetches, ask the server for the current tools list again.
    useEffect(() => {
        if (!isWorkbenchMcpServer(server) || workbenchToolListDataUpdatedAt == null) {
            return;
        }
        if (connection.state !== 'ready') {
            return;
        }
        const listTools = listToolsRef.current;
        if (!listTools) {
            return;
        }
        void listTools().catch((err: unknown) => {
            console.warn('[McpConnection] listTools after workbench file list update failed:', err);
        });
    // isWorkbenchMcpServer(server) uses id/url; full `server` ref churns each RTK emit.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [connection.state, server.id, workbenchToolListDataUpdatedAt, server.url]);

    useEffect(() => {
        if (connection.callTool && prevCallToolRef.current !== connection.callTool) {
            prevCallToolRef.current = connection.callTool;
            onConnectionChange(connection, server.name);
        }
    }, [connection.callTool, server.name, onConnectionChange, connection]);

    return null; // This component only manages the connection
};

export type UseMultipleMcpOptions = {
    /**
     * Fingerprint of workbench tool files (e.g. sorted ids). When this changes, workbench MCP
     * connections remount so use-mcp runs tools/list again (the library does not refresh tools after connect).
     */
    workbenchToolListFingerprint?: string;
    /** RTK Query `dataUpdatedAt` for the workbench tool-file list; triggers tools/list on the live session. */
    workbenchToolListDataUpdatedAt?: number;
};

// Custom hook to manage multiple MCP connections dynamically
export const useMultipleMcp = (
    servers: McpServer[],
    mcpPreferences: McpPreferences,
    sessionId?: string,
    options?: UseMultipleMcpOptions,
) => {
    const [serverToolsMap, setServerToolsMap] = useState<Map<string, any[]>>(new Map());
    const [connectionsMap, setConnectionsMap] = useState<Map<string, any>>(new Map());
    const [toolToServerMap, setToolToServerMap] = useState<Map<string, string>>(new Map());

    const serversRef = useRef(servers);
    useEffect(() => {
        serversRef.current = servers;
    });

    /** Stable when enabled id/name set is unchanged (avoids prune effect running every parent render). */
    const enabledServersBindKey = useMemo(() => {
        if (!servers?.length) {
            return '';
        }
        return servers.map((s) => `${s.id}:${s.name}`).sort().join('|');
    }, [servers]);

    const handleToolsChange = useCallback((tools: any[], srv: McpServer, isReady: boolean) => {
        const clientName = srv.name;

        if (!isReady) {
            setServerToolsMap((prev) => {
                if (!prev.has(clientName)) {
                    return prev;
                }
                const next = new Map(prev);
                next.delete(clientName);
                return next;
            });
            setToolToServerMap((prev) => {
                const toDelete: string[] = [];
                for (const [toolName, srvName] of prev.entries()) {
                    if (srvName === clientName) {
                        toDelete.push(toolName);
                    }
                }
                if (toDelete.length === 0) {
                    return prev;
                }
                const next = new Map(prev);
                for (const toolName of toDelete) {
                    next.delete(toolName);
                }
                return next;
            });
            setConnectionsMap((prev) => {
                if (!prev.has(clientName)) {
                    return prev;
                }
                const next = new Map(prev);
                next.delete(clientName);
                return next;
            });
            return;
        }

        const pref = mcpPreferences?.enabledServers?.find(
            (s) => s.id === srv.id || s.name === clientName,
        );
        const disabledForServer = pref?.disabledTools;

        setServerToolsMap((prev) => {
            const newMap = new Map(prev);
            newMap.set(
                clientName,
                tools.filter((tool) => !(disabledForServer?.includes(tool.name) ?? false)),
            );
            return newMap;
        });

        setToolToServerMap((prev) => {
            const newMap = new Map(prev);
            prev.forEach((serverName, toolName) => {
                if (serverName === clientName) {
                    newMap.delete(toolName);
                }
            });
            tools.forEach((tool) => {
                if (tool.name) {
                    newMap.set(tool.name, clientName);
                }
            });
            return newMap;
        });
    }, [mcpPreferences?.enabledServers]);

    const handleConnectionChange = useCallback((connection: any, clientName: string) => {
        setConnectionsMap((prev) => {
            const newMap = new Map(prev);
            newMap.set(clientName, connection);
            return newMap;
        });
    }, []);

    // Drop tool/connection state for servers that are no longer enabled (map keys are server names).
    // Otherwise stale rows accumulate and the chat banner sums too many tools (e.g. "1 servers — 3 tools").
    useEffect(() => {
        const current = serversRef.current;
        if (!current?.length) {
            setServerToolsMap((prev) => (prev.size > 0 ? new Map() : prev));
            setToolToServerMap((prev) => (prev.size > 0 ? new Map() : prev));
            setConnectionsMap((prev) => (prev.size > 0 ? new Map() : prev));
            return;
        }
        const allowed = new Set(current.map((s) => s.name));
        setServerToolsMap((prev) => {
            let hasStaleServer = false;
            for (const name of prev.keys()) {
                if (!allowed.has(name)) {
                    hasStaleServer = true;
                    break;
                }
            }
            if (!hasStaleServer) {
                return prev;
            }
            const next = new Map<string, any[]>();
            for (const [name, tools] of prev) {
                if (allowed.has(name)) {
                    next.set(name, tools);
                }
            }
            return next;
        });
        setToolToServerMap((prev) => {
            let changed = false;
            const next = new Map(prev);
            for (const [toolName, srvName] of [...next.entries()]) {
                if (!allowed.has(srvName)) {
                    next.delete(toolName);
                    changed = true;
                }
            }
            return changed ? next : prev;
        });
        setConnectionsMap((prev) => {
            let changed = false;
            const next = new Map(prev);
            for (const name of [...next.keys()]) {
                if (!allowed.has(name)) {
                    next.delete(name);
                    changed = true;
                }
            }
            return changed ? next : prev;
        });
    }, [enabledServersBindKey]);

    const allTools = useMemo(
        () => Array.from(serverToolsMap.values()).flat(),
        [serverToolsMap],
    );

    const callTool = useCallback(async (toolName: string, args: any) => {
        const serverName = toolToServerMap.get(toolName);
        if (!serverName) {
            throw new Error(`Tool "${toolName}" not found in any MCP server`);
        }

        const connection = connectionsMap.get(serverName);
        if (!connection || !connection.callTool) {
            throw new Error(`Connection for server "${serverName}" not available or doesn't support tool calling`);
        }

        try {
            return await connection.callTool(toolName, args);
        } catch (error) {
            console.error(`Error calling tool "${toolName}" on server "${serverName}":`, error);
            throw error;
        }
    }, [toolToServerMap, connectionsMap]);

    const workbenchFp = options?.workbenchToolListFingerprint ?? '';
    const workbenchDataUpdatedAt = options?.workbenchToolListDataUpdatedAt;

    return {
        tools: allTools,
        /** MCP sessions currently in `ready` state (same keys as `serverToolsMap`). */
        readyMcpServerCount: serverToolsMap.size,
        callTool,
        McpConnections: servers?.map((server) => (
            <McpConnection
                key={`${server.id}::${sessionId ?? ''}::${isWorkbenchMcpServer(server) ? workbenchFp : ''}`}
                server={server}
                onToolsChange={handleToolsChange}
                onConnectionChange={handleConnectionChange}
                sessionId={sessionId}
                workbenchToolListDataUpdatedAt={isWorkbenchMcpServer(server) ? workbenchDataUpdatedAt : undefined}
            />
        )),
        toolToServerMap
    };
};

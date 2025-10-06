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

// Individual MCP Connection Component
export const McpConnection = ({ server, onToolsChange, onConnectionChange }: {
    server: McpServer,
    onToolsChange: (tools: any[], clientName: string) => void,
    onConnectionChange: (connection: any, clientName: string) => void
}) => {
    const connection = useMcp({
        url: server?.url ?? ' ',
        callbackUrl: `${window.location.origin}/#/oauth/callback`,
        clientName: server?.name,
        autoReconnect: true,
        autoRetry: true,
        debug: false,
        clientConfig: server?.clientConfig ?? undefined,
        customHeaders: server?.customHeaders ?? undefined,
    });

    // Use refs to track previous values and avoid unnecessary updates
    const prevToolsRef = useRef<string>('');
    const prevCallToolRef = useRef<any>(null);

    // Memoize tools to avoid unnecessary re-renders
    const toolsString = useMemo(() => JSON.stringify(connection.tools || []), [connection.tools]);

    useEffect(() => {
        if (prevToolsRef.current !== toolsString) {
            prevToolsRef.current = toolsString;
            onToolsChange(connection.tools || [], server.name);
        }
    }, [toolsString, server.name, onToolsChange, connection.tools]);

    useEffect(() => {
        if (connection.callTool && prevCallToolRef.current !== connection.callTool) {
            prevCallToolRef.current = connection.callTool;
            onConnectionChange(connection, server.name);
        }
    }, [connection.callTool, server.name, onConnectionChange, connection]);

    return null; // This component only manages the connection
};

// Custom hook to manage multiple MCP connections dynamically
export const useMultipleMcp = (servers: McpServer[], mcpPreferences: McpPreferences) => {
    const [allTools, setAllTools] = useState([]);
    const [serverToolsMap, setServerToolsMap] = useState<Map<string, any[]>>(new Map());
    const [connectionsMap, setConnectionsMap] = useState<Map<string, any>>(new Map());
    const [toolToServerMap, setToolToServerMap] = useState<Map<string, string>>(new Map());

    const handleToolsChange = useCallback((tools: any[], clientName: string) => {
        setServerToolsMap((prev) => {
            const newMap = new Map(prev);
            newMap.set(clientName, tools.filter((tool) => !mcpPreferences?.enabledServers?.find((server) => server.name === clientName)?.disabledTools.includes(tool.name)));
            return newMap;
        });

        // Update tool-to-server mapping
        setToolToServerMap((prev) => {
            const newMap = new Map(prev);
            // Remove old mappings for this server
            prev.forEach((serverName, toolName) => {
                if (serverName === clientName) {
                    newMap.delete(toolName);
                }
            });
            // Add new mappings
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

    useEffect(() => {
        // Combine all tools from all servers
        const combinedTools = Array.from(serverToolsMap.values()).flat();
        setAllTools(combinedTools);
    }, [serverToolsMap]);

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

    return {
        tools: allTools,
        callTool,
        McpConnections: servers?.map((server) => (
            <McpConnection
                key={server.name}
                server={server}
                onToolsChange={handleToolsChange}
                onConnectionChange={handleConnectionChange}
            />
        )),
        toolToServerMap
    };
};

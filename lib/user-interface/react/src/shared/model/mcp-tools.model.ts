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
 * Interface representing an MCP Tool - TypeScript equivalent of Python MCPToolModel
 */
export type IMcpTool = {
    /** The filename/toolId seen by frontend */
    id: string;
    /** The Python code content */
    contents: string;
    /** Timestamp of when the tool was created/updated */
    updated_at?: string;
    /** File size in bytes (included in list responses) */
    size?: number;
};

/**
 * Response interface for listing MCP tools
 */
export type IMcpToolListResponse = {
    tools: IMcpTool[];
};

/**
 * Request interface for creating a new MCP tool
 */
export type IMcpToolRequest = {
    /** The tool identifier/filename */
    id: string;
    /** The Python code content */
    contents: string;
};

/**
 * Request interface for updating an existing MCP tool
 */
export type IMcpToolUpdateRequest = {
    /** The Python code content */
    contents: string;
};

/**
 * Response interface for delete operations
 */
export type IMcpToolDeleteResponse = {
    status: string;
    message: string;
};

/**
 * Interface for MCP tool validation response
 */
export type IMcpToolValidationResponse = {
    /** Whether the code is valid */
    is_valid: boolean;

    /** List of syntax errors */
    syntax_errors: Array<{
        type: string;
        message: string;
        line: number;
        column: number;
        text?: string;
    }>;
    /** Missing required MCP imports */
    missing_required_imports: string[];

    /** Timestamp of validation */
    validation_timestamp: string;
};

/**
 * Default empty MCP tool for forms
 */
export const DefaultMcpTool: IMcpToolRequest = {
    id: '',
    contents: ''
};

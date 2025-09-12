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

import { Button, CodeEditor, Container, Grid, SpaceBetween, List, ButtonDropdown, Header, Box, Icon, Input, FormField, Alert, TextFilter, Pagination } from '@cloudscape-design/components';
import 'react';
import 'ace-builds';
// import * as ace from 'ace-builds/src-noconflict/ace';
    import { Ace } from 'ace-builds';
// import 'ace-builds/webpack-resolver'; // lets ace load workers/themes when bundled
import 'ace-builds/src-noconflict/mode-python';
import 'ace-builds/src-noconflict/theme-tomorrow';
import 'ace-builds/src-noconflict/ext-language_tools';
import { ReactElement, useEffect, useState } from 'react';
import { useAppDispatch } from '@/config/store';
import { useNotificationService } from '@/shared/util/hooks';
import { setConfirmationModal } from '@/shared/reducers/modal.reducer';
import {
    useListMcpToolsQuery,
    useGetMcpToolQuery,
    useCreateMcpToolMutation,
    useUpdateMcpToolMutation,
    useDeleteMcpToolMutation
} from '@/shared/reducers/mcp-tools.reducer';
import { IMcpTool, DefaultMcpTool } from '@/shared/model/mcp-tools.model';
import initialTool from './default_tool.txt?raw';
import { setBreadcrumbs } from '@/shared/reducers/breadcrumbs.reducer';

export function McpWorkbenchManagementComponent(): ReactElement {
    const dispatch = useAppDispatch();
    const notificationService = useNotificationService(dispatch);
    
    // API hooks
    const { data: tools = [], isFetching: isLoadingTools, refetch } = useListMcpToolsQuery();
    const [selectedToolId, setSelectedToolId] = useState<string | null>(null);
    const { data: selectedToolData, isFetching: isLoadingTool } = useGetMcpToolQuery(selectedToolId!, {  });
    
    const [createToolMutation, { isLoading: isCreating }] = useCreateMcpToolMutation();
    const [updateToolMutation, { isLoading: isUpdating }] = useUpdateMcpToolMutation();
    const [deleteToolMutation, { isLoading: isDeleting }] = useDeleteMcpToolMutation();
    
    // Local state
    const defaultContent = initialTool;
    const [editorContent, setEditorContent] = useState<string>('');
    const [isEditing, setIsEditing] = useState<boolean>(false);
    const [isCreatingNew, setIsCreatingNew] = useState<boolean>(false);
    const [newToolName, setNewToolName] = useState<string>('');
    const [hasUnsavedChanges, setHasUnsavedChanges] = useState<boolean>(false);
    
    // Filtering and pagination state
    const [filterText, setFilterText] = useState<string>('');
    const [currentPageIndex, setCurrentPageIndex] = useState<number>(1);
    const pageSize = 5;
    
    // Filter and paginate tools
    const filteredTools = tools.filter(tool => 
        tool.id.toLowerCase().includes(filterText.toLowerCase()) ||
        tool.contents?.toLowerCase().includes(filterText.toLowerCase())
    );
    
    const totalPages = Math.ceil(filteredTools.length / pageSize);
    const paginatedTools = filteredTools.slice(
        (currentPageIndex - 1) * pageSize,
        currentPageIndex * pageSize
    );

    dispatch(setBreadcrumbs([]));
    
    // Reset pagination when filter changes
    useEffect(() => {
        setCurrentPageIndex(1);
    }, [filterText]);

    // Update editor content when a tool is selected
    useEffect(() => {
        if (selectedToolData && !isCreatingNew) {
            setEditorContent(selectedToolData.contents);
            setIsEditing(true);
            setHasUnsavedChanges(false);
        }
    }, [selectedToolData, isCreatingNew]);

    // Handle tool selection
    const handleToolSelect = (tool: IMcpTool) => {
        if (hasUnsavedChanges) {
            dispatch(
                setConfirmationModal({
                    action: 'Switch Tool',
                    resourceName: selectedToolId,
                    onConfirm: () => {
                        setSelectedToolId(tool.id);
                        setIsCreatingNew(false);
                        setHasUnsavedChanges(false);
                    },
                    description: 'You have unsaved changes. Switching tools will lose these changes.'
                })
            );
        } else {
            setSelectedToolId(tool.id);
            setIsCreatingNew(false);
        }
    };

    // Handle editor content change
    const handleEditorChange = (value: string) => {
        setEditorContent(value);
        if (!isCreatingNew && selectedToolData && value !== selectedToolData.contents) {
            setHasUnsavedChanges(true);
        } else if (isCreatingNew && value !== defaultContent) {
            setHasUnsavedChanges(true);
        }
    };

    // Handle creating new tool
    const handleCreateNew = () => {
        if (hasUnsavedChanges && selectedToolId) {
            dispatch(
                setConfirmationModal({
                    action: 'Create New Tool',
                    resourceName: '',
                    onConfirm: () => {
                        setIsCreatingNew(true);
                        setSelectedToolId(null);
                        setNewToolName('');
                        setEditorContent(defaultContent);
                        setHasUnsavedChanges(false);
                        setIsEditing(false);
                    },
                    description: 'You have unsaved changes. Creating a new tool will lose these changes.'
                })
            );
        } else {
            setIsCreatingNew(true);
            setSelectedToolId(null);
            setNewToolName('');
            setEditorContent(defaultContent);
            setHasUnsavedChanges(false);
            setIsEditing(false);
        }
    };

    // Handle create tool
    const handleCreateTool = async () => {
        if (!newToolName.trim()) {
            notificationService.generateNotification('Please enter a tool name', 'error');
            return;
        }

        try {
            const toolName = newToolName.endsWith('.py') ? newToolName : `${newToolName}.py`;
            await createToolMutation({
                id: toolName,
                contents: editorContent
            }).unwrap();
            
            notificationService.generateNotification(`Successfully created tool: ${toolName}`, 'success');
            setIsCreatingNew(false);
            setNewToolName('');
            setHasUnsavedChanges(false);
            refetch();
        } catch (error: any) {
            const errorMessage = error?.data?.message || error?.message || 'Unknown error occurred';
            notificationService.generateNotification(`Error creating tool: ${errorMessage}`, 'error');
        }
    };

    // Handle update tool
    const handleUpdateTool = async () => {
        if (!selectedToolId || !selectedToolData) return;

        try {
            await updateToolMutation({
                toolId: selectedToolId,
                tool: { contents: editorContent }
            }).unwrap();
            
            notificationService.generateNotification(`Successfully updated tool: ${selectedToolId}`, 'success');
            setHasUnsavedChanges(false);
        } catch (error: any) {
            const errorMessage = error?.data?.message || error?.message || 'Unknown error occurred';
            notificationService.generateNotification(`Error updating tool: ${errorMessage}`, 'error');
        }
    };

    // Handle delete tool
    const handleDeleteTool = (tool: IMcpTool) => {
        dispatch(
            setConfirmationModal({
                action: 'Delete',
                resourceName: 'Tool',
                onConfirm: async () => {
                    try {
                        await deleteToolMutation(tool.id).unwrap();
                        notificationService.generateNotification(`Successfully deleted tool: ${tool.id}`, 'success');
                        
                        // Reset selection if the deleted tool was selected
                        if (selectedToolId === tool.id) {
                            setSelectedToolId(null);
                            setEditorContent('');
                            setIsEditing(false);
                            setHasUnsavedChanges(false);
                        }
                        
                        refetch();
                    } catch (error: any) {
                        const errorMessage = error?.data?.message || error?.message || 'Unknown error occurred';
                        notificationService.generateNotification(`Error deleting tool: ${errorMessage}`, 'error');
                    }
                },
                description: `This will permanently delete the tool: ${tool.id}`
            })
        );
    };

    const getCurrentToolName = () => {
        if (isCreatingNew) return 'New Tool';
        if (selectedToolData) return selectedToolData.id;
        return '';
    };

    return (
        <Container
            header={
                <Header variant='h1'>
                    MCP Workbench
                </Header>
            }>
        <Grid gridDefinition={[{ colspan: 3 }, { colspan: 9 }]}>
            <SpaceBetween size='s' direction='vertical'>
                <Header
                    variant="h3"
                    actions={
                        <SpaceBetween direction='horizontal' size='xxs'>
                            <Button
                                onClick={() => refetch()}
                                ariaLabel="Refresh tools"
                                disabled={isLoadingTools}
                            >
                                <Icon name='refresh' />
                            </Button>
                            <Button 
                                variant="primary"
                                onClick={handleCreateNew}
                                disabled={isCreating}
                            >
                                New Tool
                            </Button>
                        </SpaceBetween>
                    }
                >
                    Tools ({tools.length})
                </Header>

                {tools.length > 0 && (
                    <TextFilter
                        filteringText={filterText}
                        filteringPlaceholder="Find tools..."
                        filteringAriaLabel="Find tools"
                        onChange={({ detail }) => setFilterText(detail.filteringText)}
                    />
                )}

                {isLoadingTools ? (
                    <Box margin={{ vertical: 'xs' }} textAlign='center' color='inherit'>
                        <SpaceBetween size='m'>
                            <b>Loading tools...</b>
                        </SpaceBetween>
                    </Box>
                ) : tools.length === 0 ? (
                    <Box margin={{ vertical: 'xs' }} textAlign='center' color='inherit'>
                        <SpaceBetween size='m'>
                            <b>No tools</b>
                            <p>Create your first tool to get started.</p>
                        </SpaceBetween>
                    </Box>
                ) : filteredTools.length === 0 ? (
                    <Box margin={{ vertical: 'xs' }} textAlign='center' color='inherit'>
                        <SpaceBetween size='m'>
                            <b>No tools match your search</b>
                            <p>Try adjusting your search criteria.</p>
                        </SpaceBetween>
                    </Box>
                ) : (
                    <>
                        <List
                            renderItem={(item: IMcpTool) => ({
                                id: item.id,
                                content: (
                                    <Box>
                                        <Button
                                            variant="inline-link"
                                            onClick={() => handleToolSelect(item)}
                                            disabled={selectedToolId === item.id && !isCreatingNew}
                                            ariaLabel={`Load ${item.id} in editor`}
                                        >
                                            <div style={{ fontWeight: 'bold' }}>{item.id}</div>
                                        </Button>
                                        {item.updated_at && (
                                            <div style={{ fontSize: '0.875rem', color: '#555' }}>
                                                Updated: {new Date(item.updated_at).toLocaleString()}
                                            </div>
                                        )}
                                        {item.size && (
                                            <div style={{ fontSize: '0.875rem', color: '#555' }}>
                                                Size: {item.size} bytes
                                            </div>
                                        )}
                                    </Box>
                                ),
                                actions: (
                                    <Button
                                        variant='icon'
                                        iconName='remove'
                                        ariaLabel={`Delete ${item.id}`}
                                        onClick={() => handleDeleteTool(item)}
                                    />
                                )
                            })}
                            items={paginatedTools}
                        />
                        
                        {totalPages > 1 && (
                            <Box textAlign="center">
                                <Pagination
                                    currentPageIndex={currentPageIndex}
                                    pagesCount={totalPages}
                                    onChange={({ detail }) => setCurrentPageIndex(detail.currentPageIndex)}
                                />
                            </Box>
                        )}
                    </>
                )}
            </SpaceBetween>

            <SpaceBetween size='s' direction='vertical'>
                <Header
                    variant="h3"
                    description={isCreatingNew ? "Create a new tool" : isEditing ? "Edit the selected tool" : ""}
                >
                    {getCurrentToolName()}
                </Header>

                {isCreatingNew && (
                    <FormField
                        label="Tool Name"
                        description="Enter a name for your tool. Extension '.py' will be added automatically if omitted."
                        errorText={!newToolName.trim() ? "Tool name is required" : ""}
                    >
                        <Input
                            value={newToolName}
                            onChange={({ detail }) => {
                                let value = detail.value;
                                // Remove .py if user types it, we'll add it automatically
                                if (value.endsWith('.py')) {
                                    value = value.slice(0, -3);
                                }
                                setNewToolName(value);
                            }}
                            placeholder="my_tool"
                        />
                    </FormField>
                )}

                <CodeEditor
                    language='python'
                    value={editorContent}
                    ace={ace}
                    loading={isLoadingTool}
                    onDelayedChange={({ detail }) => {
                        // Only allow changes if we're creating new or editing
                        if (isCreatingNew || isEditing) {
                            handleEditorChange(detail.value);
                        }
                    }}
                    preferences={{
                        wrapLines: true,
                        theme: 'cloud_editor',
                    }}
                    onPreferencesChange={() => {}}
                    themes={{
                        light: ["cloud_editor"],
                        dark: ["cloud_editor_dark"]
                    }}
                />

                <Box float="right">
                    {isCreatingNew ? (
                        <Button 
                            variant="primary"
                            onClick={handleCreateTool}
                            loading={isCreating}
                            disabled={!newToolName.trim() || !editorContent.trim()}
                        >
                            Create Tool
                        </Button>
                    ) : isEditing ? (
                        <Button 
                            variant="primary"
                            onClick={handleUpdateTool}
                            loading={isUpdating}
                            disabled={!hasUnsavedChanges}
                        >
                            Save Changes
                        </Button>
                    ) : null}
                </Box>
            </SpaceBetween>
        </Grid>
        </Container>
    );
}

export default McpWorkbenchManagementComponent;

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

import { Button, Container, Grid, SpaceBetween, List, Header, Box, Input, FormField, TextFilter, Pagination, Link, TextContent, Spinner } from '@cloudscape-design/components';
import { RefreshButton } from '@/components/common/RefreshButton';
import AceEditor from 'react-ace';
import {Editor} from 'ace-builds';

import 'react';
import { ReactElement, useCallback, useContext, useEffect, useState } from 'react';
import { useAppDispatch } from '@/config/store';
import { useDebounce, useNotificationService } from '@/shared/util/hooks';
import * as z from 'zod';
import { setConfirmationModal } from '@/shared/reducers/modal.reducer';
import {
    useListMcpToolsQuery,
    useGetMcpToolQuery,
    useCreateMcpToolMutation,
    useUpdateMcpToolMutation,
    useDeleteMcpToolMutation,
    mcpToolsApi,
    useValidateMcpToolMutation,
} from '@/shared/reducers/mcp-tools.reducer';
import { IMcpTool } from '@/shared/model/mcp-tools.model';
import { setBreadcrumbs } from '@/shared/reducers/breadcrumbs.reducer';
import { useValidationReducer } from '@/shared/validation';
import { ModifyMethod } from '@/shared/validation/modify-method';
import ColorSchemeContext from '@/shared/color-scheme.provider';
import { Mode } from '@cloudscape-design/global-styles';
import { formatDate } from '@/shared/util/formats';

const DEFAULT_CONTENT = 'from mcpworkbench.core.annotations import mcp_tool\nfrom mcpworkbench.core.base_tool import BaseTool\nfrom typing import Annotated\n\n\n# =============================================================================\n# METHOD 1: FUNCTION-BASED APPROACH WITH @mcp_tool DECORATOR\n# =============================================================================\n# This is a simpler approach for straightforward tools that don\'t need\n# complex initialization or state management.\n\n@mcp_tool(\n    name="simple_calculator",\n    description="A simple calculator using the decorator approach"\n)\nasync def simple_calculator(\n    operator: Annotated[str, "The arithmetic operation: add, subtract, multiply, or divide"],\n    left_operand: Annotated[float, "The first number in the operation"],\n    right_operand: Annotated[float, "The second number in the operation"]\n) -> dict:\n    \'\'\'\n    Perform basic arithmetic operations using the decorator approach.\n    \n    The @mcp_tool decorator automatically:\n    1. Registers the function as an MCP tool\n    2. Extracts parameter information from type annotations\n    3. Uses the Annotated descriptions for parameter documentation\n    4. Handles the MCP protocol communication\n    \n    This approach is ideal for:\n    - Simple, stateless operations\n    - Quick prototyping\n    - Tools that don\'t need complex initialization\n    \'\'\'\n    \n    if operator == "add":\n        result = left_operand + right_operand\n    elif operator == "subtract":\n        result = left_operand - right_operand\n    elif operator == "multiply":\n        result = left_operand * right_operand\n    elif operator == "divide":\n        if right_operand == 0:\n            raise ValueError("Cannot divide by zero")\n        result = left_operand / right_operand\n    else:\n        raise ValueError(f"Unknown operator: {operator}")\n    \n    return {\n        "operator": operator,\n        "left_operand": left_operand,\n        "right_operand": right_operand,\n        "result": result\n    }\n\n\n# =============================================================================\n# METHOD 2: CLASS-BASED APPROACH\n# =============================================================================\n# This is the more structured approach, ideal for complex tools that need\n# initialization, state management, or multiple related operations.\n\nclass CalculatorTool(BaseTool):\n    """\n    A simple calculator tool that performs basic arithmetic operations.\n    \n    This class demonstrates the class-based approach to creating MCP tools:\n    1. Inherit from BaseTool\n    2. Initialize with name and description in __init__\n    3. Implement execute() method that returns the callable function\n    4. Define the actual tool function with proper type annotations\n    """\n    \n    def __init__(self):\n        """\n        Initialize the tool with metadata.\n        \n        The BaseTool constructor requires:\n        - name: A unique identifier for the tool\n        - description: A clear description of what the tool does\n        """\n        super().__init__(\n            name="calculator",\n            description="Performs basic arithmetic operations (add, subtract, multiply, divide)"\n        )\n\n    async def execute(self):\n        """\n        Return the callable function that implements the tool\'s functionality.\n        \n        This method is called by the MCP framework to get the actual function\n        that will be executed when the tool is invoked.\n        """\n        return self.calculate\n    \n    async def calculate(\n        self,\n        operator: Annotated[str, "add, subtract, multiply, or divide"],\n        left_operand: Annotated[float, "The first number"],\n        right_operand: Annotated[float, "The second number"]\n    ):\n        """\n        Execute the calculator operation.\n        \n        Parameter Type Annotations with Context:\n        =======================================\n        Notice the use of Annotated[type, "description"] for each parameter.\n        This is OPTIONAL but highly recommended because it provides:\n        \n        1. Type information for the MCP framework\n        2. Human-readable descriptions that help AI models understand\n           what each parameter is for\n        3. Better error messages and validation\n        \n        The Annotated type comes from typing module and follows this pattern:\n        Annotated[actual_type, "description_string"]\n        \n        Examples:\n        - Annotated[str, "The operation to perform"]\n        - Annotated[int, "A positive integer between 1 and 100"]\n        - Annotated[list[str], "A list of file paths to process"]\n        """        \n        if operator == "add":\n            result = left_operand + right_operand\n        elif operator == "subtract":\n            result = left_operand - right_operand\n        elif operator == "multiply":\n            result = left_operand * right_operand\n        elif operator == "divide":\n            if right_operand == 0:\n                raise ValueError("Cannot divide by zero")\n            result = left_operand / right_operand\n        else:\n            raise ValueError(f"Unknown operator: {operator}")\n        \n        return {\n            "operator": operator,\n            "left_operand": left_operand,\n            "right_operand": right_operand,\n            "result": result\n        }';

export function McpWorkbenchManagementComponent (): ReactElement {
    const dispatch = useAppDispatch();
    const notificationService = useNotificationService(dispatch);

    // API hooks
    const { data: tools = [], isFetching: isLoadingTools } = useListMcpToolsQuery();
    const [selectedToolId, setSelectedToolId] = useState<string | null>(null);
    const { data: selectedToolData, isUninitialized } = useGetMcpToolQuery(selectedToolId!, {
        skip: selectedToolId === null,
        refetchOnMountOrArgChange: true,
        refetchOnFocus: true
    });

    const [loadingAce, setLoadingAce] = useState(true);
    const [isDirty, setIsDirty] = useState<boolean>(false);
    const [createToolMutation, { isLoading: isCreating }] = useCreateMcpToolMutation();
    const [updateToolMutation, { isLoading: isUpdating }] = useUpdateMcpToolMutation();
    const [deleteToolMutation] = useDeleteMcpToolMutation();
    const {colorScheme} = useContext(ColorSchemeContext);
    const [statusText, setStatusText] = useState<string | undefined>('');

    const schema = z.object({
        id: z.string().regex(/^[a-z0-9_.]+?(\.py)?$/).trim().min(3, 'String cannot be empty.'),
        contents: z.string().trim().min(1, 'String cannot be empty.'),
    });

    const { errors, touchFields, setFields, isValid, state, setState } = useValidationReducer(schema, {
        form: { } as Partial<IMcpTool>,
        formSubmitting: false,
        touched: {},
        validateAll: false
    });

    const [validateMcpToolMutation, {isLoading: isLoadingValidateMcpTool, data: validMcpToolResponse} ] = useValidateMcpToolMutation();
    const [editor, setEditor] = useState<Editor>();

    // Filtering and pagination state
    const [filterText, setFilterText] = useState<string>('');
    const [currentPageIndex, setCurrentPageIndex] = useState<number>(1);
    const pageSize = 5;

    // Filter and paginate tools
    const filteredTools = tools.filter((tool) =>
        tool.id.toLowerCase().includes(filterText.toLowerCase()) ||
        tool.contents?.toLowerCase().includes(filterText.toLowerCase())
    );

    const totalPages = Math.ceil(filteredTools.length / pageSize);
    const paginatedTools = filteredTools.slice(
        (currentPageIndex - 1) * pageSize,
        currentPageIndex * pageSize
    );

    const [ waitingForValidation, setWaitingForValidation ] = useState<boolean>(false);

    // Dont validate immediately, wait until this hasn't been called for 300ms
    const debouncedValidation = useDebounce(useCallback((contents: string) => {
        validateMcpToolMutation(contents).then((response) => {
            setWaitingForValidation(false);
            setStatusText(undefined);

            // Handle validation response
            if ('data' in response) {
                // Successful validation response
                const validationData = response.data;
                const annotations = [];

                // Add syntax error annotations
                if (validationData.syntax_errors && validationData.syntax_errors.length > 0) {
                    validationData.syntax_errors.forEach((error) => {
                        annotations.push({
                            row: Math.max(0, error.line - 1), // Ace editor is 0-indexed
                            column: error.column,
                            type: 'error',
                            text: `${error.type}: ${error.message}`
                        });
                    });
                }

                if (validationData.missing_required_imports.length > 0) {
                    validationData.missing_required_imports.forEach((error) => {
                        annotations.push({
                            row: 0,
                            column: 0,
                            type: 'error',
                            text: error
                        });
                    });
                }

                // Apply annotations to editor
                if (editor) {
                    editor.getSession().setAnnotations(annotations);
                }

            } else if ('error' in response) {
                // Error response from validation API
                console.error('Validation API error:', response.error);

                // Clear any existing annotations
                if (editor) {
                    editor.getSession().setAnnotations([]);
                }

                // Show error notification
                const errorMessage = 'data' in response.error && response.error.data?.message
                    ? response.error.data.message
                    : 'Unknown validation error';
                notificationService.generateNotification(
                    `Validation error: ${errorMessage}`,
                    'error'
                );
            }
        }).catch((error) => {
            // Handle promise rejection
            console.error('Validation request failed:', error);

            // Clear any existing annotations
            if (editor) {
                editor.getSession().setAnnotations([]);
            }

            // Show error notification
            notificationService.generateNotification(
                `Validation failed: ${error.message || 'Unknown error'}`,
                'error'
            );
        });
    }, [validateMcpToolMutation, editor, notificationService]), 300);

    // remove top breadcrumbs
    useEffect(() => {
        dispatch(setBreadcrumbs([]));
    }, [dispatch]);

    // Reset pagination when filter changes
    useEffect(() => {
        setCurrentPageIndex(1);
    }, [filterText]);

    useEffect(() => {
        async function loadAce () {
            await import('ace-builds');

            // Import language modes you need
            await import('ace-builds/src-noconflict/mode-python');

            // Import themes
            await import('ace-builds/src-noconflict/theme-cloud_editor');
            await import('ace-builds/src-noconflict/theme-cloud_editor_dark');

            setLoadingAce(false);
        }

        loadAce();
    }, []);

    // Update editor content when a tool is selected
    useEffect(() => {
        if (!isUninitialized && selectedToolData?.id) {
            setFields({
                id: selectedToolData.id,
                contents: selectedToolData.contents,
                size: selectedToolData.size,
                updated_at: selectedToolData.updated_at
            });
            setIsDirty(false);
            setStatusText(undefined);
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isUninitialized, selectedToolData]);

    // Handle tool selection
    const handleToolSelect = (tool: IMcpTool) => {
        if (isDirty) {
            dispatch(
                setConfirmationModal({
                    title: 'Switch Tool?',
                    action: 'Switch Tool',
                    onConfirm: () => {
                        setSelectedToolId(tool.id);
                        setStatusText('Loading MCP tool.');
                    },
                    description: 'You have unsaved changes. Switching tools will discard these changes.'
                })
            );
        } else {
            setSelectedToolId(tool.id);
            setStatusText('Loading MCP tool.');
        }
    };

    // Handle creating new tool
    const handleCreateNew = (event?: any) => {
        event?.preventDefault();

        const newTool = {
            id: '',
            contents: DEFAULT_CONTENT,
        };

        if (isDirty && selectedToolId) {
            dispatch(
                setConfirmationModal({
                    title: 'Create New Tool?',
                    action: 'Create New Tool',
                    onConfirm: () => {
                        setSelectedToolId(null);
                        touchFields(['id'], ModifyMethod.Unset);
                        setFields(newTool);
                        setIsDirty(false);
                    },
                    description: 'You have unsaved changes. Creating a new tool will discard these changes.'
                })
            );
        } else {
            setSelectedToolId(null);
            touchFields(['id'], ModifyMethod.Unset);
            setFields(newTool);
            setIsDirty(false);
        }
    };

    // Handle create tool
    const handleCreateTool = async () => {
        const result = schema.safeParse(state.form);
        if (!result.success) {
            setState({
                ...state,
                validateAll: true
            });

            return;
        }

        try {
            const result = await createToolMutation({
                id: state.form.id,
                contents: state.form.contents
            }).unwrap();

            notificationService.generateNotification(`Successfully created tool: ${state.form.id}`, 'success');
            setSelectedToolId(result.id);
            setIsDirty(false);
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
                tool: { contents: state.form.contents }
            }).unwrap();

            notificationService.generateNotification(`Successfully updated tool: ${selectedToolId}`, 'success');
            setIsDirty(false);
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
                            setFields({
                                id: '',
                                contents: '',
                                size: undefined,
                                updated_at: undefined
                            });
                            setIsDirty(false);
                        }


                    } catch (error: any) {
                        const errorMessage = error?.data?.message || error?.message || 'Unknown error occurred';
                        notificationService.generateNotification(`Error deleting tool: ${errorMessage}`, 'error');
                    }
                },
                description: `This will permanently delete the tool: ${tool.id}`
            })
        );
    };

    const disabled = !isDirty || !isValid || (isLoadingValidateMcpTool || waitingForValidation) || !validMcpToolResponse?.is_valid;
    const disabledReason = [
        {predicate: !isDirty, message: 'Tool has not been modified.'},
        {predicate: !isValid, message: 'Ensure all fields are valid.'},
        {predicate: isLoadingValidateMcpTool || waitingForValidation, message: 'Validating tool.'},
        {predicate: !validMcpToolResponse?.is_valid, message: 'Please correct all errors.'}
    ].find((reason) => reason.predicate)?.message;

    return (
        <SpaceBetween size='m'>
            <Header variant='h1' description='Use the code editor to experiment with MCP tools.'>MCP Workbench</Header>
            <Container>
                <Grid gridDefinition={[{ colspan: 3 }, { colspan: 9 }]}>
                    <SpaceBetween size='s' direction='vertical'>
                        <Header
                            variant='h3'
                            actions={
                                <SpaceBetween direction='horizontal' size='xxs'>
                                    <RefreshButton
                                        isLoading={isLoadingTools}
                                        onClick={() => {
                                            // Invalidate cache - this will automatically trigger refetch of active queries
                                            dispatch(mcpToolsApi.util.invalidateTags(['mcpTools']));
                                        }}
                                        ariaLabel='Refresh tools list'
                                    />
                                    <Button
                                        variant='primary'
                                        onClick={handleCreateNew}
                                        ariaLabel='New Tool File'
                                    >New Tool</Button>
                                </SpaceBetween>
                            }
                        >
                            Tool Files ({tools.length})
                        </Header>

                        {tools.length > 0 && (
                            <TextFilter
                                filteringText={filterText}
                                filteringPlaceholder='Find tools...'
                                filteringAriaLabel='Find tools'
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
                                                    variant='inline-link'
                                                    onClick={(event) => {
                                                        event.preventDefault();
                                                        handleToolSelect(item);
                                                    }}
                                                    disabled={selectedToolId === item.id}
                                                    ariaLabel={`Load ${item.id} in editor`}
                                                >
                                                    <div style={{ fontWeight: 'bold' }}>{item.id}</div>
                                                </Button>
                                                {item.updated_at && (
                                                    <div style={{ fontSize: '0.875rem', color: '#555' }}>
                                                        Updated: {formatDate(item.updated_at)}
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
                                    <Box textAlign='center'>
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

                    {(!loadingAce && state.form.contents) ?
                        <SpaceBetween size='s' direction='vertical'>

                            <FormField
                                errorText={errors?.id}
                            >
                                <Input
                                    disabled={!!selectedToolId}
                                    value={state.form.id}
                                    onChange={({ detail }) => {
                                        touchFields(['id']);
                                        const value = detail.value;
                                        setFields({ id: value });
                                    }}
                                    placeholder='my_tool'
                                />
                            </FormField>

                            <Container
                                disableContentPaddings={true}
                            // disableHeaderPaddings={true}
                            >
                                <div style={{overflow: 'hidden', borderRadius: '16px'}}>
                                    <AceEditor
                                        theme={colorScheme === Mode.Light ? 'cloud_editor' : 'cloud_editor_dark'}
                                        showGutter={true}
                                        value={state.form.contents}
                                        mode='python'
                                        setOptions={{
                                            firstLineNumber: 0,
                                            dragEnabled: true
                                        }}
                                        onChange={(contents) => {
                                            setFields({
                                                contents
                                            });
                                            debouncedValidation(contents);
                                            setStatusText('Validating MCP tool.');
                                            setIsDirty(true);
                                            touchFields(['contents']);

                                            if (!waitingForValidation) {
                                                setWaitingForValidation(true);
                                            }
                                        }}
                                        onLoad={(editor) => {
                                            setEditor(editor);
                                        }}
                                        width='100%'
                                    />
                                </div>
                            </Container>

                            <Box float='right'>
                                <SpaceBetween direction='horizontal' size='s'>
                                    { statusText ? <TextContent>
                                        <p><Spinner /> {statusText}</p>
                                    </TextContent> : null}

                                    <Button onClick={() => {
                                        setSelectedToolId(null);
                                        setFields({
                                            id: null,
                                            contents: null
                                        });
                                        setIsDirty(false);
                                    }}>
                                        Cancel
                                    </Button>
                                    {selectedToolId === null ? (
                                        <Button
                                            variant='primary'
                                            onClick={handleCreateTool}
                                            loading={isCreating}
                                            disabled={disabled}
                                            disabledReason={disabledReason}
                                        >
                                            Create Tool
                                        </Button>
                                    ) : (
                                        <Button
                                            variant='primary'
                                            onClick={handleUpdateTool}
                                            loading={isUpdating}
                                            disabled={disabled}
                                            disabledReason={disabledReason}
                                        >
                                            Save Changes
                                        </Button>
                                    )}
                                </SpaceBetween>
                            </Box>
                        </SpaceBetween> : <div style={{display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%'}}>
                            <SpaceBetween direction='vertical' size='m'>
                                <p style={{textAlign: 'center'}}>Select an existing tool or <Link onClick={handleCreateNew}>Create Tool</Link></p>
                                {statusText ? <TextContent>
                                    <p style={{textAlign: 'center'}}><Spinner /> {statusText}</p>
                                </TextContent> : null}
                            </SpaceBetween>

                        </div>}
                </Grid>
            </Container>
        </SpaceBetween>
    );
}

export default McpWorkbenchManagementComponent;

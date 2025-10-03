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

import {
    Button,
    Container,
    Form,
    FormField,
    Grid,
    Header,
    Input,
    SpaceBetween,
    Toggle,
    StatusIndicator,
    Box,
    TokenGroup,
} from '@cloudscape-design/components';
import { KeyCode } from '@cloudscape-design/component-toolkit/internal';
import 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { issuesToErrors, scrollToInvalid, useValidationReducer } from '../../shared/validation';
import { z } from 'zod';
import React, { useEffect, useState, useMemo } from 'react';
import { setBreadcrumbs } from '../../shared/reducers/breadcrumbs.reducer';
import { useAppDispatch, useAppSelector } from '../../config/store';
import { useNotificationService } from '../../shared/util/hooks';
import { ModifyMethod } from '../../shared/validation/modify-method';
import { selectCurrentUserIsAdmin, selectCurrentUsername } from '../../shared/reducers/user.reducer';
import {
    DefaultMcpServer,
    mcpServerApi,
    McpServerStatus,
    NewMcpServer,
    useCreateMcpServerMutation,
    useLazyGetMcpServerQuery,
    useUpdateMcpServerMutation
} from '@/shared/reducers/mcp-server.reducer';
import { AttributeEditorSchema, EnvironmentVariables } from '@/shared/form/environment-variables';
import { useMcp } from 'use-mcp/react';

export type McpServerFormProps = {
    isEdit?: boolean
};

export function McpServerForm (props: McpServerFormProps) {
    const { isEdit } = props;
    const { mcpServerId } = useParams();
    const navigate = useNavigate();
    const dispatch = useAppDispatch();
    const isUserAdmin = useAppSelector(selectCurrentUserIsAdmin);
    const userName = useAppSelector(selectCurrentUsername);

    const [createMcpServer, {data: createData, isLoading: isCreating, isSuccess: isCreatingSuccess, isError: isCreatingError, error: createError}] = useCreateMcpServerMutation();
    const [updateMcpSever, {data: updateData, isLoading: isUpdating, isSuccess: isUpdatingSuccess, isError: isUpdatingError, error: updateError}] = useUpdateMcpServerMutation();
    const [getMcpServerQuery, {data, isSuccess, isUninitialized, isFetching}] = useLazyGetMcpServerQuery();
    const notificationService = useNotificationService(dispatch);

    if (isSuccess) {
        dispatch(setBreadcrumbs([
            { text: 'MCP Connections', href: '/mcp-connections' },
            { text: data.name, href: '' }
        ]));
    }

    const schema = z.object({
        name: z.string().trim().min(1, 'String cannot be empty.'),
        url: z.string().trim().min(1, 'String cannot be empty.'),
        description: z.string().trim().optional(),
        status: z.string().trim(),
        clientConfig: z.object({
            name: z.string().trim(),
            version: z.string().trim()
        }),
        customHeaders: AttributeEditorSchema
    });

    const { errors, touchFields, setFields, isValid, state, setState } = useValidationReducer(schema, {
        form: DefaultMcpServer,
        formSubmitting: false,
        touched: {},
        validateAll: false
    });

    // handle separate token text validation
    const [tokenText, setTokenText] = useState('');
    const tokenTextSchema = z.object({'groups': z.string().trim().max(0, {message: 'You must press return to add a group.'})});
    const tokenTextResult = tokenTextSchema.safeParse({'groups': tokenText});
    const tokenTextErrors = tokenTextResult.success ? undefined : issuesToErrors(tokenTextResult?.error?.issues || [], state.touched);

    // memoize conversion to tokens
    const tokens = useMemo(() => {
        return state.form.groups
            .filter((group) => group !== 'lisa:public')
            .map((group) => ({label: group.replace(/^\w+:/, '')}));
    }, [state.form.groups]);

    const canEdit = mcpServerId ? (isUserAdmin || data?.isOwner) : true;
    const disabled = isFetching || isCreating || isUpdating;

    if (isEdit && isUninitialized && mcpServerId) {
        getMcpServerQuery({mcpServerId, showPlaceholder: true}).then((response) => {
            if (response.isSuccess) {
                setFields({ ...response.data,
                    customHeaders: response.data.customHeaders ? Object.entries(response.data.customHeaders).map(([key, value]) => ({ key, value })) : [],
                    status: response.data.status ?? McpServerStatus.Inactive,
                });
                setSharePublic(response.data.owner === 'lisa:public');
            }
        });
    }

    const submit = (mcpServer: NewMcpServer) => {
        if (isValid) {
            const toSubmit = {
                ...mcpServer,
                customHeaders: mcpServer.customHeaders?.reduce((r,{key,value}) => (r[key] = value,r), {}),
            };
            if (mcpServer.id) {
                updateMcpSever(toSubmit);
            } else {
                createMcpServer(toSubmit);
            }
        } else {
            setState({validateAll: true});
            scrollToInvalid();
        }
    };

    const [sharePublic, setSharePublic] = useState(false);

    // Test connection state
    const [testConnectionUrl, setTestConnectionUrl] = useState<string>('');
    const [isTestingConnection, setIsTestingConnection] = useState(false);

    // Test connection using useMcp
    const {
        state: connectionState,
        tools,
    } = useMcp({
        url: testConnectionUrl,
        callbackUrl: new URL('/#/oauth/callback', window.location.origin).toString(),
        clientName: state.form.clientConfig?.name || 'Test Client',
        clientConfig: state.form.clientConfig || {},
        customHeaders: state.form.customHeaders?.reduce((r,{key,value}) => (r[key] = value,r), {}),
        autoReconnect: false,
        autoRetry: false,
        debug: false,
    });

    const testConnection = () => {
        if (state.form.url && String(state.form.url).trim()) {
            setIsTestingConnection(true);
            setTestConnectionUrl(String(state.form.url).trim());

            // Add a timeout to prevent infinite loading
            setTimeout(() => {
                if (isTestingConnection) {
                    setIsTestingConnection(false);
                }
            }, 30000); // 30 second timeout
        }
    };

    // Reset test connection state when URL changes
    useEffect(() => {
        if (testConnectionUrl !== state.form.url) {
            setTestConnectionUrl('');
            setIsTestingConnection(false);
        }
    }, [state.form.url, testConnectionUrl]);

    // Reset testing state when connection completes
    useEffect(() => {
        if (testConnectionUrl && (connectionState === 'ready' || connectionState === 'failed')) {
            setIsTestingConnection(false);
        }
    }, [connectionState, testConnectionUrl]);

    // create success notification
    useEffect(() => {
        if (isCreatingSuccess || isUpdatingSuccess) {
            const verb = isCreatingSuccess ? 'created' : 'updated';
            const data = isCreatingSuccess ? createData : updateData;
            notificationService.generateNotification(`Successfully ${verb} MCP Connection: ${data.name}`, 'success');
            navigate(`/mcp-connections/${data.id}`);
            dispatch(mcpServerApi.util.invalidateTags(['mcpServers']));
        }
    }, [isCreatingSuccess, isUpdatingSuccess, notificationService, createData, updateData, navigate, dispatch]);

    // create failure notification
    useEffect(() => {
        if (isCreatingError || isUpdatingError) {
            const verb = isCreatingError ? 'created' : 'updated';
            const error = createError || updateError;
            notificationService.generateNotification(`Error ${verb} MCP Connection: ${error.data?.message ?? error.data}`, 'error');
        }
    }, [isCreatingError, isUpdatingError, createError, updateError, notificationService]);

    return (
        <Form
            header={<Header variant='h1'>Connection</Header>}
            actions={
                <SpaceBetween direction='horizontal' size='s'>
                    <Button onClick={() => navigate(-1)}>Cancel</Button>
                    <Button variant='primary'
                        disabled={disabled || !canEdit}
                        loading={isCreating || isUpdating}
                        disabledReason={!canEdit ? 'You can only edit connections you created.' : undefined}
                        onClick={() => submit(state.form)}>
                        { mcpServerId ? 'Update' : 'Create'} Connection
                    </Button>
                </SpaceBetween>
            }
        >
            <Container header={<Header>Details</Header>}>
                <SpaceBetween direction='vertical' size='s'>
                    <FormField label='Name' errorText={errors?.name} description={'This will be used to identify your connection.'}>
                        <Input value={state.form.name} inputMode='text' onBlur={() => touchFields(['name'])} onChange={({ detail }) => {
                            setFields({ 'name': detail.value });
                        }}
                        disabled={disabled}
                        placeholder='Enter MCP connection name' />
                    </FormField>
                    <FormField label='Description' errorText={errors?.description} description={'A description that provides an overview of your connection.'}>
                        <Input value={state.form.description} inputMode='text' onBlur={() => touchFields(['description'])} onChange={({ detail }) => {
                            setFields({ 'description': detail.value });
                        }}
                        disabled={disabled}
                        placeholder='Enter MCP connection description' />
                    </FormField>
                    <FormField label='URL' errorText={errors?.url} description={'The URL for your MCP server.'}>
                        <Grid gridDefinition={[{ colspan: 8 }, { colspan: 4 }]}>
                            <Input value={state.form.url} inputMode='text' onBlur={() => touchFields(['url'])} onChange={({ detail }) => {
                                setFields({ 'url': detail.value });
                            }}
                            disabled={disabled}
                            placeholder='Enter MCP server URL' />
                            <Button
                                onClick={testConnection}
                                disabled={disabled || !String(state.form.url || '').trim()}
                                loading={isTestingConnection}
                                variant='normal'
                            >
                                Test Connection
                            </Button>
                        </Grid>
                        {testConnectionUrl && (
                            <Box margin={{ top: 'xs' }}>
                                <StatusIndicator
                                    type={connectionState === 'ready' ? 'success' :
                                        connectionState === 'failed' ? 'error' :
                                            connectionState === 'discovering' || connectionState === 'authenticating' || connectionState === 'connecting' || connectionState === 'loading' ? 'pending' : 'error'}
                                >
                                    {connectionState === 'ready' ? 'Connection successful' :
                                        connectionState === 'failed' ? 'Connection failed' :
                                            connectionState === 'discovering' ? 'Discovering server...' :
                                                connectionState === 'authenticating' ? 'Authenticating...' :
                                                    connectionState === 'connecting' || connectionState === 'loading' ? 'Connecting...' :
                                                        'Connection failed'}
                                </StatusIndicator>
                                {connectionState === 'ready' && tools && (
                                    <Box margin={{ top: 'xs' }}>
                                        <small>Available tools: {tools.length}</small>
                                    </Box>
                                )}
                                {connectionState === 'failed' && (
                                    <Box margin={{ top: 'xs' }}>
                                        <small>Unable to connect to the MCP server. Please check the URL and try again.</small>
                                    </Box>
                                )}
                            </Box>
                        )}
                    </FormField>

                    {isUserAdmin && <SpaceBetween direction='vertical' size='s'>
                        <Grid gridDefinition={[{colspan: 3}, {colspan: 3}]}>
                            <FormField label='Share with everyone'>
                                <Toggle checked={sharePublic} onChange={({detail}) => {
                                    setSharePublic(detail.checked);
                                    setFields({owner: detail.checked ? 'lisa:public' : userName});
                                    setFields({groups: detail.checked ? [] : state.form.groups});
                                    touchFields(['owner'], ModifyMethod.Unset);
                                }}
                                disabled={disabled} />
                            </FormField>
                            <FormField label='Active'>
                                <Toggle checked={state.form.status === McpServerStatus.Active} onChange={({detail}) => {
                                    setFields({status: detail.checked ? McpServerStatus.Active : McpServerStatus.Inactive});
                                    touchFields(['status'], ModifyMethod.Unset);
                                }}
                                disabled={disabled} />
                            </FormField>
                        </Grid>
                        <FormField label='Share with specific groups' errorText={tokenTextErrors?.groups} description={'Templates are public by default. Enter groups here to limit sharing to a specific subset. Enter a group name and then press return.'}>
                            <Input value={tokenText} inputMode='text' onChange={({ detail }) => {
                                setTokenText(detail.value);
                                if (detail.value.length === 0) {
                                    touchFields(['groups'], ModifyMethod.Unset);
                                }
                            }} onKeyDown={({detail}) => {
                                if (detail.keyCode === KeyCode.enter) {
                                    setFields({groups: state.form.groups?.concat(`group:${tokenText}`) ?? [`group:${tokenText}`]});
                                    touchFields(['groups'], ModifyMethod.Unset);
                                    setTokenText('');
                                }
                            }}
                            onBlur={() => {
                                if (tokenText.length === 0) {
                                    touchFields(['groups'], ModifyMethod.Unset);
                                } else {
                                    touchFields(['groups']);
                                }
                            }}

                            placeholder='Enter group name'
                            disabled={disabled || sharePublic} />
                            <TokenGroup items={tokens} onDismiss={({detail}) => {
                                const newTokens = [...state.form.groups];
                                newTokens.splice(detail.itemIndex, 1);
                                setFields({groups: newTokens});
                            }} readOnly={disabled || sharePublic} />
                        </FormField>
                    </SpaceBetween>}
                    <hr />
                    <Container
                        header={
                            <Header variant='h2'>Client Configuration</Header>
                        }
                    >
                        <FormField label={<span>Name <i>- optional</i>{' '}</span>} errorText={errors?.url} description={'Custom MCP client name.'}>
                            <Input value={state.form.clientConfig.name} inputMode='text' onBlur={() => touchFields(['clientConfig.name'])} onChange={({ detail }) => {
                                setFields({ 'clientConfig.name': detail.value });
                            }}
                            disabled={disabled}
                            placeholder='Enter custom MCP client name' />
                        </FormField>
                        <FormField label={<span>Version <i>- optional</i>{' '}</span>} errorText={errors?.url} description={'Custom MCP client version.'}>
                            <Input value={state.form.clientConfig.version} inputMode='text' onBlur={() => touchFields(['clientConfig.version'])} onChange={({ detail }) => {
                                setFields({ 'clientConfig.version': detail.value });
                            }}
                            disabled={disabled}
                            placeholder='Enter custom MCP client version' />
                        </FormField>
                    </Container>
                    <Container
                        header={
                            <Header variant='h2'>Custom Headers</Header>
                        }
                    >
                        <SpaceBetween size={'s'}>
                            <EnvironmentVariables item={state.form} setFields={setFields} touchFields={touchFields} formErrors={errors} propertyPath={['customHeaders']}/>
                        </SpaceBetween>
                    </Container>
                </SpaceBetween>
            </Container>
        </Form>
    );
}

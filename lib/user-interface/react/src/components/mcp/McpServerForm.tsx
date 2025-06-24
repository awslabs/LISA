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
    Header,
    Input,
    SpaceBetween,
    Toggle,
} from '@cloudscape-design/components';
import 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { scrollToInvalid, useValidationReducer } from '../../shared/validation';
import { z } from 'zod';
import React, { useEffect, useState } from 'react';
import { setBreadcrumbs } from '../../shared/reducers/breadcrumbs.reducer';
import { useAppDispatch, useAppSelector } from '../../config/store';
import { useNotificationService } from '../../shared/util/hooks';
import { ModifyMethod } from '../../shared/validation/modify-method';
import { selectCurrentUserIsAdmin } from '../../shared/reducers/user.reducer';
import {
    DefaultMcpServer, NewMcpServer,
    useCreateMcpServerMutation, useLazyGetMcpServerQuery,
    useUpdateMcpServerMutation
} from '@/shared/reducers/mcp-server.reducer';
import { AttributeEditorSchema, EnvironmentVariables } from '@/shared/form/environment-variables';

export type McpServerFormProps = {
    isEdit?: boolean
};

export function McpServerForm (props: McpServerFormProps) {
    const { isEdit } = props;
    const { mcpServerId } = useParams();
    const navigate = useNavigate();
    const dispatch = useAppDispatch();
    const isUserAdmin = useAppSelector(selectCurrentUserIsAdmin);

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

    const canEdit = mcpServerId ? (isUserAdmin || data?.isOwner) : true;
    const disabled = isFetching || isCreating || isUpdating;

    if (isEdit && isUninitialized && mcpServerId) {
        getMcpServerQuery(mcpServerId).then((response) => {
            if (response.isSuccess) {
                setFields({ ...response.data,
                    customHeaders: response.data.customHeaders ? Object.entries(response.data.customHeaders).map(([key, value]) => ({ key, value })) : [],});
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

    // create success notification
    useEffect(() => {
        if (isCreatingSuccess || isUpdatingSuccess) {
            const verb = isCreatingSuccess ? 'created' : 'updated';
            const data = isCreatingSuccess ? createData : updateData;
            notificationService.generateNotification(`Successfully ${verb} MCP Connection: ${data.name}`, 'success');
            navigate('/mcp-connections');
        }
    }, [isCreatingSuccess, isUpdatingSuccess, notificationService, createData, updateData, navigate]);

    // create failure notification
    useEffect(() => {
        if (isCreatingError || isUpdatingError) {
            const verb = isCreatingError ? 'created' : 'updated';
            const error = createError || updateError;
            notificationService.generateNotification(`Error ${verb} MCP Server: ${error.data?.message ?? error.data}`, 'error');
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
                    <FormField label='URL' errorText={errors?.url} description={'The URL for your MCP server.'}>
                        <Input value={state.form.url} inputMode='text' onBlur={() => touchFields(['url'])} onChange={({ detail }) => {
                            setFields({ 'url': detail.value });
                        }}
                        disabled={disabled}
                        placeholder='Enter MCP server URL' />
                    </FormField>

                    {isUserAdmin && <FormField label='Share with everyone'>
                        <Toggle checked={sharePublic} onChange={({detail}) => {
                            setSharePublic(detail.checked);
                            setFields({owner: detail.checked ? 'lisa:public' : undefined});
                            touchFields(['owner'], ModifyMethod.Unset);
                        }}
                        disabled={disabled} />
                    </FormField>}
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

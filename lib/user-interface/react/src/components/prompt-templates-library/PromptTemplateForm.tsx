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
    Select,
    SpaceBetween,
    Textarea,
    Toggle,
    TokenGroup
} from '@cloudscape-design/components';
import 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
    DefaultPromptTemplate,
    NewPromptTemplate,
    PromptTemplateType,
    useCreatePromptTemplateMutation,
    useLazyGetPromptTemplateQuery,
    useUpdatePromptTemplateMutation
} from '../../shared/reducers/prompt-templates.reducer';
import { issuesToErrors, scrollToInvalid, useValidationReducer } from '../../shared/validation';
import { z } from 'zod';
import { useEffect, useMemo, useState } from 'react';
import { KeyCode } from '@cloudscape-design/component-toolkit/internal';
import { setBreadcrumbs } from '../../shared/reducers/breadcrumbs.reducer';
import { useAppDispatch, useAppSelector } from '../../config/store';
import { useNotificationService } from '../../shared/util/hooks';
import { ModifyMethod } from '../../shared/validation/modify-method';
import { selectCurrentUserIsAdmin } from '../../shared/reducers/user.reducer';
import { findKey } from 'lodash';

export type PromptTemplateFormProps = {
    isEdit?: boolean
};

export function PromptTemplateForm (props: PromptTemplateFormProps) {
    const { isEdit } = props;
    const { promptTemplateId } = useParams();
    const navigate = useNavigate();
    const dispatch = useAppDispatch();
    const isUserAdmin = useAppSelector(selectCurrentUserIsAdmin);

    const [createPromptTemplate, {data: createData, isLoading: isCreating, isSuccess: isCreatingSuccess, isError: isCreatingError, error: createError}] = useCreatePromptTemplateMutation();
    const [updatePromptTemplate, {data: updateData, isLoading: isUpdating, isSuccess: isUpdatingSuccess, isError: isUpdatingError, error: updateError}] = useUpdatePromptTemplateMutation();
    const [getPromptTemplateQuery, {data, isSuccess, isUninitialized, isFetching}] = useLazyGetPromptTemplateQuery();
    const notificationService = useNotificationService(dispatch);

    // if create/update was successful, redirect back to list
    if (isCreatingSuccess || isUpdatingSuccess) {
        navigate('/prompt-templates');
    }

    if (isSuccess) {
        dispatch(setBreadcrumbs([
            { text: 'Prompt Templates', href: '/prompt-templates' },
            { text: data.title, href: '' }
        ]));
    }

    const schema = z.object({
        title: z.string().trim().min(1, 'String cannot be empty.'),
        body: z.string().trim().min(1, 'String cannot be empty.'),
    });

    const { errors, touchFields, setFields, isValid, state, setState } = useValidationReducer(schema, {
        form: DefaultPromptTemplate,
        formSubmitting: false,
        touched: {},
        validateAll: false
    });

    const canEdit = promptTemplateId ? (isUserAdmin || data?.isOwner) : true;
    const disabled = isFetching || isCreating || isUpdating;

    if (isEdit && isUninitialized && promptTemplateId) {
        getPromptTemplateQuery(promptTemplateId).then((response) => {
            if (response.isSuccess) {
                setFields(response.data);
            }
        });
    }

    const submit = (promptTemplate: NewPromptTemplate) => {
        if (isValid) {
            if (promptTemplate.id) {
                updatePromptTemplate(promptTemplate);
            } else {
                createPromptTemplate(promptTemplate);
            }
        } else {
            setState({validateAll: true});
            scrollToInvalid();
        }
    };

    // handle separate token text validation
    const [tokenText, setTokenText] = useState('');
    const tokenTextSchema = z.object({'groups': z.string().trim().max(0, {message: 'You must press return to add a group.'})});
    const tokenTextResult = tokenTextSchema.safeParse({'groups': tokenText});
    const tokenTextErrors = tokenTextResult.success ? undefined : issuesToErrors(tokenTextResult?.error?.issues || [], state.touched);

    const [sharePublic, setSharePublic] = useState(false);

    useEffect(() => {
        if (data?.groups?.findIndex((group) => group === 'lisa:public') > -1) {
            setSharePublic(true);
        }
    }, [data?.groups]);

    // memoize conversion to tokens
    const tokens = useMemo(() => {
        return state.form.groups
            .filter((group) => group !== 'lisa:public')
            .map((group) => ({label: group.replace(/^\w+:/, '')}));
    }, [state.form.groups]);

    // create success notification
    useEffect(() => {
        if (isCreatingSuccess || isUpdatingSuccess) {
            const verb = isCreatingSuccess ? 'created' : 'updated';
            const data = isCreatingSuccess ? createData : updateData;
            notificationService.generateNotification(`Successfully ${verb} Prompt Template: ${data.title}`, 'success');
        }
    }, [isCreatingSuccess, isUpdatingSuccess, notificationService, createData, updateData]);

    // create failure notification
    useEffect(() => {
        if (isCreatingError || isUpdatingError) {
            const verb = isCreatingError ? 'created' : 'updated';
            const error = createError || updateError;
            notificationService.generateNotification(`Error ${verb} Prompt Template: ${error.data?.message ?? error.data}`, 'error');
        }
    }, [isCreatingError, isUpdatingError, createError, updateError, notificationService]);

    return (
        <Form
            header={<Header variant='h1'>Template</Header>}
            actions={
                <SpaceBetween direction='horizontal' size='s'>
                    <Button onClick={() => navigate(-1)}>Cancel</Button>
                    <Button variant='primary'
                        disabled={disabled || !canEdit}
                        disabledReason={!canEdit ? 'You can only edit prompts you created.' : undefined}
                        onClick={() => submit(state.form)}>
                        { promptTemplateId ? 'Update' : 'Create'} Template
                    </Button>
                </SpaceBetween>
            }
        >
            <Container header={<Header>Details</Header>}>
                <SpaceBetween direction='vertical' size='s'>
                    <FormField label='Title' errorText={errors?.title} description={'This will be used to identify your template.'}>
                        <Input value={state.form.title} inputMode='text' onBlur={() => touchFields(['title'])} onChange={({ detail }) => {
                            setFields({ 'title': detail.value });
                        }}
                        disabled={disabled}
                        placeholder='Enter template title' />
                    </FormField>

                    <FormField label='Type' errorText={errors?.type} description={'The type of template you are creating.'}>
                        <Select
                            selectedOption={{label: findKey(PromptTemplateType, (type) => type === state.form.type), value: state.form.type}}
                            onChange={({detail}) => {
                                setFields({'type': detail.selectedOption.value});
                            }}
                            options={Object.entries(PromptTemplateType).map(([key, value]) => ({label: key, value}))}
                        />
                    </FormField>

                    <FormField label='Share with everyone'>
                        <Toggle checked={sharePublic} onChange={({detail}) => {
                            setSharePublic(detail.checked);
                            setFields({groups: detail.checked ? ['lisa:public'] : []});
                            touchFields(['groups'], ModifyMethod.Unset);
                            setTokenText('');
                        }}
                        disabled={disabled} />
                    </FormField>

                    <FormField label='Share with specific groups' errorText={tokenTextErrors?.groups} description={'Templates are public by default. Enter groups here to limit sharing to a specific subset. Enter a group name and then press return.'}>
                        <Input value={tokenText} inputMode='text' onChange={({ detail }) => {
                            setTokenText(detail.value);
                            if (detail.value.length === 0) {
                                touchFields(['groups'], ModifyMethod.Unset);
                            }
                        }} onKeyDown={({detail}) => {
                            if (detail.keyCode === KeyCode.enter) {
                                setFields({groups: state.form.groups.concat(`group:${tokenText}`)});
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
                    </FormField>
                    <TokenGroup items={tokens} onDismiss={({detail}) => {
                        const newTokens = [...state.form.groups];
                        newTokens.splice(detail.itemIndex, 1);
                        setFields({groups: newTokens});
                    }} readOnly={disabled || sharePublic} />

                    <hr />

                    <FormField label='Prompt' errorText={errors?.body}>
                        <Textarea value={state.form.body} onBlur={() => touchFields(['body'])} onChange={({ detail }) => {
                            setFields({ 'body': detail.value });
                        }}
                        placeholder='Enter your template content'
                        disabled={disabled} />
                    </FormField>
                </SpaceBetween>
            </Container>
        </Form>
    );
}

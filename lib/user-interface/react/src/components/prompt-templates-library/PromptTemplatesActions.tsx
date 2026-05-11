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

import React, { ReactElement, useEffect } from 'react';
import { Button, ButtonDropdown, SpaceBetween } from '@cloudscape-design/components';
import { RefreshButton } from '@/components/common/RefreshButton';
import { useAppDispatch, useAppSelector } from '../../config/store';
import { useNotificationService } from '../../shared/util/hooks';
import { INotificationService } from '../../shared/notification/notification.service';
import { MutationTrigger } from '@reduxjs/toolkit/dist/query/react/buildHooks';
import { Action, ThunkDispatch } from '@reduxjs/toolkit';
import { setConfirmationModal } from '../../shared/reducers/modal.reducer';
import { PromptTemplate, promptTemplateApi, useDeletePromptTemplateMutation } from '../../shared/reducers/prompt-templates.reducer';
import { NavigateFunction, useNavigate } from 'react-router-dom';
import { selectCurrentUserIsAdmin, selectCurrentUsername } from '../../shared/reducers/user.reducer';

export type PromptTemplatesActionsProps = {
    selectedItems: readonly PromptTemplate[];
    setSelectedItems: (items: PromptTemplate[]) => void;
    showPublic: boolean;
    isFetching: boolean;
};

export function PromptTemplatesActions (props: PromptTemplatesActionsProps): ReactElement {
    const dispatch = useAppDispatch();
    const notificationService = useNotificationService(dispatch);
    const navigate = useNavigate();
    const isUserAdmin = useAppSelector(selectCurrentUserIsAdmin);
    const username = useAppSelector(selectCurrentUsername);

    return (
        <SpaceBetween direction='horizontal' size='xs'>
            <RefreshButton
                isLoading={props.isFetching}
                onClick={() => {
                    props.setSelectedItems([]);
                    dispatch(promptTemplateApi.util.invalidateTags(['promptTemplates']));
                }}
                ariaLabel='Refresh prompt templates'
            />
            <PromptTemplatesActionButton
                dispatch={dispatch}
                notificationService={notificationService}
                isUserAdmin={isUserAdmin}
                username={username}
                selectedItems={props.selectedItems}
                setSelectedItems={props.setSelectedItems}
                showPublic={props.showPublic}
                isFetching={props.isFetching}
            />
            <Button variant='primary' onClick={() => {
                navigate('./new');
            }}>
                Create Prompt Template
            </Button>
        </SpaceBetween>
    );
}

// Rendered as a JSX child so the React Compiler treats it as a component
// (own hook scope) instead of memoizing the call by args and skipping its
// hook bodies on re-renders. See note in RepositoryActions.tsx.
type PromptTemplatesActionButtonProps = PromptTemplatesActionsProps & {
    dispatch: ThunkDispatch<any, any, Action>;
    notificationService: INotificationService;
    isUserAdmin: boolean;
    username: string;
};

function PromptTemplatesActionButton (props: PromptTemplatesActionButtonProps): ReactElement {
    const { dispatch, notificationService, isUserAdmin, selectedItems, setSelectedItems, showPublic } = props;
    const selectedPromptTemplate: PromptTemplate = selectedItems[0];
    const navigate = useNavigate();
    const [
        deleteMutation,
        { isSuccess: isDeleteSuccess, isError: isDeleteError, error: deleteError, isLoading: isDeleteLoading },
    ] = useDeletePromptTemplateMutation();

    useEffect(() => {
        if (!isDeleteLoading && isDeleteSuccess && selectedPromptTemplate) {
            notificationService.generateNotification(`Successfully deleted Prompt Template: ${selectedPromptTemplate.title}`, 'success');
            setSelectedItems([]);
        } else if (!isDeleteLoading && isDeleteError && selectedPromptTemplate) {
            notificationService.generateNotification(`Error deleting Prompt Template: ${deleteError.data?.message ?? deleteError.data}`, 'error');
            setSelectedItems([]);
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isDeleteSuccess, isDeleteError, deleteError, isDeleteLoading]);

    const items = [];
    if (selectedPromptTemplate) {
        items.push({
            text: 'Edit',
            id: 'editPromptTemplate',
            disabled: !isUserAdmin && showPublic,
            disabledReason: 'You cannot edit a Prompt Template you down own.',
        });

        items.push({
            text: 'Delete',
            id: 'deletePromptTemplate',
            disabled: !isUserAdmin && showPublic,
            disabledReason: 'You cannot delete a Prompt Template you down own.',
        });
    }

    return (
        <ButtonDropdown
            items={items}
            variant='primary'
            disabled={!selectedPromptTemplate}
            loading={isDeleteLoading}
            onItemClick={(e) =>
                ModelActionHandler(e, selectedPromptTemplate, dispatch, deleteMutation, navigate)
            }
            data-testid='prompt-template-actions-dropdown'
        >
            Actions
        </ButtonDropdown>
    );
}

const ModelActionHandler = (
    e: any,
    selectedItem: PromptTemplate,
    dispatch: ThunkDispatch<any, any, Action>,
    deleteMutation: MutationTrigger<any>,
    navigate: NavigateFunction
) => {
    switch (e.detail.id) {
        case 'editPromptTemplate':
            navigate(`./${selectedItem.id}`);
            break;
        case 'deletePromptTemplate':
            dispatch(
                setConfirmationModal({
                    action: 'Delete',
                    resourceName: 'Prompt Template',
                    onConfirm: () => deleteMutation(selectedItem.id),
                    description: `This will delete the following Prompt Template: ${selectedItem.title}.`
                })
            );
            break;
        default:
            return;
    }
};

export default PromptTemplatesActions;

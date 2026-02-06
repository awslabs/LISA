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

import { ReactElement } from 'react';
import { Button, SpaceBetween } from '@cloudscape-design/components';
import { RefreshButton } from '@/components/common/RefreshButton';
import { ITokenInfo } from '../../shared/model/api-token.model';
import { useDeleteTokenMutation } from '../../shared/reducers/api-token.reducer';
import { useAppDispatch } from '../../config/store';
import { setConfirmationModal } from '../../shared/reducers/modal.reducer';
import { useNotificationService } from '../../shared/util/hooks';

export type ApiTokenActionsProps = {
    selectedItems: ITokenInfo[];
    setSelectedItems: (items: ITokenInfo[]) => void;
    setCreateWizardVisible: (visible: boolean) => void;
    onRefresh: () => void;
    disableCreate?: boolean;
    isFetching?: boolean;
};

export function ApiTokenActions ({
    selectedItems,
    setSelectedItems,
    setCreateWizardVisible,
    onRefresh,
    disableCreate = false,
    isFetching = false,
}: ApiTokenActionsProps): ReactElement {
    const dispatch = useAppDispatch();
    const notificationService = useNotificationService(dispatch);
    const [deleteToken, { isLoading: isDeleting }] = useDeleteTokenMutation();

    const handleDelete = () => {
        if (selectedItems.length === 0) return;

        const token = selectedItems[0];
        dispatch(
            setConfirmationModal({
                action: 'Delete',
                resourceName: `${token.name}`,
                onConfirm: async () => {
                    try {
                        // For legacy tokens, use the token attribute
                        // For modern tokens, use the tokenUUID
                        const tokenIdForDelete = token.isLegacy ? token.name : token.tokenUUID;
                        await deleteToken(tokenIdForDelete).unwrap();
                        notificationService.generateNotification(
                            `Successfully deleted token: ${token.name}`,
                            'success'
                        );
                        setSelectedItems([]);
                    } catch (error: any) {
                        notificationService.generateNotification(
                            `Failed to delete token: ${error.message || 'Unknown error'}`,
                            'error'
                        );
                    }
                },
                description: 'Are you sure you want to delete this API token? This action cannot be undone and will immediately revoke access for any applications using this token.',
            })
        );
    };

    return (
        <SpaceBetween direction='horizontal' size='xs'>
            <RefreshButton
                isLoading={isFetching}
                onClick={onRefresh}
                ariaLabel='Refresh tokens'
            />
            <Button
                onClick={() => setCreateWizardVisible(true)}
                variant='primary'
                disabled={disableCreate}
            >
                Create Token
            </Button>
            <Button
                onClick={handleDelete}
                disabled={selectedItems.length === 0 || isDeleting}
            >
                Delete
            </Button>
        </SpaceBetween>
    );
}

export default ApiTokenActions;

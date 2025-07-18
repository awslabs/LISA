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

import { Modal as CloudscapeModal, Box, SpaceBetween, Button, ModalProps, NonCancelableCustomEvent } from '@cloudscape-design/components';
import React, { ReactElement, useState } from 'react';
import { useAppDispatch } from '../../config/store';
import { dismissModal } from '../reducers/modal.reducer';

export type CallbackFunction<T = any, R = void> = (props?: T) => R;

export type ConfirmationModalProps = {
    action: string;
    resourceName: string;
    onConfirm: () => void;
    postConfirm?: CallbackFunction;
    description?: string | ReactElement;
    disabled?: boolean;
    onDismiss?: (event?: NonCancelableCustomEvent<ModalProps.DismissDetail>) => void;
    ignoreResponses?: boolean;
};

function ConfirmationModal ({
    action,
    resourceName,
    onConfirm,
    postConfirm,
    description,
    disabled,
    onDismiss,
    ignoreResponses
}: ConfirmationModalProps): ReactElement {
    const [processing, setProcessing] = useState(false);
    const dispatch = useAppDispatch();

    return (
        <CloudscapeModal
            onDismiss={(event) => {
                dispatch(dismissModal());
                onDismiss?.(event);
            }}
            visible={true}
            closeAriaLabel='Close modal'
            footer={
                <Box float='right'>
                    <SpaceBetween direction='horizontal' size='xs'>
                        <Button onClick={() => {
                            dispatch(dismissModal());
                            onDismiss?.();
                        }}>
                            Cancel
                        </Button>
                        <Button
                            data-cy='modal-confirm'
                            variant='primary'
                            onClick={async () => {
                                setProcessing(true);
                                try {
                                    if (ignoreResponses) {
                                        onConfirm();
                                    } else {
                                        await onConfirm();
                                    }
                                } finally {
                                    dispatch(dismissModal());
                                    if (postConfirm) {
                                        postConfirm();
                                    }
                                }
                            }}
                            loading={processing}
                            disabled={disabled}
                        >
                            {action}
                        </Button>
                    </SpaceBetween>
                </Box>
            }
            header={`${action} "${resourceName}"`}
        >
            {description}
        </CloudscapeModal>
    );
}

export default ConfirmationModal;

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

import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import { ConfirmationModalProps } from '../modal/confirmation-modal';

const initialState = {
    confirmationModal: undefined as ConfirmationModalProps | undefined,
};

const modalSlice = createSlice({
    name: 'modal',
    initialState,
    reducers: {
        setConfirmationModal (state, action: PayloadAction<ConfirmationModalProps>) {
            state.confirmationModal = action.payload;
        },
        dismissModal (state) {
            state.confirmationModal = undefined;
        },
    },
});

// Reducer
export const { setConfirmationModal, dismissModal} = modalSlice.actions;
export default modalSlice.reducer;

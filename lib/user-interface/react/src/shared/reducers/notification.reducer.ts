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
import { NotificationProp } from '../notification/notifications.props';

const initialState = {
  notifications: [] as NotificationProp[],
};

const NotificationSlice = createSlice({
  name: 'notification',
  initialState,
  reducers: {
    addNotification(state, action: PayloadAction<NotificationProp>) {
      state.notifications = [...state.notifications, action.payload];
    },
    clearNotification(state, action: PayloadAction<string>) {
      state.notifications = state.notifications.filter((item) => item.id !== action.payload);
    },
    reset(state) {
      state.notifications = [];
    },
  },
});

export const { addNotification, clearNotification, reset } = NotificationSlice.actions;
export default NotificationSlice.reducer;
export const selectNotifications = (state: any) => state.notification.notifications;

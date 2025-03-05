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

import { ReducersMapObject } from '@reduxjs/toolkit';

import userReducer from './user.reducer';
import notificationReducer from './notification.reducer';
import modalReducer from './modal.reducer';
import { modelManagementApi } from './model-management.reducer';
import { configurationApi } from './configuration.reducer';
import { sessionApi } from './session.reducer';
import breadcrumbGroup from './breadcrumbs.reducer';
import { ragApi } from './rag.reducer';

const rootReducer: ReducersMapObject = {
    user: userReducer,
    notification: notificationReducer,
    modal: modalReducer,
    breadcrumbGroup: breadcrumbGroup,
    [modelManagementApi.reducerPath]: modelManagementApi.reducer,
    [configurationApi.reducerPath]: configurationApi.reducer,
    [sessionApi.reducerPath]: sessionApi.reducer,
    [ragApi.reducerPath]: ragApi.reducer,
};

export const rootMiddleware = [modelManagementApi.middleware, configurationApi.middleware, sessionApi.middleware, ragApi.middleware];

export default rootReducer;

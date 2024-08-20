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

import { Flashbar } from '@cloudscape-design/components';
import React, { useMemo } from 'react';
import { useDispatch } from 'react-redux';
import { reset, selectNotifications } from '../reducers/notification.reducer';
import { NotificationProp } from './notifications.props';
import { useNotificationService } from '../util/hooks';
import { useAppSelector } from '../../config/store';

function NotificationBanner() {
  const notifications: NotificationProp[] = useAppSelector(selectNotifications);
  const notificationDisplayMaxSize = 5;

  const dispatch = useDispatch();
  const notificationService = useNotificationService(dispatch);

  useMemo(() => {
    dispatch(reset());
  }, [dispatch]);

  return (
    <div role="status" aria-live="polite">
      <Flashbar
        items={notifications
          .slice(
            0,
            notifications.length > notificationDisplayMaxSize ? notificationDisplayMaxSize : notifications.length,
          )
          .map((props) => notificationService.createNotification(props))}
      />
    </div>
  );
}

export default NotificationBanner;

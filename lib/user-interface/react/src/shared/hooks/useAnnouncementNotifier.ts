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

import { useEffect, useCallback } from 'react';
import { useAppDispatch } from '@/config/store';
import { useNotificationService } from '@/shared/util/hooks';
import { clearNotification } from '@/shared/reducers/notification.reducer';
import { shouldShowAnnouncement, setDismissedTimestamp } from '@/shared/util/announcementDismissal';
import { IConfiguration } from '@/shared/model/configuration.model';

const ANNOUNCEMENT_NOTIFICATION_ID = 'announcement-notification';

/**
 * Custom hook that displays announcement notifications based on the system configuration.
 * Handles showing, dismissing, and persisting dismissal state for announcements.
 */
export function useAnnouncementNotifier (config: IConfiguration | undefined): void {
    const dispatch = useAppDispatch();
    const notificationService = useNotificationService(dispatch);

    const clearAnnouncement = useCallback(() => {
        dispatch(clearNotification(ANNOUNCEMENT_NOTIFICATION_ID));
    }, [dispatch]);

    useEffect(() => {
        if (!config) {
            return;
        }

        const announcement = config.configuration.announcement ?? { isEnabled: false, message: '' };
        const { isEnabled, message } = announcement;

        if (!isEnabled || !message) {
            clearAnnouncement();
            return;
        }

        if (!shouldShowAnnouncement(config.createdAt)) {
            return;
        }

        const onDismiss = () => {
            if (config.createdAt !== undefined) {
                setDismissedTimestamp(config.createdAt);
            }
            clearAnnouncement();
        };

        notificationService.generateNotification(
            '📢 Announcement: ' + message,
            'info',
            ANNOUNCEMENT_NOTIFICATION_ID,
            null,
            true,
            onDismiss,
        );
    }, [config, clearAnnouncement, notificationService]);
}

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

import { useEffect, useCallback, useRef } from 'react';
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
    const lastAnnouncementRef = useRef<string | null>(null);

    const clearAnnouncement = useCallback(() => {
        dispatch(clearNotification(ANNOUNCEMENT_NOTIFICATION_ID));
    }, [dispatch]);

    // Extract stable primitive values to avoid re-running the effect on object reference changes
    const isEnabled = config?.configuration?.announcement?.isEnabled ?? false;
    const message = config?.configuration?.announcement?.message ?? '';
    const createdAt = config?.createdAt;

    useEffect(() => {
        if (!isEnabled || !message) {
            lastAnnouncementRef.current = null;
            clearAnnouncement();
            return;
        }

        if (!shouldShowAnnouncement(createdAt)) {
            return;
        }

        // Avoid re-dispatching the same announcement notification
        const announcementKey = `${message}:${createdAt}`;
        if (lastAnnouncementRef.current === announcementKey) {
            return;
        }
        lastAnnouncementRef.current = announcementKey;

        const onDismiss = () => {
            if (createdAt !== undefined) {
                setDismissedTimestamp(createdAt);
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
    }, [isEnabled, message, createdAt, clearAnnouncement, notificationService]);
}

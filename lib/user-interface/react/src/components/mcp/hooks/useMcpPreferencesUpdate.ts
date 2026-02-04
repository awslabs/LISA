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

import { useEffect, useState } from 'react';
import {
    McpPreferences,
    UserPreferences,
    useUpdateUserPreferencesMutation
} from '@/shared/reducers/user-preferences.reducer';
import { useNotificationService } from '@/shared/util/hooks';
import { useAppDispatch } from '@/config/store';

interface UseMcpPreferencesUpdateOptions {
    successMessage?: string;
    errorMessage?: string;
}

/**
 * Custom hook to handle MCP preferences updates with loading states and notifications.
 * Provides optimistic UI updates and handles success/error notifications.
 */
export function useMcpPreferencesUpdate(options: UseMcpPreferencesUpdateOptions = {}) {
    const {
        successMessage = 'Successfully updated preferences',
        errorMessage = 'Error updating preferences'
    } = options;

    const dispatch = useAppDispatch();
    const notificationService = useNotificationService(dispatch);
    const [updatingItemId, setUpdatingItemId] = useState<string | null>(null);
    const [updatePreferences, {
        isSuccess: isUpdatingSuccess,
        isError: isUpdatingError,
        error: updateError,
        isLoading: isUpdating
    }] = useUpdateUserPreferencesMutation();

    // Handle success notification
    useEffect(() => {
        if (isUpdatingSuccess) {
            notificationService.generateNotification(successMessage, 'success');
            setUpdatingItemId(null);
        }
    }, [isUpdatingSuccess, notificationService, successMessage]);

    // Handle error notification
    useEffect(() => {
        if (isUpdatingError) {
            const errorDetail = 'data' in updateError 
                ? (updateError.data?.message ?? updateError.data) 
                : updateError.message;
            notificationService.generateNotification(
                `${errorMessage}: ${errorDetail}`,
                'error'
            );
            setUpdatingItemId(null);
        }
    }, [isUpdatingError, updateError, notificationService, errorMessage]);

    /**
     * Updates MCP preferences with optimistic UI state management.
     * 
     * @param itemId - The ID of the item being updated (for spinner tracking)
     * @param preferences - Current user preferences
     * @param mcpPrefsBuilder - Function that builds the new MCP preferences
     * @param setPreferences - Function to update local preferences state
     */
    const updateMcpPreferences = (
        itemId: string,
        preferences: UserPreferences,
        mcpPrefsBuilder: (currentMcpPrefs: McpPreferences) => McpPreferences,
        setPreferences: (prefs: UserPreferences) => void
    ) => {
        setUpdatingItemId(itemId);

        const existingMcpPrefs = preferences.preferences.mcp ?? {
            enabledServers: [],
            overrideAllApprovals: false
        };

        const newMcpPrefs = mcpPrefsBuilder(existingMcpPrefs);

        const updatedPreferences = {
            ...preferences,
            preferences: {
                ...preferences.preferences,
                mcp: {
                    ...preferences.preferences.mcp,
                    ...newMcpPrefs
                }
            }
        };

        setPreferences(updatedPreferences);
        updatePreferences(updatedPreferences);
    };

    return {
        updatingItemId,
        isUpdating,
        updateMcpPreferences
    };
}

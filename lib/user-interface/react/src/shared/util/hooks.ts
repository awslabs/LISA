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

import { Action, ThunkDispatch } from '@reduxjs/toolkit';
import { useCallback, useMemo } from 'react';
import NotificationService from '../notification/notification.service';
import { debounce, DebouncedFunc } from 'lodash';

/**
 * Creates a memoized NotificationService based on {@link dispatch}
 */
export function useNotificationService (
    dispatch: ThunkDispatch<any, any, Action>,
): ReturnType<typeof NotificationService> {
    return useMemo(() => NotificationService(dispatch), [dispatch]);
}

/**
 * Creates a debounced function that delays invoking {@link callback} until after {@link delay} milliseconds have elapsed since
 * the last time the debounced function was invoked.
 *
 * NOTE: The returned function has {@link callback} as a dependency so it is up to the caller to ensure {@link callback} doesn't
 * change or is memoized.
 *
 * @param {Function} callback The function to debounce.
 * @param {number} delay The number of milliseconds to delay.
 * @returns {Function} The memoized and debounced function.
 */
export function useDebounce<T extends (...args: any[]) => void> (callback: T, delay = 300): DebouncedFunc<T> {
    // useMemo is necessary because useCallback doesn't understand the dependencies for the debounced function
    const debounced = useMemo(() => debounce(callback, delay), [callback, delay]);

    return useCallback(debounced, [debounced]);
}

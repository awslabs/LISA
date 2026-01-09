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

import { Middleware } from '@reduxjs/toolkit';

/**
 * Middleware to handle RTK Query cancelled/aborted requests.
 *
 * When a component unmounts during navigation (common in Cypress tests),
 * RTK Query cancels in-flight requests. Without this middleware, those
 * queries can get stuck in a loading state when the component remounts.
 *
 * This middleware detects cancelled queries and logs them for debugging.
 * The combination of this middleware with keepUnusedDataFor and
 * refetchOnMountOrArgChange ensures queries retry properly on remount.
 */
export const rtkQueryErrorMiddleware: Middleware = () => (next) => (action: any) => {
    // Check if this is a rejected action by looking at the type
    if (action.type && action.type.endsWith('/rejected')) {
        // Check various error formats that indicate cancellation
        const error = action.error;
        const payload = action.payload;

        let isAborted = false;

        // Check action.error first (standard rejected actions)
        if (error) {
            isAborted =
                error.name === 'AbortError' ||
                error.message?.includes('abort') ||
                error.message?.includes('cancel');
        }

        // Check action.payload.error (rejectedWithValue actions)
        if (!isAborted && payload && typeof payload === 'object' && 'error' in payload) {
            const errorToCheck = payload.error;

            if (typeof errorToCheck === 'string') {
                isAborted = errorToCheck.toLowerCase().includes('abort');
            } else if (errorToCheck instanceof Error) {
                isAborted =
                    errorToCheck.name === 'AbortError' ||
                    errorToCheck.message?.includes('abort') ||
                    errorToCheck.message?.includes('cancel');
            }
        }

        if (isAborted) {
            // Log for debugging
            console.debug('[RTK Query] Detected cancelled request:', action.meta?.arg?.endpointName);
        }
    }

    return next(action);
};

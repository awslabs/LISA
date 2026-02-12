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

/**
 * Hook to calculate dynamic maximum rows for prompt input and preview
 * based on available window height.
 *
 * @returns An object containing:
 *   - dynamicMaxRows: The calculated maximum number of rows
 *   - LINE_HEIGHT: Pixels per row (24px)
 *   - PADDING: Total padding for the container
 */
export const useDynamicMaxRows = () => {
    const [dynamicMaxRows, setDynamicMaxRows] = useState(8);

    useEffect(() => {
        const calculateMaxRows = () => {
            const LINE_HEIGHT = 24; // pixels per row
            const RESERVED_UI_HEIGHT = 280; // model selector, buttons, status
            const MAX_INPUT_PERCENTAGE = 0.5; // 50% of viewport max

            const availableHeight = window.innerHeight - RESERVED_UI_HEIGHT;
            const maxInputHeight = availableHeight * MAX_INPUT_PERCENTAGE;
            const calculatedMaxRows = Math.floor(maxInputHeight / LINE_HEIGHT);

            // Clamp between 3 and 12 rows
            const clampedMaxRows = Math.max(3, Math.min(12, calculatedMaxRows));
            setDynamicMaxRows(clampedMaxRows);
        };

        calculateMaxRows();
        window.addEventListener('resize', calculateMaxRows);
        return () => window.removeEventListener('resize', calculateMaxRows);
    }, []);

    return {
        dynamicMaxRows,
        LINE_HEIGHT: 24,
        PADDING: 24,
    };
};

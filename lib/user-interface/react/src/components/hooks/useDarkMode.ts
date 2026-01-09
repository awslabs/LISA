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
 * Custom hook to detect and track dark mode by monitoring the 'awsui-dark-mode' class on the body element.
 * This hook automatically updates when the user toggles between light and dark themes via user-profile dropdown.
 *
 * @returns {boolean} isDarkMode - True if dark mode is active, false otherwise
 */
export const useDarkMode = (): boolean => {
    const [isDarkMode, setIsDarkMode] = useState(() =>
        document.body.classList.contains('awsui-dark-mode')
    );

    useEffect(() => {
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.attributeName === 'class') {
                    setIsDarkMode(document.body.classList.contains('awsui-dark-mode'));
                }
            });
        });

        observer.observe(document.body, { attributes: true });

        return () => observer.disconnect();
    }, []);

    return isDarkMode;
};

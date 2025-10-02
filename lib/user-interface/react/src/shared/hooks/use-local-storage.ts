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

import { useCallback, useState } from 'react';

export const save = (key: string, value: unknown) => {
    localStorage.setItem(key, JSON.stringify(value));
};

export const remove = (key: string) => localStorage.removeItem(key);

export const load = <T = unknown> (key: string): T | undefined => {
    const value = localStorage.getItem(key);
    try {
        if (!value) {
            return undefined;
        }
        return JSON.parse(value) as T;
    } catch {

        console.warn(
            `⚠️ The ${key} value that is stored in localStorage is incorrect. Try to remove the value ${key} from localStorage and reload the page`,
        );
        return undefined;
    }
};

export function useLocalStorage<T> (key: string, defaultValue?: T) {
    const [value, setValue] = useState<T | undefined>(() => load<T>(key) ?? defaultValue);

    const handleValueChange = useCallback(
        (newValue: T | undefined) => {
            if (newValue === undefined) {
                remove(key);
                return;
            }

            setValue(newValue);
            save(key, newValue);
        },
        [key],
    );

    const handleValueReset = useCallback(
        (newValue: T) => {
            setValue(newValue);
            remove(key);
        },
        [key],
    );

    return [value, handleValueChange, handleValueReset] as const;
}

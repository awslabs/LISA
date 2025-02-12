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

import _ from 'lodash';
import { SerializedError } from '@reduxjs/toolkit';

/**
 * Computes the difference between two JSON objects, recursively.
 *
 * This function takes two JSON objects as input and returns a new object that
 * contains the differences between the two. Works with nested objects.
 *
 * @param {object} [obj1={}] - The first JSON object to compare.
 * @param {object} [obj2={}] - The second JSON object to compare.
 * @returns {object} - A new object containing the differences between the two input objects.
 */
export function getJsonDifference (obj1: object = {}, obj2: object = {}): object {
    const output = {},
        merged = { ...obj1, ...obj2 }; // has properties of both

    for (const key in merged) {
        const value1 = obj1 && Object.keys(obj1).includes(key) ? obj1[key] : undefined;
        const value2 = obj2 && Object.keys(obj2).includes(key) ? obj2[key] : undefined;

        if (_.isPlainObject(value1) || _.isPlainObject(value2)) {
            const value = getJsonDifference(value1, value2); // recursively call
            if (Object.keys(value).length !== 0) {
                output[key] = value;
            }

        } else {
            if (!_.isEqual(value1, value2) && (value1 || value2)) {
                output[key] = value2;
            }
        }
    }
    return output;
}

/**
 * Normalizes error object to a SerializedError object
 * @param resource - resource name
 * @param error
 */
export const normalizeError = (resource: string, error: SerializedError | {
    status: string,
    data: any
}): SerializedError | undefined => {
    // type predicate to help discriminate between types
    function isResponseError<T extends {
        status: string,
        data: any
    }> (responseError: SerializedError | T): responseError is T {
        return (responseError as T)?.status !== undefined;
    }

    if (error !== undefined) {
        if (isResponseError(error)) {
            return {
                name: `${resource} Error`,
                message: error.status,
            };
        } else if (error) {
            return {
                name: error?.name || `${resource} Error`,
                message: error?.message,
            };
        }
    }

    return undefined;
};

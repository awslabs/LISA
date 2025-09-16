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

/**
 * Executes a function on a value only if the value is defined (not null or undefined).
 * This utility function provides a safe way to perform operations on potentially nullable values,
 * avoiding the need for explicit null checks.
 *
 * Inspired by Kotlin's `let` scope function, which allows you to execute a block of code
 * only when the receiver object is not null. This TypeScript implementation provides
 * similar functionality for handling nullable values in a functional programming style.
 *
 * @template T - The type of the input value
 * @template R - The type of the return value from the function
 * @param value - The value to check and potentially transform (can be null or undefined)
 * @param fn - The function to execute if the value is defined
 * @returns The result of the function if value is defined, otherwise undefined
 *
 * @example
 * // Basic usage with a string
 * const name: string | null = getUserName();
 * const upperName = letIfDefined(name, (n) => n.toUpperCase());
 * // upperName will be the uppercase name if name exists, or undefined if name is null
 *
 * @example
 * // Chaining operations safely
 * const user: User | undefined = getUser();
 * const userEmail = letIfDefined(user, (u) => u.email?.toLowerCase());
 *
 * @example
 * // Using with complex transformations
 * const config: Config | null = loadConfig();
 * const port = letIfDefined(config, (c) => c.server?.port ?? 3000);
 *
 * @example
 * // Avoiding nested if statements
 * // Instead of:
 * // if (data != null) {
 * //   return processData(data);
 * // }
 * // return undefined;
 *
 * // Use:
 * return letIfDefined(data, processData);
 */
export function letIfDefined<T, R> (value: T | null | undefined, fn: (value: T) => R): R | undefined {
    return value != null ? fn(value) : undefined;
}

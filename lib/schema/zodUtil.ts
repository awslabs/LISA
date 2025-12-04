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

import { z } from 'zod';

function isZodTransform (schema: z.ZodTypeAny): schema is z.ZodTransform<any, any> {
    return schema instanceof z.ZodTransform;
}

function isDefault (schema: z.ZodTypeAny): schema is z.ZodDefault<any> {
    return schema instanceof z.ZodDefault;
}

function isOptional (schema: z.ZodTypeAny): schema is z.ZodOptional<any> {
    return schema instanceof z.ZodOptional;
}

function isNullable (schema: z.ZodTypeAny): schema is z.ZodNullable<any> {
    return schema instanceof z.ZodNullable;
}

function isArray (schema: z.ZodTypeAny): schema is z.ZodArray<any> {
    return schema instanceof z.ZodArray || schema instanceof z.ZodSet;
}

function isString (schema: z.ZodTypeAny): schema is z.ZodString {
    return schema instanceof z.ZodString;
}

function isObject (schema: z.ZodTypeAny): schema is z.ZodObject<any> {
    return schema instanceof z.ZodObject;
}

// Builds an object consisting of the default values for all validators.
// https://github.com/colinhacks/zod/discussions/1953#discussioncomment-5695528
export function getDefaults<T extends z.ZodTypeAny> (schema: z.ZodObject<any> | z.ZodTransform<any, any>): z.infer<T> {

    if (isZodTransform(schema)) {
        // For transforms, we can't easily get defaults, return empty object
        return {} as z.infer<T>;
    }

    function getDefaultValue (schema: z.ZodTypeAny): unknown {
        // Handle default values
        if (isDefault(schema)) {
            const defaultVal = (schema as any)._def.defaultValue;
            return typeof defaultVal === 'function' ? defaultVal() : defaultVal;
        }
        
        // Handle optional - unwrap and get default of inner type
        if (isOptional(schema)) {
            return getDefaultValue(schema.unwrap());
        }
        
        // Handle nullable - unwrap and get default of inner type
        if (isNullable(schema)) {
            return getDefaultValue(schema.unwrap());
        }
        
        // return an empty array if it is
        if (isArray(schema)) return [];
        // return an empty string if it is
        if (isString(schema)) return '';
        // return content of object recursively
        if (isObject(schema)) return getDefaults(schema);
        
        return undefined;
    }

    if (!isObject(schema)) {
        return {} as z.infer<T>;
    }

    return Object.fromEntries(
        Object.entries(schema.shape).map(([key, value]) => {
            return [key, getDefaultValue(value as z.ZodTypeAny)];
        }),
    ) as z.infer<T>;
}

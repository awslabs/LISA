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

function isZodEffects (schema: z.ZodTypeAny): schema is z.ZodEffects<any> {
    return schema instanceof z.ZodEffects ||
         (schema._def && schema._def.typeName === z.ZodFirstPartyTypeKind.ZodEffects);
}

function isDefault (schema: z.ZodTypeAny): boolean {
    const type = schema._def.typeName;
    return (schema instanceof z.ZodDefault || type === z.ZodFirstPartyTypeKind.ZodDefault);
}

function isArray (schema: z.ZodTypeAny): boolean {
    const type = schema._def.typeName;
    return (schema instanceof z.ZodArray || type === z.ZodFirstPartyTypeKind.ZodArray || type === z.ZodFirstPartyTypeKind.ZodSet);
}

function isString (schema: z.ZodTypeAny): schema is z.ZodString {
    return schema instanceof z.ZodString || schema._def.type === z.ZodFirstPartyTypeKind.ZodString;
}

function isObject (schema: z.ZodTypeAny): schema is z.ZodObject<any> {
    return schema instanceof z.ZodObject || schema._def.type === z.ZodFirstPartyTypeKind.ZodObject;
}

// Builds an object consisting of the default values for all validators.
// https://github.com/colinhacks/zod/discussions/1953#discussioncomment-5695528
export function getDefaults<T extends z.ZodTypeAny> (schema: z.AnyZodObject | z.ZodEffects<any>): z.infer<T> {

    if (isZodEffects(schema)) {
        // Check if it's a recursive ZodEffect
        if (isZodEffects(schema.innerType())) return getDefaults(schema.innerType());
        // return schema inner shape as a fresh zodObject
        return getDefaults(z.ZodObject.create(schema.innerType().shape));
    }

    function getDefaultValue (schema: z.ZodTypeAny): unknown {
        if (isDefault(schema)) return schema._def.defaultValue();
        // return an empty array if it is
        if (isArray(schema)) return [];
        // return an empty string if it is
        if (isString(schema)) return '';
        // return content of object recursively
        if (isObject(schema)) return getDefaults(schema);

        if (!('innerType' in schema._def)) return undefined;
        return getDefaultValue(schema._def.innerType);
    }

    return Object.fromEntries(
        Object.entries(schema.shape).map(([key, value]) => {
            return [key, getDefaultValue(value as z.ZodTypeAny)];
        }),
    );
}

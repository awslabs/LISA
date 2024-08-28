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

type rangeValidatorProps = {
    min?: number;
    max?: number;
    isFloat?: boolean;
    required?: boolean;
    includeMin?: boolean;
    includeMax?: boolean;
    alternateValues?: string[];
};

/**
 * Creates a validator for ensuring a number meets the required conditions
 *
 * @param fieldName Name of the field being validated
 * @param inputProps Properties that ensure the validity of the field
 * @returns A validator for the field that ensures the desired requirements
 */
export const numberValidator = (
    fieldName: string,
    inputProps?: rangeValidatorProps
) => {
    // Create properties by merging the defaults with the provided input properties
    const props = {
        min: Number.NEGATIVE_INFINITY, // Specifies the smallest number allowed (default is infinitely negative to allow for any number)
        max: Number.POSITIVE_INFINITY, // Specifies the largest number allowed (default is infinitely positive to allow for any number)
        isFloat: false, // The number is assumed to be an Integer unless specified (default is that it is an Integer)
        required: false, // Specify whether this field is required for submission and must not be empty (default is that the field is not required)
        includeMin: true, // Whether the specified minimum is a valid number option (default is that it is valid)
        includeMax: true, // Whether the specified maximum is a valid number option (default is that it is valid)
        ...inputProps
    };

    // Create range message
    let rangeMessage = '';
    if (props.min !== Number.NEGATIVE_INFINITY && props.max !== Number.POSITIVE_INFINITY){
        // Create range message
        rangeMessage = ` value in the range ${props.includeMin ? '[' : '('}${props.min},${props.max}${props.includeMax ? ']' : ')'}`;
    } else if (props.max === Number.POSITIVE_INFINITY) {
        // If there is a min, but not a max, create greater than message
        rangeMessage = ` value greater than ${props.includeMin ? 'or equal to ' : ''}${props.min}`;
    } else if (props.min === Number.NEGATIVE_INFINITY) {
        // If there is a max, but not a min, create less than message
        rangeMessage = ` value less than ${props.includeMax ? 'or equal to ' : ''}${props.max}`;
    }

    // Create validation message for errors
    const validationMessage = `${fieldName}${props.required ? ' is required and' : '' } must be ${
        props.isFloat ? 'a float' : 'an integer'}${rangeMessage}${
        props.alternateValues ? ' or be one of the following values: ' + props.alternateValues.map((value) => `'${value}'`).join(', ') : ''}`;


    // Create base number validator
    let numberContext = z.coerce.number({
        invalid_type_error: validationMessage,
    });

    // Add min/max check based on min and max inclusions
    numberContext = props.includeMin ? numberContext.gte(props.min, { message: validationMessage }) : numberContext.gt(props.min, { message: validationMessage });
    numberContext = props.includeMax ? numberContext.lte(props.max, { message: validationMessage }) : numberContext.lt(props.max, { message: validationMessage });

    // Create a wrapper validator that allows for possible text values
    let wrapperContext: any = numberContext;

    // Appends alternative non-number allowed values
    if (props.alternateValues) {
        props.alternateValues.forEach((value) => {
            wrapperContext = z.union([wrapperContext, z.literal(value)], {errorMap: () => ({ message: validationMessage})});
        });
    }

    if (!props.required) {
        // Marking as optional alone isn't sufficient if the number context includes a
        // minimum or maximum property which is always the case here. Adding the literal
        // allows for a truly optional value when parsing
        wrapperContext = wrapperContext.optional().or(z.literal(''));
    }

    return wrapperContext;
};

export const floatValidator = (fieldName: string, required = false, positive = false) => {
    return numberValidator(fieldName, {
        isFloat: true,
        required,
        min: positive ? 0 : Number.NEGATIVE_INFINITY,
        includeMin: false // If positive, can't be zero, will never reach Number.NEGATIVE_INFINITY regardless
    });
};

export const positiveIntValidator = (fieldName: string, inputProps : rangeValidatorProps = { }) => {
    return numberValidator(fieldName,
        {
            min: 1,
            ...inputProps
        });
};

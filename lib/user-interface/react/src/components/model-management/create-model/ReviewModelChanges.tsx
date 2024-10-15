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

import React, { ReactElement } from 'react';
import _ from 'lodash';
import { Alert, SpaceBetween, TextContent } from '@cloudscape-design/components';
import Container from '@cloudscape-design/components/container';
import { SerializedError } from '@reduxjs/toolkit';

export type ReviewModelChangesProps = {
    jsonDiff: object,
    error?: SerializedError
};

export function ReviewModelChanges (props: ReviewModelChangesProps) : ReactElement {
    /**
     * Converts a JSON object into an outline structure represented as React nodes.
     *
     * @param {object} [json={}] - The JSON object to be converted.
     * @returns {React.ReactNode[]} - An array of React nodes representing the outline structure.
     */
    function jsonToOutline (json = {}) {
        const output: React.ReactNode[] = [];

        for (const key in json) {
            const value = json[key];
            output.push((<li><p><strong>{_.startCase(key)}</strong>{_.isPlainObject(value) ? '' : `: ${value}`}</p></li>));

            if (_.isPlainObject(value)) {
                const recursiveJson = jsonToOutline(value); // recursively call
                output.push((recursiveJson));
            }
        }
        return <ul>{output}</ul>;
    }

    return (
        <SpaceBetween size={'s'}>
            <Container>
                <TextContent>
                    {_.isEmpty(props.jsonDiff) ? <p>No changes detected</p> : jsonToOutline(props.jsonDiff)}
                </TextContent>
            </Container>

            { props?.error && <Alert
                type='error'
                statusIconAriaLabel='Error'
                header={props?.error?.name || 'Model Error'}
            >
                { props?.error?.message }
            </Alert>}
        </SpaceBetween>
    );
}

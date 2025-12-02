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

export type ReviewChangesProps = {
    jsonDiff: object,
    error?: SerializedError,
    info?: string
};

export function ReviewChanges (props: ReviewChangesProps): ReactElement {
    const { jsonDiff, info, error } = props;

    /**
     * Converts a JSON object into an outline structure represented as React nodes.
     *
     * @param {object} [json={}] - The JSON object to be converted.
     * @param propIndex - The index of the current property being processed.
     * @returns {React.ReactNode[]} - An array of React nodes representing the outline structure.
     */
    function jsonToOutline (json: object = {}, propIndex = { index: 0 }): React.JSX.Element {
        const output: React.ReactNode[] = [];
        if (!_.isObject(json)) {
            return (<li key={propIndex.index++}><p>{json}</p></li>);
        }


        for (const key in json) {
            const value = json[key];

            // Special handling for allowedGroups - show "Public" when empty
            if (key === 'allowedGroups' && _.isArray(value) && _.isEmpty(value)) {
                output.push((
                    <li key={propIndex.index++}><p><strong>{_.startCase(key)}</strong>: Public</p>
                    </li>));
                continue;
            }

            if (key === 'scheduling' && (value === null || value === undefined)) {
                output.push((
                    <li key={propIndex.index++}><p><strong>Auto Scaling Schedule</strong>: Disabled - Model will always be on.</p>
                    </li>));
                continue;
            }

            if (key === 'scheduleType' || key === 'timezone' || key === 'dailySchedule' || key === 'recurringSchedule' || key === 'scheduleEnabled') {
                if (value === undefined || value === null) {
                    continue;
                }
            }

            // Handle nested scheduling objects that contain undefined values
            if (key === 'scheduling' && _.isPlainObject(value)) {
                // Check if this is explicitly disabled (scheduleEnabled === false or scheduleType === 'NONE')
                const isExplicitlyDisabled = value.scheduleEnabled === false || value.scheduleType === 'NONE';

                if (isExplicitlyDisabled) {
                    output.push((
                        <li key={propIndex.index++}><p><strong>Auto Scaling Schedule</strong>: Disabled - Model will always be on.</p>
                        </li>));
                    continue;
                }

                // If it's a valid schedule, filter out undefined nested properties
                const cleanedScheduling = {};
                for (const [schedKey, schedValue] of Object.entries(value)) {
                    if (schedValue !== undefined && schedValue !== null) {
                        if (schedKey === 'dailySchedule' && _.isPlainObject(schedValue)) {
                            // Clean dailySchedule object
                            const cleanedDailySchedule = {};
                            for (const [dayKey, dayValue] of Object.entries(schedValue)) {
                                if (dayValue !== undefined && dayValue !== null && _.isPlainObject(dayValue)) {
                                    const cleanedDaySchedule = {};
                                    for (const [dayPropKey, dayPropValue] of Object.entries(dayValue)) {
                                        if (dayPropValue !== undefined && dayPropValue !== null && dayPropValue !== '') {
                                            cleanedDaySchedule[dayPropKey] = dayPropValue;
                                        }
                                    }
                                    if (Object.keys(cleanedDaySchedule).length > 0) {
                                        cleanedDailySchedule[dayKey] = cleanedDaySchedule;
                                    }
                                } else if (dayValue !== undefined && dayValue !== null && dayValue !== '') {
                                    cleanedDailySchedule[dayKey] = dayValue;
                                }
                            }
                            if (Object.keys(cleanedDailySchedule).length > 0) {
                                cleanedScheduling[schedKey] = cleanedDailySchedule;
                            }
                        } else if (schedKey === 'recurringSchedule' && _.isPlainObject(schedValue)) {
                            // Clean recurringSchedule object (day schedule for recurring type)
                            const cleanedRecurringSchedule = {};
                            for (const [recKey, recValue] of Object.entries(schedValue)) {
                                if (recValue !== undefined && recValue !== null && recValue !== '') {
                                    cleanedRecurringSchedule[recKey] = recValue;
                                }
                            }
                            if (Object.keys(cleanedRecurringSchedule).length > 0) {
                                cleanedScheduling[schedKey] = cleanedRecurringSchedule;
                            }
                        } else {
                            cleanedScheduling[schedKey] = schedValue;
                        }
                    }
                }

                // Check if scheduling is effectively disabled
                if (Object.keys(cleanedScheduling).length === 0) {
                    output.push((
                        <li key={propIndex.index++}><p><strong>Auto Scaling Schedule</strong>: Disabled - Model will always be on.</p>
                        </li>));
                    continue;
                }

                // Only show scheduling if it has valid content
                if (Object.keys(cleanedScheduling).length > 0) {
                    output.push((
                        <li key={propIndex.index++}><p><strong>{_.startCase(key)}</strong></p></li>
                    ));
                    output.push(jsonToOutline(cleanedScheduling, propIndex));
                }
                continue;
            }

            const isNested = _.isObject(value);
            output.push((
                <li key={propIndex.index++}><p><strong>{_.startCase(key)}</strong>{isNested ? '' : `: ${value}`}</p>
                </li>));
            if (_.isPlainObject(value)) {
                output.push((jsonToOutline(value, propIndex)));
            } else if (_.isArray(value)) {
                for (const item of value) {
                    output.push((jsonToOutline(item, propIndex)));
                    if (_.isObject(item)) {
                        output.push((<hr />));
                    }
                }
            }
        }
        return <ul>{output}</ul>;
    }

    return (
        <SpaceBetween size={'s'}>
            <Container>
                <TextContent>
                    {_.isEmpty(jsonDiff) ? <p>No changes detected</p> : jsonToOutline(jsonDiff)}
                </TextContent>

            </Container>

            {info && <Alert type='info'>{info}</Alert>}

            {error &&
                <Alert type='error' header={error?.name || 'Diff Error'}>
                    {error?.message}
                </Alert>
            }
        </SpaceBetween>
    );
}

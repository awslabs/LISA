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

import React, { ReactElement, useEffect } from 'react';
import { FormProps } from '../../../shared/form/form-props';
import FormField from '@cloudscape-design/components/form-field';
import Select from '@cloudscape-design/components/select';
import Toggle from '@cloudscape-design/components/toggle';
import TimeInput from '@cloudscape-design/components/time-input';
import { Grid, Header, SpaceBetween, Container, Box, Alert } from '@cloudscape-design/components';

import { IScheduleConfig, ScheduleType, IDaySchedule, IWeeklySchedule } from '../../../shared/model/model-management.model';

type ScheduleConfigProps = FormProps<IScheduleConfig> & {
    isEdit: boolean;
};

// Generate timezone options from IANA timezone database
const generateTimezoneOptions = () => {
    try {
        const allTimezones = Intl.supportedValuesOf('timeZone');
        console.log('Available IANA timezones:', allTimezones.slice(0, 10)); // Log first 10 for debugging

        return allTimezones
            .map((timezone) => ({
                label: timezone,
                value: timezone
            }))
            .sort((a, b) => a.label.localeCompare(b.label)); // Sort alphabetically by label
    } catch (error) {
        console.warn('Intl.supportedValuesOf not supported, falling back to common timezones:', error);
        // Fallback to common timezones if the API is not supported
        return [
            { label: 'America/New_York', value: 'America/New_York' },
            { label: 'America/Chicago', value: 'America/Chicago' },
            { label: 'America/Denver', value: 'America/Denver' },
            { label: 'America/Los_Angeles', value: 'America/Los_Angeles' },
            { label: 'Europe/London', value: 'Europe/London' },
            { label: 'Europe/Paris', value: 'Europe/Paris' },
            { label: 'Europe/Berlin', value: 'Europe/Berlin' },
            { label: 'Asia/Tokyo', value: 'Asia/Tokyo' },
            { label: 'Asia/Shanghai', value: 'Asia/Shanghai' },
            { label: 'Asia/Singapore', value: 'Asia/Singapore' },
            { label: 'Australia/Sydney', value: 'Australia/Sydney' },
        ];
    }
};

const timezoneOptions = generateTimezoneOptions();

const scheduleTypeOptions = [
    { label: 'Daily', value: ScheduleType.DAILY },
    { label: 'Recurring', value: ScheduleType.RECURRING },
];

// Validation helper functions
const isValidTimeFormat = (time: string): boolean => {
    if (!time) return true; // Empty time is allowed for optional fields
    const timeRegex = /^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$/;
    return timeRegex.test(time);
};

const timeToMinutes = (time: string): number => {
    if (!time || !isValidTimeFormat(time)) return 0;
    const [hours, minutes] = time.split(':').map(Number);
    return hours * 60 + minutes;
};

// Enhanced validation function with clearer error messages
const validateTimePair = (startTime: string, endTime: string): string | undefined => {
    if (!startTime || !endTime) return undefined; // Skip validation if either time is empty
    if (!isValidTimeFormat(startTime) || !isValidTimeFormat(endTime)) return undefined;

    const startMinutes = timeToMinutes(startTime);
    const endMinutes = timeToMinutes(endTime);

    // Check if end time is earlier than start time (invalid for same-day scheduling)
    if (endMinutes <= startMinutes) {
        return 'Stop time must be later than Start time on the same day.';
    }

    // Check minimum 2-hour gap
    if (endMinutes - startMinutes < 120) {
        return 'Stop time must be at least 2 hours after Start time.';
    }

    return undefined; // Valid
};

const validateDailySchedule = (dailySchedule?: IDaySchedule): string | undefined => {
    if (!dailySchedule) return 'Recurring schedule must be configured when selected.';

    const { startTime, stopTime } = dailySchedule;

    if (!startTime && !stopTime) {
        return 'Recurring schedule must have both start and stop times.';
    }

    if (!startTime) return 'Start time is required for recurring schedule.';
    if (!stopTime) return 'Stop time is required for recurring schedule.';

    if (!isValidTimeFormat(startTime)) return 'Start time must be in HH:MM format (24-hour).';
    if (!isValidTimeFormat(stopTime)) return 'Stop time must be in HH:MM format (24-hour).';

    // Use enhanced validation for time pair
    const timePairError = validateTimePair(startTime, stopTime);
    if (timePairError) return timePairError;

    return undefined;
};

const validateWeeklySchedule = (weeklySchedule?: IWeeklySchedule): { [key: string]: string } => {
    const errors: { [key: string]: string } = {};

    if (!weeklySchedule) {
        errors.general = 'Daily schedule must be configured when selected.';
        return errors;
    }

    const daysOfWeek: (keyof IWeeklySchedule)[] = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
    let hasAtLeastOneDay = false;

    daysOfWeek.forEach((day) => {
        const daySchedule = weeklySchedule[day];
        if (daySchedule && daySchedule.startTime && daySchedule.stopTime) {
            hasAtLeastOneDay = true;

            const { startTime, stopTime } = daySchedule;

            // Validate time formats
            if (startTime && !isValidTimeFormat(startTime)) {
                errors[`${day}_startTime`] = 'Start time must be in HH:MM format (24-hour).';
            }

            if (stopTime && !isValidTimeFormat(stopTime)) {
                errors[`${day}_stopTime`] = 'Stop time must be in HH:MM format (24-hour).';
            }

            // Use enhanced validation for time pair with clearer error messages
            if (startTime && stopTime && isValidTimeFormat(startTime) && isValidTimeFormat(stopTime)) {
                const timePairError = validateTimePair(startTime, stopTime);
                if (timePairError) {
                    errors[`${day}_times`] = timePairError;
                }
            }
        } else if (daySchedule && (daySchedule.startTime || daySchedule.stopTime)) {
            // Partial schedule validation
            if (daySchedule.startTime && !daySchedule.stopTime) {
                errors[`${day}_stopTime`] = 'Stop time is required when Start time is provided.';
            }
            if (daySchedule.stopTime && !daySchedule.startTime) {
                errors[`${day}_startTime`] = 'Start time is required when Stop time is provided.';
            }
        }
    });

    if (!hasAtLeastOneDay) {
        errors.general = 'At least one day must have a schedule configured.';
    }

    return errors;
};

export function ScheduleConfig (props: ScheduleConfigProps): ReactElement {
    const isScheduleEnabled = props.item.scheduleEnabled;
    const scheduleType = props.item.scheduleType;
    const showScheduleOptions = isScheduleEnabled && scheduleType !== ScheduleType.NONE;
    const showDailySchedule = showScheduleOptions && scheduleType === ScheduleType.RECURRING;
    const showWeeklySchedule = showScheduleOptions && scheduleType === ScheduleType.DAILY;

    // State for additional time slots toggle
    const [validationErrors, setValidationErrors] = React.useState<{ [key: string]: string }>({});

    const selectedTimezone = props.item.timezone ? timezoneOptions.find((option) => option.value === props.item.timezone) : null;
    const selectedScheduleType = scheduleType !== ScheduleType.NONE ? scheduleTypeOptions.find((option) => option.value === scheduleType) : null;

    // Run validation whenever schedule data changes
    useEffect(() => {
        const errors: { [key: string]: string } = {};

        if (isScheduleEnabled && scheduleType !== ScheduleType.NONE) {
            // Validate timezone selection
            if (!props.item.timezone) {
                errors.timezone = 'Timezone must be selected when auto scaling is enabled.';
            }

            if (scheduleType === ScheduleType.RECURRING) {
                const dailyError = validateDailySchedule(props.item.dailySchedule);
                if (dailyError) {
                    errors.dailySchedule = dailyError;
                }
            } else if (scheduleType === ScheduleType.DAILY) {
                const weeklyErrors = validateWeeklySchedule(props.item.weeklySchedule);
                Object.assign(errors, weeklyErrors);
            }
        }

        setValidationErrors(errors);
    }, [isScheduleEnabled, scheduleType, props.item.dailySchedule, props.item.weeklySchedule, props.item.timezone]);

    // Helper functions for weekly schedule management
    const getDefaultWeeklySchedule = (): IWeeklySchedule => ({
        monday: undefined,
        tuesday: undefined,
        wednesday: undefined,
        thursday: undefined,
        friday: undefined,
        saturday: undefined,
        sunday: undefined,
    });

    const weeklySchedule = props.item.weeklySchedule || getDefaultWeeklySchedule();

    // Helper functions for day schedule management
    const updateDaySchedule = (dayName: keyof IWeeklySchedule, daySchedule: IDaySchedule | undefined) => {
        const updatedWeeklySchedule = {
            ...weeklySchedule,
            [dayName]: daySchedule
        };
        props.setFields({ 'weeklySchedule': updatedWeeklySchedule });
    };

    // Helper functions for days of the week
    const getDaysOfWeek = () => [
        { key: 'monday' as keyof IWeeklySchedule, label: 'Monday' },
        { key: 'tuesday' as keyof IWeeklySchedule, label: 'Tuesday' },
        { key: 'wednesday' as keyof IWeeklySchedule, label: 'Wednesday' },
        { key: 'thursday' as keyof IWeeklySchedule, label: 'Thursday' },
        { key: 'friday' as keyof IWeeklySchedule, label: 'Friday' },
        { key: 'saturday' as keyof IWeeklySchedule, label: 'Saturday' },
        { key: 'sunday' as keyof IWeeklySchedule, label: 'Sunday' }
    ];

    return (
        <SpaceBetween size={'s'}>
            <Container header={
                <SpaceBetween size='xs'>
                    <Header variant='h3'>Resource Scheduling</Header>
                    <Box>
                        <p>Manage auto scaling for self-hosted models</p>
                    </Box>
                </SpaceBetween>
            }>
                <SpaceBetween size={'s'}>
                    <FormField
                        label=''
                        description=''
                        errorText={props.formErrors?.scheduleEnabled}
                    >
                        <Toggle
                            checked={isScheduleEnabled}
                            onChange={({ detail }) => {
                                props.setFields({
                                    'scheduleEnabled': detail.checked,
                                    // Keep schedule type as NONE when enabling so user must choose
                                    'scheduleType': detail.checked ? ScheduleType.NONE : ScheduleType.NONE,
                                    // Clear schedules when disabling
                                    'weeklySchedule': detail.checked ? props.item.weeklySchedule : undefined,
                                    'dailySchedule': detail.checked ? props.item.dailySchedule : undefined
                                });
                            }}
                            onBlur={() => props.touchFields(['scheduleEnabled'])}
                        >
                            Auto Scaling
                        </Toggle>
                    </FormField>

                    {!isScheduleEnabled && (
                        <Alert
                            statusIconAriaLabel='Warning'
                            type='warning'
                        >
                            When Auto Scaling is deactivated, the model will run 24/7
                        </Alert>
                    )}

                    {isScheduleEnabled && (
                        <FormField
                            label=''
                            description='Choose how the model should be scheduled'
                            errorText={props.formErrors?.scheduleType}
                        >
                            <Select
                                selectedOption={selectedScheduleType}
                                placeholder='Choose a scheduling method: Daily or Recurring'
                                onChange={({ detail }) => {
                                    props.setFields({
                                        'scheduleType': detail.selectedOption.value as ScheduleType,
                                        // Clear schedules when changing type
                                        'weeklySchedule': undefined,
                                        'dailySchedule': undefined
                                    });
                                }}
                                options={scheduleTypeOptions}
                                onBlur={() => props.touchFields(['scheduleType'])}
                            />
                        </FormField>
                    )}

                    {showScheduleOptions && (
                        <FormField
                            label='Timezone'
                            description='Select the timezone for schedule times (required)'
                            errorText={props.formErrors?.timezone || validationErrors.timezone}
                        >
                            <Select
                                selectedOption={selectedTimezone}
                                placeholder='Select a timezone'
                                onChange={({ detail }) => {
                                    props.setFields({ 'timezone': detail.selectedOption.value });
                                }}
                                options={timezoneOptions}
                                onBlur={() => props.touchFields(['timezone'])}
                                filteringType='auto'
                                invalid={!!(props.formErrors?.timezone || validationErrors.timezone)}
                            />
                        </FormField>
                    )}

                    {showDailySchedule && (
                        <>
                            <SpaceBetween size='s'>
                                <Header variant='h3'>Recurring Schedule</Header>
                                <Box>
                                    <p>Set a Start and a Stop time to be applied to every day of the week.</p>
                                </Box>
                            </SpaceBetween>

                            <Grid gridDefinition={[{ colspan: 6 }, { colspan: 6 }]}>
                                <FormField
                                    label='Start Time'
                                    description='Time to scale up the model (24-hour format)'
                                    errorText={props.formErrors?.dailySchedule?.startTime}
                                >
                                    <TimeInput
                                        value={props.item.dailySchedule?.startTime || ''}
                                        onChange={({ detail }) => {
                                            const updatedDailySchedule = {
                                                ...props.item.dailySchedule,
                                                startTime: detail.value,
                                                stopTime: props.item.dailySchedule?.stopTime || ''
                                            };
                                            props.setFields({ 'dailySchedule': updatedDailySchedule });
                                        }}
                                        onBlur={() => props.touchFields(['dailySchedule.startTime'])}
                                        format='hh:mm'
                                        placeholder='HH:MM'
                                    />
                                </FormField>

                                <FormField
                                    label='Stop Time'
                                    description='Time to scale down the model (must be at least 2 hours after start time)'
                                    errorText={props.formErrors?.dailySchedule?.stopTime || validationErrors.dailySchedule}
                                >
                                    <TimeInput
                                        value={props.item.dailySchedule?.stopTime || ''}
                                        onChange={({ detail }) => {
                                            const updatedDailySchedule = {
                                                ...props.item.dailySchedule,
                                                startTime: props.item.dailySchedule?.startTime || '',
                                                stopTime: detail.value
                                            };
                                            props.setFields({ 'dailySchedule': updatedDailySchedule });
                                        }}
                                        onBlur={() => props.touchFields(['dailySchedule.stopTime'])}
                                        format='hh:mm'
                                        placeholder='HH:MM'
                                    />
                                </FormField>
                            </Grid>
                        </>
                    )}

                    {showWeeklySchedule && (
                        <>
                            <SpaceBetween size='s'>
                                <Header variant='h3'>Daily Schedule</Header>
                                <p>Set both a Start and a Stop time for each day of the week as needed. The model will not be available on days without a defined schedule.</p>

                                {/* Table Header */}
                                <Grid gridDefinition={[{ colspan: 4 }, { colspan: 4 }, { colspan: 4 }]}>
                                    <Box fontWeight='bold'>Day</Box>
                                    <Box fontWeight='bold'>Start Time (24-hour)</Box>
                                    <Box fontWeight='bold'>Stop Time (min 2hrs after start)</Box>
                                </Grid>

                                {/* Table Rows */}
                                {getDaysOfWeek().map((day) => {
                                    const daySchedule = weeklySchedule[day.key];
                                    const startTimeError = validationErrors[`${day.key}_startTime`];
                                    const stopTimeError = validationErrors[`${day.key}_stopTime`];
                                    const timesError = validationErrors[`${day.key}_times`];

                                    return (
                                        <Grid key={day.key} gridDefinition={[{ colspan: 4 }, { colspan: 4 }, { colspan: 4 }]}>
                                            <Box padding={{ vertical: 's' }}>
                                                <strong>{day.label}</strong>
                                            </Box>
                                            <FormField
                                                errorText={startTimeError}
                                            >
                                                <TimeInput
                                                    value={daySchedule?.startTime || ''}
                                                    onChange={({ detail }) => {
                                                        const newSchedule = detail.value ? {
                                                            startTime: detail.value,
                                                            stopTime: daySchedule?.stopTime || ''
                                                        } : undefined;
                                                        updateDaySchedule(day.key, newSchedule);
                                                    }}
                                                    format='hh:mm'
                                                    placeholder='HH:MM'
                                                />
                                            </FormField>
                                            <FormField
                                                errorText={stopTimeError || timesError}
                                            >
                                                <TimeInput
                                                    value={daySchedule?.stopTime || ''}
                                                    onChange={({ detail }) => {
                                                        const newSchedule = detail.value ? {
                                                            startTime: daySchedule?.startTime || '',
                                                            stopTime: detail.value
                                                        } : undefined;
                                                        updateDaySchedule(day.key, newSchedule);
                                                    }}
                                                    format='hh:mm'
                                                    placeholder='HH:MM'
                                                />
                                            </FormField>
                                        </Grid>
                                    );
                                })}
                            </SpaceBetween>
                        </>
                    )}
                </SpaceBetween>
            </Container>

        </SpaceBetween>
    );
}

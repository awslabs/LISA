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
import { IModel, ModelStatus, ScheduleType } from '../../shared/model/model-management.model';
import { StatusIndicatorProps } from '@cloudscape-design/components/status-indicator';
import { CollectionPreferencesProps, StatusIndicator, Box } from '@cloudscape-design/components';
import { DEFAULT_PAGE_SIZE_OPTIONS } from '../../shared/preferences/common-preferences';
import Badge from '@cloudscape-design/components/badge';

type EnumDictionary<T extends string | symbol | number, U> = {
    [K in T]: U;
};

export const MODEL_STATUS_LOOKUP: EnumDictionary<ModelStatus, StatusIndicatorProps.Type> = {
    [ModelStatus.Creating]: 'in-progress',
    [ModelStatus.InService]: 'success',
    [ModelStatus.Stopping]: 'in-progress',
    [ModelStatus.Starting]: 'in-progress',
    [ModelStatus.Stopped]: 'stopped',
    [ModelStatus.Updating]: 'in-progress',
    [ModelStatus.Deleting]: 'in-progress',
    [ModelStatus.Failed]: 'error',
};

// Utility functions for schedule display
const formatScheduleType = (model: IModel): string => {
    const scheduling = model.autoScalingConfig?.scheduling;
    
    if (!scheduling?.scheduleEnabled || !scheduling?.scheduleType || scheduling.scheduleType === ScheduleType.NONE) {
        return '24/7';
    }
    
    switch (scheduling.scheduleType) {
        case ScheduleType.DAILY:
            return 'Daily Schedule';
        case ScheduleType.RECURRING:
            return 'Recurring Schedule';
        default:
            return '24/7';
    }
};

const formatScheduleDetails = (model: IModel) => {
    const scheduling = model.autoScalingConfig?.scheduling;
    
    if (!scheduling?.scheduleEnabled || !scheduling?.scheduleType || scheduling.scheduleType === ScheduleType.NONE) {
        return (
            <Box color="text-status-inactive">
                <em>Model runs continuously without scheduled downtime</em>
            </Box>
        );
    }
    
    const timezone = scheduling.timezone || 'UTC';
    
    if (scheduling.scheduleType === ScheduleType.RECURRING && scheduling.dailySchedule) {
        const { startTime, stopTime } = scheduling.dailySchedule;
        return (
            <Box>
                <div><strong>Every day:</strong> {startTime} - {stopTime}</div>
                <div><small>Timezone: {timezone}</small></div>
            </Box>
        );
    }
    
    if (scheduling.scheduleType === ScheduleType.DAILY && scheduling.weeklySchedule) {
        const daysWithSchedule = Object.entries(scheduling.weeklySchedule)
            .filter(([_, daySchedules]) => daySchedules && daySchedules.length > 0)
            .map(([day, daySchedules]) => {
                const schedule = daySchedules![0]; // Use first schedule for each day
                const dayName = day.charAt(0).toUpperCase() + day.slice(1);
                return `${dayName}: ${schedule.startTime} - ${schedule.stopTime}`;
            });
        
        if (daysWithSchedule.length === 0) {
            return (
                <Box color="text-status-inactive">
                    <em>No days configured - Model runs 24/7</em>
                </Box>
            );
        }
        
        return (
            <Box>
                {daysWithSchedule.map((daySchedule, index) => (
                    <div key={index}><small>{daySchedule}</small></div>
                ))}
                <div><small>Timezone: {timezone}</small></div>
            </Box>
        );
    }
    
    return (
        <Box color="text-status-inactive">
            <em>Schedule configured but details unavailable</em>
        </Box>
    );
};

export const createCardDefinitions = (defaultModelId?: string) => ({
    header: (model: IModel) => <div>{model.modelId} {model.modelId === defaultModelId && <Badge>DEFAULT</Badge>}</div>,
    sections: [
        {
            id: 'modelName',
            header: 'Name',
            content: (model: IModel) => model.modelName,
        },
        {
            id: 'modelFeatures',
            header: 'Model Features',
            content: (model: IModel) => model.features ? model.features.map((feat) => feat.name).join(', ') : '-',
        },
        {
            id: 'modelType',
            header: 'Type',
            content: (model: IModel) => model.modelType,
        },
        {
            id: 'modelUrl',
            header: 'URL',
            content: (model: IModel) => model.modelUrl ? model.modelUrl : '-',
        },
        {
            id: 'streaming',
            header: 'Streaming',
            content: (model: IModel) => String(model.streaming),
        },
        {
            id: 'hosting',
            header: 'Hosted in LISA',
            content: (model: IModel) => String(model.containerConfig !== null && model.autoScalingConfig !== null && model.loadBalancerConfig !== null),
        },
        {
            id: 'instanceType',
            header: 'Instance Type',
            content: (model: IModel) => model.instanceType ?  model.instanceType : '-',
        },
        {
            id: 'scheduleType',
            header: 'Schedule Type',
            content: (model: IModel) => formatScheduleType(model),
        },
        {
            id: 'scheduleDetails',
            header: 'Schedule Details',
            content: (model: IModel) => formatScheduleDetails(model),
        },
        {
            id: 'modelDescription',
            header: 'Description',
            content: (model: IModel) => model.modelDescription ? model.modelDescription : '-',
        },
        {
            id: 'allowedGroups',
            header: 'Allowed Groups',
            content: (model: IModel) => model?.allowedGroups?.length > 0 ? `${model.allowedGroups.join(', ')}` : <em>(public)</em>,
        },
        {
            id: 'modelStatus',
            header: 'Status',
            content: (model: IModel) => (
                <StatusIndicator type={MODEL_STATUS_LOOKUP[model.status]}>{model.status}</StatusIndicator>
            ),
        },
    ],
});

// Keep the original export for backward compatibility
export const CARD_DEFINITIONS = createCardDefinitions();

export const PAGE_SIZE_OPTIONS = DEFAULT_PAGE_SIZE_OPTIONS('Models');

export const DEFAULT_PREFERENCES: CollectionPreferencesProps.Preferences = {
    pageSize: 12,
    visibleContent: ['modelName', 'modelFeatures', 'modelType', 'modelUrl', 'streaming', 'hosting', 'instanceType', 'scheduleType', 'modelDescription', 'allowedGroups', 'modelStatus'],
};

export const VISIBLE_CONTENT_OPTIONS = [
    {
        label: 'Displayed Properties',
        options: [
            { id: 'modelName', label: 'Name' },
            { id: 'modelFeatures', label: 'Features'},
            { id: 'modelType', label: 'Type' },
            { id: 'modelUrl', label: 'URL' },
            { id: 'streaming', label: 'Streaming' },
            { id: 'hosting', label: 'LISA-Hosted Infrastructure' },
            { id: 'instanceType', label: 'Instance Type' },
            { id: 'scheduleType', label: 'Schedule Type' },
            { id: 'scheduleDetails', label: 'Schedule Details' },
            { id: 'modelDescription', label: 'Description' },
            { id: 'allowedGroups', label: 'Allowed Groups' },
            { id: 'modelStatus', label: 'Status' },
        ],
    },
];

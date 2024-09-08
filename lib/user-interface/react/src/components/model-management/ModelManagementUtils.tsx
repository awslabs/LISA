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
import { IModel, ModelStatus } from '../../shared/model/model-management.model';
import { StatusIndicatorProps } from '@cloudscape-design/components/status-indicator';
import { StatusIndicator } from '@cloudscape-design/components';

type EnumDictionary<T extends string | symbol | number, U> = {
    [K in T]: U;
};

export const MODEL_STATUS_LOOKUP: EnumDictionary<ModelStatus, StatusIndicatorProps.Type> = {
    [ModelStatus.Creating]: 'in-progress',
    [ModelStatus.InService]: 'success',
    [ModelStatus.Stopping]: 'in-progress',
    [ModelStatus.Stopped]: 'stopped',
    [ModelStatus.Updating]: 'in-progress',
    [ModelStatus.Deleting]: 'in-progress',
    [ModelStatus.Failed]: 'error',
};

export const CARD_DEFINITIONS = {
    header: (model: IModel) => <div>{model.modelId}</div>,
    sections: [
        {
            id: 'modelName',
            header: 'Name',
            content: (model: IModel) => model.modelName,
        },
        {
            id: 'modelType',
            header: 'Type',
            content: (model: IModel) => model.modelType,
        },
        {
            id: 'modelUrl',
            header: 'URL',
            content: (model: IModel) => model.modelUrl ? 'Model URL not defined' : model.modelUrl,
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
            content: (model: IModel) => model.instanceType ? 'Instance Type not defined' : model.instanceType,
        },
        {
            id: 'modelStatus',
            header: 'Status',
            content: (model: IModel) => (
                <StatusIndicator type={MODEL_STATUS_LOOKUP[model.status]}>{model.status}</StatusIndicator>
            ),
        },
    ],
};

export const PAGE_SIZE_OPTIONS = [
    { value: 6, label: '6 Models' },
    { value: 12, label: '12 Models' },
    { value: 24, label: '24 Models' },
    { value: 48, label: '48 Models' },
];

export const DEFAULT_PREFERENCES = {
    pageSize: 12,
    visibleContent: ['modelName', 'modelType', 'modelUrl', 'streaming', 'hosting', 'instanceType', 'modelStatus'],
};

export const VISIBLE_CONTENT_OPTIONS = [
    {
        label: 'Displayed Properties',
        options: [
            { id: 'modelName', label: 'Name' },
            { id: 'modelType', label: 'Type' },
            { id: 'modelUrl', label: 'URL' },
            { id: 'streaming', label: 'Streaming' },
            { id: 'hosting', label: 'LISA-Hosted Infrastructure' },
            { id: 'instanceType', label: 'Instance Type' },
            { id: 'modelStatus', label: 'Status' },
        ],
    },
];

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
  header: (model: IModel) => <div>{model.ModelName}</div>,
  sections: [
    {
      id: 'ModelId',
      header: 'ID',
      content: (model: IModel) => model.ModelId,
    },
    {
      id: 'ModelType',
      header: 'Type',
      content: (model: IModel) => model.ModelType,
    },
    {
      id: 'ModelUrl',
      header: 'URL',
      content: (model: IModel) => model.ModelUrl,
    },
    {
      id: 'Streaming',
      header: 'Streaming',
      content: (model: IModel) => String(model.Streaming),
    },
    {
      id: 'ModelStatus',
      header: 'Status',
      content: (model: IModel) => (
        <StatusIndicator type={MODEL_STATUS_LOOKUP[model.Status]}>{model.Status}</StatusIndicator>
      ),
    },
  ],
};

export const PAGE_SIZE_OPTIONS = [
  { value: 10, label: '10 Models' },
  { value: 30, label: '30 Models' },
  { value: 50, label: '50 Models' },
];

export const DEFAULT_PREFERENCES = {
  pageSize: 30,
  visibleContent: ['ModelType', 'ModelStatus'],
};

export const VISIBLE_CONTENT_OPTIONS = [
  {
    label: 'Main distribution properties',
    options: [
      { id: 'ModelId', label: 'ID' },
      { id: 'ModelType', label: 'Type' },
      { id: 'ModelUrl', label: 'URL' },
      { id: 'Streaming', label: 'Streaming' },
      { id: 'ModelStatus', label: 'Status' },
    ],
  },
];

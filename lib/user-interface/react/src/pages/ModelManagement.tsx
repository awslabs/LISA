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

import { useEffect, useState } from 'react';
import {
  Box,
  Button,
  ButtonDropdown,
  Cards,
  CollectionPreferences,
  Header,
  Modal,
  Pagination,
  StatusIndicator,
  TextFilter,
} from '@cloudscape-design/components';
import SpaceBetween from '@cloudscape-design/components/space-between';
import Form from '@cloudscape-design/components/form';
import Container from '@cloudscape-design/components/container';
import FormField from '@cloudscape-design/components/form-field';
import Input from '@cloudscape-design/components/input';
import { useGetAllModelsQuery } from '../shared/reducers/model-management.reducer';
import { IModel, ModelStatus, ModelType } from '../shared/model/model-management.model';

type EnumDictionary<T extends string | symbol | number, U> = {
  [K in T]: U;
};


const MODEL_STATUS_LOOKUP: EnumDictionary<ModelStatus, string> = {
  [ModelStatus.Creating]: "in-progress",
  [ModelStatus.InService]: "success",
  [ModelStatus.Stopping]: "in-progress",
  [ModelStatus.Stopped]: "stopped",
  [ModelStatus.Updating]: "in-progress",
  [ModelStatus.Deleting]: "in-progress",
  [ModelStatus.Failed]: "error"
}

const CARD_DEFINITIONS = {
  header: model => (
    <div>
      {model.ModelName}
    </div>
  ),
  sections: [
    {
      id: 'ModelId',
      header: 'ID',
      content: model => model.ModelId,
    },{
      id: 'ModelType',
      header: 'Type',
      content: model => model.ModelType,
    },{
      id: 'ModelUrl',
      header: 'URL',
      content: model => model.ModelUrl,
    },{
      id: 'Streaming',
      header: 'Streaming',
      content: model => String(model.Streaming),
    },
    {
      id: 'ModelStatus',
      header: 'Status',
      content: model => (
        <StatusIndicator type={MODEL_STATUS_LOOKUP[model.ModelStatus]}>{model.ModelStatus}</StatusIndicator>
      ),
    },
  ],
};

const VISIBLE_CONTENT_OPTIONS = [
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

const PAGE_SIZE_OPTIONS = [
  { value: 10, label: '10 Models' },
  { value: 30, label: '30 Models' },
  { value: 50, label: '50 Models' },
];

const DEFAULT_PREFERENCES = {
  pageSize: 30,
  visibleContent: ['ModelType', 'ModelStatus'],
};

export function ModelManagement({ setTools }) {
    const { data: allModels, isFetching: fetchingModels } = useGetAllModelsQuery();

    useEffect(() => {
        if(!fetchingModels && allModels)
            console.log(allModels)
    }, [allModels, fetchingModels]);

    useEffect(() => {
        setTools(null);
    }, [setTools]);

    const [selectedItems, setSelectedItems] = useState([]);
    const [preferences, setPreferences] = useState(DEFAULT_PREFERENCES);
    const [newModelModalVisible, setNewModelModelVisible] = useState(false);
    
    const models: IModel[] = [
      {
        ModelId: "123",
        ModelName: "Model 1",
        ModelType: ModelType.textgen,
        Streaming: true,
        ModelUrl: "http://dummy.url",
        ModelStatus: ModelStatus.Stopping
      },
      {
        ModelId: "234",
        ModelName: "Model 2",
        ModelType: ModelType.embedding,
        Streaming: true,
        ModelUrl: "http://dummy.url",
        ModelStatus: ModelStatus.Deleting
      },
      {
        ModelId: "345",
        ModelName: "Model 3",
        ModelType: ModelType.textgen,
        Streaming: true,
        ModelUrl: "http://dummy.url",
        ModelStatus: ModelStatus.Stopped
      },
      {
        ModelId: "456",
        ModelName: "Model 4",
        ModelType: ModelType.textgen,
        Streaming: true,
        ModelUrl: "http://dummy.url",
        ModelStatus: ModelStatus.Creating
      },
      {
        ModelId: "567",
        ModelName: "Model 5",
        ModelType: ModelType.embedding,
        Streaming: true,
        ModelUrl: "http://dummy.url",
        ModelStatus: ModelStatus.Failed
      },
      {
        ModelId: "678",
        ModelName: "Model 6",
        ModelType: ModelType.embedding,
        Streaming: false,
        ModelUrl: "http://dummy.url",
        ModelStatus: ModelStatus.InService
      },
      {
        ModelId: "789",
        ModelName: "Model 7",
        ModelType: ModelType.embedding,
        Streaming: true,
        ModelUrl: "http://dummy.url",
        ModelStatus: ModelStatus.Updating
      }
      ]

    return (
      <>
        <Modal
          onDismiss={() => setNewModelModelVisible(false)}
          visible={newModelModalVisible}
          header="Create Model"
        >
          <form onSubmit={e => e.preventDefault()}>
            <Form
              actions={
                <SpaceBetween direction="horizontal" size="xs">
                  <Button formAction="none" variant="link" onClick={() => setNewModelModelVisible(false)}>
                    Cancel
                  </Button>
                  <Button variant="primary">Submit</Button>
                </SpaceBetween>
              }
            >
              <Container
              >
                <SpaceBetween direction="vertical" size="l">
                  <FormField label="First field">
                    <Input value=""/>
                  </FormField>
                  <FormField label="Second field">
                    <Input value=""/>
                  </FormField>
                  <FormField label="Third field">
                    <Input value=""/>
                  </FormField>
                </SpaceBetween>
              </Container>
            </Form>
          </form>
        </Modal>
        <Cards
          onSelectionChange={({ detail }) =>
            setSelectedItems(detail?.selectedItems ?? [])
          }
          selectedItems={selectedItems}
          ariaLabels={{
            itemSelectionLabel: (e, t) => `select ${t.ModelName}`,
            selectionGroupLabel: "Model selection"
          }}
          cardDefinition={CARD_DEFINITIONS}
          visibleSections={preferences.visibleContent}
          loadingText="Loading models"
          items={models}
          selectionType="single"  // single | multi
          trackBy="ModelId"
          variant="full-page"
          header={
            <Header
              counter={
                selectedItems?.length
                  ? `(${selectedItems.length})`
                  : ""
              }
              actions={
                <SpaceBetween
                  direction="horizontal"
                  size="xs"
                >
                  <ButtonDropdown
                    items={[
                      {
                        text: "Start",
                        id: "start",
                        disabled: false
                      },
                      {
                        text: "Stop",
                        id: "stop",
                        disabled: false
                      },
                      {
                        text: "Edit",
                        id: "edit",
                        disabled: true
                      },
                      {
                        text: "Delete",
                        id: "delete",
                        disabled: true
                      }
                    ]}
                  >
                    Actions
                  </ButtonDropdown>
                  <Button iconName="add-plus" variant="primary" onClick={()=>setNewModelModelVisible(true)}>
                    New Model
                  </Button>
                </SpaceBetween>
              }
            >
              Models
            </Header>
          }
          filter={
            <TextFilter filteringPlaceholder="Find models" />
          }
          pagination={
            <Pagination currentPageIndex={1} pagesCount={1} />
          }
          preferences={
            <CollectionPreferences
              title="Preferences"
              confirmLabel="Confirm"
              cancelLabel="Cancel"
              preferences={preferences}
              onConfirm={({ detail }) => setPreferences(detail)}
              pageSizePreference={{
                title: 'Page size',
                options: PAGE_SIZE_OPTIONS,
              }}
              visibleContentPreference={{
                title: 'Select visible columns',
                options: VISIBLE_CONTENT_OPTIONS,
              }}
            />
          }
          empty={
            <Box
              margin={{ vertical: "xs" }}
              textAlign="center"
              color="inherit"
            >
              <SpaceBetween size="m">
                <b>No models</b>
              </SpaceBetween>
            </Box>
          }
        />
      </>
    );
}

export default ModelManagement;

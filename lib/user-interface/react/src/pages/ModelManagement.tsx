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
    Box, Button, ButtonDropdown,
    Cards,
    CollectionPreferences,
    Header, Modal,
    Pagination,
    StatusIndicator,
    TextFilter,
} from '@cloudscape-design/components';
import SpaceBetween from '@cloudscape-design/components/space-between';
import Form from '@cloudscape-design/components/form';
import Container from '@cloudscape-design/components/container';
import FormField from '@cloudscape-design/components/form-field';
import Input from '@cloudscape-design/components/input';

type EnumDictionary<T extends string | symbol | number, U> = {
  [K in T]: U;
};

enum ModelState {
  Running = "Running",
  Stopped = "Stopped",
  Starting = "Starting",
  Stopping = "Stopping",
  Failed = "Failed"
}

const MODEL_STATE_LOOKUP: EnumDictionary<ModelState, string> = {
  [ModelState.Running]: "success",
  [ModelState.Stopped]: "stopped",
  [ModelState.Starting]: "in-progress",
  [ModelState.Stopping]: "in-progress",
  [ModelState.Failed]: "error"
}


const CARD_DEFINITIONS = {
  header: model => (
    <div>
      {model.name}
    </div>
  ),
  sections: [
    {
      id: 'description',
      header: 'Description',
      content: model => model.description,
    },
    {
      id: 'state',
      header: 'State',
      content: model => (
        <StatusIndicator type={MODEL_STATE_LOOKUP[model.state]}>{model.state}</StatusIndicator>
      ),
    },
  ],
};

const VISIBLE_CONTENT_OPTIONS = [
  {
    label: 'Main distribution properties',
    options: [
      { id: 'description', label: 'Description' },
      { id: 'state', label: 'State' },
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
  visibleContent: ['description', 'state'],
};

export function ModelManagement({ setTools }) {

    useEffect(() => {
        setTools(null);
    }, [setTools]);

    const [selectedItems, setSelectedItems] = useState([]);
    const [preferences, setPreferences] = useState(DEFAULT_PREFERENCES);
    const [newModelModalVisible, setNewModelModelVisible] = useState(false);


    const models = [
      {
        name: "Model 1",
        description: "LLM 1",
        state: ModelState.Stopping
      },
      {
        name: "Model 2",
        description: "LLM 2",
        state: ModelState.Running
      },
      {
        name: "Model 3",
        description: "Expensive Model",
        state: ModelState.Stopped
      },
      {
        name: "Model 4",
        description: "Fast model",
        state: ModelState.Starting
      },
      {
        name: "Model 5",
        description: "Broken model",
        state: ModelState.Failed
      },
      {
        name: "Model 6",
        description: "Model v3",
        state: ModelState.Running
      }
      ]

    return (
      <div>
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
                    <Input />
                  </FormField>
                  <FormField label="Second field">
                    <Input />
                  </FormField>
                  <FormField label="Third field">
                    <Input />
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
            itemSelectionLabel: (e, t) => `select ${t.name}`,
            selectionGroupLabel: "Model selection"
          }}
          cardDefinition={CARD_DEFINITIONS}
          visibleSections={preferences.visibleContent}
          loadingText="Loading models"
          items={models}
          selectionType="single" // single | multi
          trackBy="name"
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
                    New model
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
      </div>
    );
}

export default ModelManagement;

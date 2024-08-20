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
import Form from '@cloudscape-design/components/form';
import SpaceBetween from '@cloudscape-design/components/space-between';
import { Button, Modal } from '@cloudscape-design/components';
import Container from '@cloudscape-design/components/container';
import FormField from '@cloudscape-design/components/form-field';
import Input from '@cloudscape-design/components/input';
import { IModel } from '../../../shared/model/model-management.model';

export type CreateModelModalProps = {
  visible: boolean;
  isEdit: boolean;
  setVisible: (boolean) => void;
  selectedItems: IModel[];
};

export function CreateModelModal(props: CreateModelModalProps) {
  return (
    <Modal onDismiss={() => props.setVisible(false)} visible={props.visible} header={`${props.isEdit ? 'Update' : 'Create'} Model`}>
      <form onSubmit={(e) => e.preventDefault()}>
        <Form
          actions={
            <SpaceBetween direction='horizontal' size='xs'>
              <Button formAction='none' variant='link' onClick={() => props.setVisible(false)}>
                Cancel
              </Button>
              <Button variant='primary'>Submit</Button>
            </SpaceBetween>
          }
        >
          <Container>
            <SpaceBetween direction='vertical' size='l'>
              <FormField label='First field'>
                <Input value='' />
              </FormField>
              <FormField label='Second field'>
                <Input value='' />
              </FormField>
              <FormField label='Third field'>
                <Input value='' />
              </FormField>
            </SpaceBetween>
          </Container>
        </Form>
      </form>
    </Modal>
  );
}

export default CreateModelModal;

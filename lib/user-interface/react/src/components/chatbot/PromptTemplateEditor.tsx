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

import {
    Modal,
    SpaceBetween,
    TextContent, Textarea,
} from '@cloudscape-design/components';

import FormField from '@cloudscape-design/components/form-field';
import Input from '@cloudscape-design/components/input';
import { IChatConfiguration } from '../../shared/model/chat.configurations.model';

export type PromptTemplateEditorProps = {
    chatConfiguration: IChatConfiguration;
    setChatConfiguration: (items: IChatConfiguration) => void;
    setVisible: (boolean) => void;
    visible: boolean;
};

export default function PromptTemplateEditor ({ chatConfiguration, setChatConfiguration,visible, setVisible }: PromptTemplateEditorProps) {
    // Defaults based on https://huggingface.co/docs/transformers/main_classes/text_generation#transformers.GenerationConfig
    // Default stop sequences based on User/Assistant instruction prompting for Falcon, Mistral, etc.
    return (
        <Modal
            onDismiss={() => setVisible(false)}
            visible={visible}
            header='Prompt Editor'
            footer=''
            size='large'
        >
            <TextContent>
                <h4>Prompt Template</h4>
                <p>
                    <small>
                        Sets the prompt used in a LangChain ConversationChain to converse with an LLM. The <code>`history`</code>{' '}
                        and <code>`input`</code> keys are available for use in the prompt like:
                        <br />
                        <br />
                        <code>
                            ```
                            <br />
                            Current conversation:
                            <br />
                            &#123;history&#125;
                            <br />
                            ```
                        </code>
                    </small>
                </p>
            </TextContent>
            <SpaceBetween direction='vertical' size='xs'>
                <Textarea
                    rows={10}
                    disableBrowserAutocorrect={false}
                    autoFocus
                    onChange={(e) => setChatConfiguration({ ...chatConfiguration, promptConfiguration: { ...chatConfiguration.promptConfiguration, promptTemplate: e.detail.value } })}
                    onKeyDown={(e) => {
                        if (e.detail.key === 'Enter' && !e.detail.shiftKey) {
                            e.preventDefault();
                        }
                    }}
                    value={chatConfiguration.promptConfiguration.promptTemplate}
                />
                <FormField description='Sets the prefix representing the user in the LLM prompt.' label='Human Prefix'>
                    <Input
                        value={chatConfiguration.promptConfiguration.humanPrefix}
                        onChange={(e) => setChatConfiguration({ ...chatConfiguration, promptConfiguration: { ...chatConfiguration.promptConfiguration, humanPrefix: e.detail.value } })}
                        onKeyDown={(e) => {
                            if (e.detail.key === 'Enter' && !e.detail.shiftKey) {
                                e.preventDefault();
                            }
                        }}
                    />
                </FormField>
                <FormField description='Sets the prefix representing the AI in the LLM prompt.' label='AI Prefix'>
                    <Input
                        value={chatConfiguration.promptConfiguration.aiPrefix}
                        onChange={(e) => setChatConfiguration({ ...chatConfiguration, promptConfiguration: { ...chatConfiguration.promptConfiguration, aiPrefix: e.detail.value } })}
                        onKeyDown={(e) => {
                            if (e.detail.key === 'Enter' && !e.detail.shiftKey) {
                                e.preventDefault();
                            }
                        }}
                    />
                </FormField>
            </SpaceBetween>
        </Modal>
    );
}

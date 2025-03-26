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
    Autosuggest,
    Box,
    Button,
    Modal,
    Select,
    SelectProps,
    SpaceBetween,
    Textarea,
    TextContent,
} from '@cloudscape-design/components';
import { useMemo, useState } from 'react';
import { IModel } from '../../shared/model/model-management.model';
import { IChatConfiguration } from '../../shared/model/chat.configurations.model';
import FormField from '@cloudscape-design/components/form-field';
import { PromptTemplate, useListPromptTemplatesQuery } from '../../shared/reducers/prompt-templates.reducer';
import { IConfiguration } from '../../shared/model/configuration.model';

export type PromptTemplateModalProps = {
    showModal: boolean;
    setShowModal: (state: boolean) => void;
    setUserPrompt: (state: string) => void;
    setSelectedModel: (state: IModel) => void;
    chatConfiguration: IChatConfiguration;
    setChatConfiguration: (state: IChatConfiguration) => void;
    config: IConfiguration;
};

export function PromptTemplateModal ({
    showModal,
    setShowModal,
    setUserPrompt,
    setSelectedModel,
    chatConfiguration,
    setChatConfiguration,
    config
}: PromptTemplateModalProps) {
    const [selectedOption, setSelectedOption] = useState<SelectProps.Option>({label: 'Owned by me', value: ''});
    const args = {showPublic: Boolean(selectedOption.value)};
    const { data: {Items: allItems} = {Items: []}, isFetching: isFetchingList } = useListPromptTemplatesQuery(args, {});
    const [selectedItem, setSelectedItem] = useState<PromptTemplate>();
    const [suggestText, setSuggestText] = useState<string>('');
    const [promptTemplateText, setPromptTemplateText] = useState(chatConfiguration.promptConfiguration.promptTemplate);

    const options: SelectProps.Option[] = useMemo(() => {
        return isFetchingList ? [] : allItems.map((item) => ({
            value: item.title,
            label: item.title,
            labelTags: [item.id],
            id: item.id
        }));
    }, [allItems, isFetchingList]);

    return (
        <Modal
            onDismiss={() => {
                setShowModal(false);
                setSelectedItem(undefined);
                setUserPrompt('');
                setSelectedModel(undefined);
                setSelectedItem(undefined);
            }}
            visible={showModal}
            header='Prompt Editor'
            size='large'
            footer={
                <Box float='right'>
                    <SpaceBetween direction='horizontal' size='xs'>
                        <Button
                            onClick={() => {
                                setShowModal(false);
                                setSelectedItem(undefined);
                                setUserPrompt('');
                                setSelectedModel(undefined);
                            }}
                            variant={'link'}
                        >
                            Cancel
                        </Button>
                        <Button
                            variant='primary'
                            onClick={() => {
                                setChatConfiguration({
                                    ...chatConfiguration,
                                    promptConfiguration: {
                                        ...chatConfiguration.promptConfiguration,
                                        promptTemplate: selectedItem.body
                                    }
                                });

                                setShowModal(false);
                            }}
                            disabled={selectedItem === undefined}
                        >
                            Use Prompt
                        </Button>
                    </SpaceBetween>
                </Box>
            }
        >
            <SpaceBetween direction='vertical' size='m'>
                { config?.configuration?.enabledComponents?.showPromptTemplateLibrary && <SpaceBetween direction='horizontal' size='s'>
                    <FormField label='Select existing Prompt'>
                        <SpaceBetween direction='horizontal' size='s'>
                            <Autosuggest
                                placeholder='Search by title'
                                filteringType='auto'
                                value={suggestText}
                                empty={'No Prompt found'}
                                statusType={isFetchingList ? 'loading' : 'finished'}
                                onChange={({detail}) => {
                                    setSuggestText(detail.value);
                                    if (detail.value.length === 0) {
                                        setSelectedItem(undefined);
                                    }
                                }}
                                onSelect={({detail}) => {
                                    const item = allItems.find((item) => item.id === detail.selectedOption?.id);
                                    setSelectedItem(item);
                                    setPromptTemplateText(item.body);
                                }}
                                loadingText={'Loading Prompts'}
                                options={options}
                            />
                            <Select selectedOption={selectedOption} options={[
                                {label: 'Owned by me', value: ''},
                                {label: 'Public', value: 'true'}
                            ]} onChange={({detail}) => {
                                setSelectedOption(detail.selectedOption);
                            }} />
                        </SpaceBetween>
                    </FormField>
                    <FormField>
                    </FormField>

                </SpaceBetween>}

                <hr />
                    
                { selectedItem  && <SpaceBetween direction='vertical' size='s'>
                    <FormField label='Title'>
                        <TextContent>{ selectedItem.title }</TextContent>
                    </FormField>
                </SpaceBetween>}

                <FormField label='Prompt Template' description='Sets the initial system prompt to setup the conversation with an LLM.'>
                    <Textarea rows={10} value={promptTemplateText} placeholder='Enter prompt text' onChange={({detail}) => setPromptTemplateText(detail.value)} />
                </FormField>
            </SpaceBetween>
        </Modal>
    );
}

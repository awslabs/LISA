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
    Link,
    Modal,
    Select,
    SelectProps,
    SpaceBetween,
    Textarea,
} from '@cloudscape-design/components';
import { useMemo, useState } from 'react';
import { IModel } from '../../shared/model/model-management.model';
import { DEFAULT_PROMPT_TEMPLATE, IChatConfiguration } from '../../shared/model/chat.configurations.model';
import FormField from '@cloudscape-design/components/form-field';
import { useListPromptTemplatesQuery } from '../../shared/reducers/prompt-templates.reducer';
import { IConfiguration } from '../../shared/model/configuration.model';
import { LisaChatSession } from '../types';

export type PromptTemplateModalProps = {
    session: LisaChatSession,
    showModal: boolean;
    setShowModal: (state: boolean) => void;
    setUserPrompt: (state: string) => void;
    setSelectedModel: (state: IModel) => void;
    chatConfiguration: IChatConfiguration;
    setChatConfiguration: (state: IChatConfiguration) => void;
    config: IConfiguration;
};

export function PromptTemplateModal ({
    session,
    showModal,
    setShowModal,
    setUserPrompt,
    setSelectedModel,
    chatConfiguration,
    setChatConfiguration,
    config,
}: PromptTemplateModalProps) {
    const [selectedOption, setSelectedOption] = useState<SelectProps.Option>({label: 'Owned by me', value: ''});
    const args = {showPublic: Boolean(selectedOption.value)};
    const { data: {Items: allItems} = {Items: []}, isFetching: isFetchingList } = useListPromptTemplatesQuery(args, {});
    const [suggestText, setSuggestText] = useState<string>('');
    const [promptTemplateText, setPromptTemplateText] = useState(chatConfiguration.promptConfiguration.promptTemplate);
    const disabled = session.history.length > 0;

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
                setUserPrompt('');
                setSelectedModel(undefined);
            }}
            visible={showModal}
            header={'Persona Editor'}
            size='large'
            footer={
                <Box float='right'>
                    <SpaceBetween direction='horizontal' size='xs'>
                        <Button
                            onClick={() => {
                                setShowModal(false);
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
                                        promptTemplate: promptTemplateText
                                    }
                                });

                                setShowModal(false);
                            }}
                            disabled={disabled}
                            disabledReason={'The Prompt cannot be updated after session has started.'}
                        >
                            Use Persona
                        </Button>
                    </SpaceBetween>
                </Box>
            }
        >
            <SpaceBetween direction='vertical' size='m'>
                { !disabled && config?.configuration?.enabledComponents?.showPromptTemplateLibrary && <SpaceBetween direction='horizontal' size='s'>
                    <FormField label={'Select existing Persona'}>
                        <SpaceBetween direction='horizontal' size='s'>
                            <Autosuggest
                                placeholder='Search by title'
                                filteringType='auto'
                                value={suggestText}
                                empty={'No Prompt found'}
                                statusType={isFetchingList ? 'loading' : 'finished'}
                                onChange={({detail}) => {
                                    setSuggestText(detail.value);
                                }}
                                onSelect={({detail}) => {
                                    const item = allItems.find((item) => item.id === detail.selectedOption?.id);
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

                <FormField label={'Persona Template'} description='Sets the initial system prompt to setup the conversation with an LLM.'>
                    <Textarea rows={10} value={promptTemplateText} placeholder='Enter prompt text' onChange={({detail}) => setPromptTemplateText(detail.value)} />
                </FormField>
                { !disabled && promptTemplateText !== DEFAULT_PROMPT_TEMPLATE && (
                    <Link onClick={() => {
                        setSuggestText('');
                        setPromptTemplateText(DEFAULT_PROMPT_TEMPLATE);
                    }}>Reset to default</Link>
                )}
            </SpaceBetween>
        </Modal>
    );
}

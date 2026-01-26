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
import { useEffect, useMemo, useState } from 'react';
import { DEFAULT_PROMPT_TEMPLATE, IChatConfiguration } from '../../shared/model/chat.configurations.model';
import FormField from '@cloudscape-design/components/form-field';
import { PromptTemplateType, useListPromptTemplatesQuery, promptTemplateApi } from '../../shared/reducers/prompt-templates.reducer';
import { IConfiguration } from '../../shared/model/configuration.model';
import { LisaChatSession } from '../types';
import { useAppDispatch } from '@/config/store';

export type PromptTemplateModalProps = {
    session: LisaChatSession,
    showModal: boolean;
    setShowModal: (state: boolean) => void;
    setUserPrompt: (state: string) => void;
    chatConfiguration: IChatConfiguration;
    setChatConfiguration: (state: IChatConfiguration) => void;
    config: IConfiguration;
    type ?: PromptTemplateType;
};

export const PromptTemplateModal = ({
    session,
    showModal,
    setShowModal,
    setUserPrompt,
    chatConfiguration,
    setChatConfiguration,
    config,
    type,
}: PromptTemplateModalProps)  => {
    const isPersona = type === PromptTemplateType.Persona;
    const [selectedOption, setSelectedOption] = useState<SelectProps.Option>({label: 'Owned by me', value: ''});
    const args = {showPublic: Boolean(selectedOption.value)};
    const { data: {Items: allItems} = {Items: []}, isFetching: isFetchingList } = useListPromptTemplatesQuery(args, {});
    const [suggestText, setSuggestText] = useState<string>('');
    const [promptTemplateText, setPromptTemplateText] = useState(isPersona ? chatConfiguration.promptConfiguration.promptTemplate : '');
    const disabled = isPersona && session.history.length > 0;
    const dispatch = useAppDispatch();
    const [startingPrompt, setStartingPrompt] = useState<string>(null);

    const options: SelectProps.Option[] = useMemo(() => {
        return isFetchingList ? [] : allItems.filter((item) => item.type === type || !type).map((item) => ({
            value: item.title,
            label: item.title,
            labelTags: [item.id],
            id: item.id
        }));
    }, [allItems, isFetchingList, type]);

    const keyWord = isPersona ? 'Persona' : 'Prompt';

    useEffect(() => {
        if (showModal){
            // refresh prompt templates
            dispatch(promptTemplateApi.util.invalidateTags(['promptTemplates']));
        }
    }, [showModal, dispatch]);

    const modalTestId = 'prompt-template-modal';
    return (
        <Modal
            data-testid={modalTestId}
            onDismiss={() => {
                setShowModal(false);
                setUserPrompt('');
            }}
            visible={showModal}
            header={`${keyWord} Editor`}
            size='large'
            footer={
                <Box float='right'>
                    <SpaceBetween direction='horizontal' size='xs'>
                        <Button
                            onClick={() => {
                                setShowModal(false);
                                setUserPrompt('');
                            }}
                            variant={'link'}
                        >
                            Cancel
                        </Button>
                        <Button
                            data-testid='use-prompt-button'
                            variant='primary'
                            onClick={() => {
                                if (isPersona) {
                                    setChatConfiguration({
                                        ...chatConfiguration,
                                        promptConfiguration: {
                                            ...chatConfiguration.promptConfiguration,
                                            promptTemplate: promptTemplateText
                                        }
                                    });
                                } else if (type === PromptTemplateType.Directive) {
                                    setUserPrompt(promptTemplateText);
                                }

                                setShowModal(false);
                            }}
                            disabled={disabled}
                            disabledReason={'The Prompt cannot be updated after session has started.'}
                        >
                            Use {keyWord}
                        </Button>
                    </SpaceBetween>
                </Box>
            }
        >
            <SpaceBetween direction='vertical' size='m'>
                { !disabled && config?.configuration?.enabledComponents?.showPromptTemplateLibrary && <SpaceBetween direction='horizontal' size='s'>
                    <FormField label={`Select existing ${keyWord}`}>
                        <SpaceBetween direction='horizontal' size='s'>
                            <Autosuggest
                                placeholder='Search by title'
                                filteringType='auto'
                                value={suggestText}
                                empty={'No Prompt found'}
                                enteredTextLabel={(value) => `Use "${value}"`}
                                statusType={isFetchingList ? 'loading' : 'finished'}
                                onChange={({detail}) => {
                                    setSuggestText(detail.value);
                                }}
                                onSelect={({detail}) => {
                                    // Try to find by id first, then fall back to matching by title/value
                                    let item = allItems.find((item) => item.id === detail.selectedOption?.id);
                                    if (!item && detail.selectedOption?.value) {
                                        item = allItems.find((item) => item.title === detail.selectedOption.value);
                                    }
                                    if (item) {
                                        setPromptTemplateText(item.body);
                                        setStartingPrompt(item.body);
                                    }
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
                </SpaceBetween>}

                <hr />

                <FormField label={`${keyWord} Template`} description={`${isPersona ? 'Sets the initial system prompt to setup the conversation with an LLM.' : 'Sets the prompt for use in conversation with the LLM.'}`}>
                    <Textarea rows={10} value={promptTemplateText} placeholder='Enter prompt text' onChange={({detail}) => setPromptTemplateText(detail.value)} />
                </FormField>
                { !disabled && promptTemplateText !== DEFAULT_PROMPT_TEMPLATE && (
                    <Link onClick={() => {
                        setSuggestText(isPersona ? '' : suggestText);
                        setPromptTemplateText(isPersona ? DEFAULT_PROMPT_TEMPLATE : startingPrompt);
                    }}>Reset to default</Link>
                )}
            </SpaceBetween>
        </Modal>
    );
};

export default PromptTemplateModal;

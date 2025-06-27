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

import { v4 as uuidv4 } from 'uuid';
import { Button, Header, SpaceBetween, TextContent } from '@cloudscape-design/components';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faFileLines, faMessage, faPenToSquare, faComment } from '@fortawesome/free-regular-svg-icons';
import { PromptTemplateType } from '@/shared/reducers/prompt-templates.reducer';
import { IConfiguration } from '@/shared/model/configuration.model';

type WelcomeScreenProps = {
    navigate: (path: string) => void;
    modelSelectRef: React.RefObject<HTMLInputElement>;
    config: IConfiguration;
    refreshPromptTemplate: () => void;
    setFilterPromptTemplateType: (type: PromptTemplateType) => void;
    openModal: (modalName: string) => void;
};

export const WelcomeScreen = ({
    navigate,
    modelSelectRef,
    config,
    refreshPromptTemplate,
    setFilterPromptTemplateType,
    openModal,
}: WelcomeScreenProps) => {
    return (
        <div style={{
            height: '400px',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            alignItems: 'center',
            gap: '2em',
            textAlign: 'center'
        }}>
            <div>
                <Header variant='h1'>What would you like to do?</Header>
            </div>
            <div style={{
                display: 'flex',
                flexDirection: 'row',
                justifyContent: 'center',
                alignItems: 'center',
                gap: '1em',
                textAlign: 'center'
            }}>
                <Button variant='normal' onClick={() => {
                    navigate(`/ai-assistant/${uuidv4()}`);
                    modelSelectRef?.current?.focus();
                }}>
                    <SpaceBetween direction='horizontal' size='xs'>
                        <FontAwesomeIcon icon={faMessage} />
                        <TextContent>Start chatting</TextContent>
                    </SpaceBetween>
                </Button>

                {config?.configuration?.enabledComponents?.showPromptTemplateLibrary && (
                    <>
                        <Button variant='normal' onClick={() => {
                            refreshPromptTemplate();
                            setFilterPromptTemplateType(PromptTemplateType.Persona);
                            openModal('promptTemplate');
                        }}>
                            <SpaceBetween direction='horizontal' size='xs'>
                                <FontAwesomeIcon icon={faPenToSquare} />
                                <TextContent>Select Persona</TextContent>
                            </SpaceBetween>
                        </Button>
                        <Button variant='normal' onClick={() => {
                            refreshPromptTemplate();
                            setFilterPromptTemplateType(PromptTemplateType.Directive);
                            openModal('promptTemplate');
                        }}>
                            <SpaceBetween direction='horizontal' size='xs'>
                                <FontAwesomeIcon icon={faComment} />
                                <TextContent>Select Directive</TextContent>
                            </SpaceBetween>
                        </Button>
                    </>
                )}

                <Button variant='normal' onClick={() => openModal('documentSummarization')}>
                    <SpaceBetween direction='horizontal' size='xs'>
                        <FontAwesomeIcon icon={faFileLines} />
                        <TextContent>Summarize a doc</TextContent>
                    </SpaceBetween>
                </Button>
            </div>
        </div>
    );
};

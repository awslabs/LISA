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
import { Header } from '@cloudscape-design/components';
import { faFileLines, faMessage, faPenToSquare, faComment } from '@fortawesome/free-regular-svg-icons';
import { PromptTemplateType } from '@/shared/reducers/prompt-templates.reducer';
import { IConfiguration } from '@/shared/model/configuration.model';
import { ButtonBadge } from '@/components/common/ButtonBadge';
import { faCodeCompare } from '@fortawesome/free-solid-svg-icons';

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
                flexWrap: 'wrap',
                justifyContent: 'center',
                alignItems: 'center',
                gap: '1em',
                textAlign: 'center'
            }}>
                <ButtonBadge
                    text='Start Chatting'
                    icon={faMessage}
                    onClick={() => {
                        navigate(`/ai-assistant/${uuidv4()}`);
                        modelSelectRef?.current?.focus();
                    }}
                />

                <ButtonBadge
                    text='Select Persona'
                    icon={faPenToSquare}
                    onClick={() => {
                        refreshPromptTemplate();
                        setFilterPromptTemplateType(PromptTemplateType.Persona);
                        openModal('promptTemplate');
                    }}
                    show={config?.configuration?.enabledComponents?.showPromptTemplateLibrary}
                />

                <ButtonBadge
                    text='Select Directive'
                    icon={faComment}
                    onClick={() => {
                        refreshPromptTemplate();
                        setFilterPromptTemplateType(PromptTemplateType.Directive);
                        openModal('promptTemplate');
                    }}
                    show={config?.configuration?.enabledComponents?.showPromptTemplateLibrary}
                />

                <ButtonBadge
                    text='Summarize a Doc'
                    icon={faFileLines}
                    onClick={() => openModal('documentSummarization')}
                />

                <ButtonBadge
                    text='Compare Models'
                    icon={faCodeCompare}
                    onClick={() => navigate('/model-comparison')}
                    show={config?.configuration?.enabledComponents?.enableModelComparisonUtility}
                />
            </div>
        </div>
    );
};

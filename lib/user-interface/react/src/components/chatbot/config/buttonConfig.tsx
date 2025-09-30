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

import { ButtonGroupProps } from '@cloudscape-design/components';
import { IConfiguration } from '@/shared/model/configuration.model';
import { useCallback } from 'react';
import { PromptTemplateType } from '@/shared/reducers/prompt-templates.reducer';

export const getButtonItems = (
    config: IConfiguration,
    useRag: boolean,
    isImageGenerationMode: boolean
): ButtonGroupProps.Item[] => {
    const baseItems: ButtonGroupProps.Item[] = [
        {
            type: 'icon-button',
            id: 'settings',
            iconName: 'settings',
            text: 'Session configuration'
        }
    ];

    const conditionalItems: ButtonGroupProps.Item[] = [];

    // RAG Upload
    if (config?.configuration.enabledComponents.uploadRagDocs &&
        window.env.RAG_ENABLED &&
        !isImageGenerationMode) {
        conditionalItems.push({
            type: 'icon-button',
            id: 'upload-to-rag',
            iconName: 'upload',
            text: 'Upload to RAG',
            disabled: !useRag
        });
        
        // RAG Job Status
        conditionalItems.push({
            type: 'icon-button',
            id: 'rag-job-status',
            iconName: 'status-info',
            text: 'RAG Job Status',
            disabled: !useRag
        });
    }

    // Context Upload
    if (config?.configuration.enabledComponents.uploadContextDocs &&
        !isImageGenerationMode) {
        conditionalItems.push({
            type: 'icon-button',
            id: 'add-file-to-context',
            iconName: 'insert-row',
            text: 'Add file to context'
        });
    }

    // Prompt Template Library
    if (config?.configuration.enabledComponents.showPromptTemplateLibrary) {
        conditionalItems.push({
            type: 'icon-button',
            id: 'insert-prompt-template',
            iconName: 'contact',
            text: 'Insert Prompt Template'
        });
    }

    // Document Summarization
    if (config?.configuration.enabledComponents.documentSummarization) {
        conditionalItems.push({
            type: 'icon-button',
            id: 'summarize-document',
            iconName: 'transcript',
            text: 'Summarize Document'
        });
    }

    // Additional Configuration Dropdown
    if (config?.configuration.enabledComponents.editPromptTemplate &&
        !isImageGenerationMode) {
        conditionalItems.push({
            type: 'menu-dropdown',
            id: 'more-actions',
            text: 'Additional Configuration',
            items: [
                {
                    id: 'edit-prompt-template',
                    iconName: 'contact',
                    text: 'Edit Persona'
                },
            ]
        });
    }

    return [...baseItems, ...conditionalItems];
};

export const useButtonActions = ({
    openModal,
    refreshPromptTemplate,
    setFilterPromptTemplateType,
}: {
    openModal: (modalName: string) => void;
    refreshPromptTemplate: () => void;
    setFilterPromptTemplateType: (type: any) => void;
}) => {
    const handleButtonClick = useCallback(({ detail }: { detail: { id: string } }) => {
        const actions: Record<string, () => void> = {
            'settings': () => openModal('sessionConfiguration'),
            'edit-prompt-template': () => {
                refreshPromptTemplate();
                setFilterPromptTemplateType(PromptTemplateType.Persona);
                openModal('promptTemplate');
            },
            'upload-to-rag': () => openModal('ragUpload'),
            'rag-job-status': () => openModal('jobStatus'),
            'add-file-to-context': () => openModal('contextUpload'),
            'summarize-document': () => openModal('documentSummarization'),
            'insert-prompt-template': () => {
                refreshPromptTemplate();
                setFilterPromptTemplateType(PromptTemplateType.Directive);
                openModal('promptTemplate');
            },
        };

        const action = actions[detail.id];
        if (action) {
            action();
        }
    }, [openModal, refreshPromptTemplate, setFilterPromptTemplateType]);

    return { handleButtonClick };
};

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

import { useCallback, useState } from 'react';

export type ModalState = {
    sessionConfiguration: boolean;
    contextUpload: boolean;
    ragUpload: boolean;
    documentSummarization: boolean;
    promptTemplate: boolean;
    modelComparison: boolean
};

export const useModals = () => {
    const [modals, setModals] = useState<ModalState>({
        sessionConfiguration: false,
        contextUpload: false,
        ragUpload: false,
        documentSummarization: false,
        promptTemplate: false,
        modelComparison: false,
    });

    const [promptTemplateKey, setPromptTemplateKey] = useState(new Date().toISOString());
    const [filterPromptTemplateType, setFilterPromptTemplateType] = useState(undefined);

    const openModal = useCallback((modalName: keyof ModalState) => {
        setModals((prev) => ({ ...prev, [modalName]: true }));
    }, []);

    const closeModal = useCallback((modalName: keyof ModalState) => {
        setModals((prev) => ({ ...prev, [modalName]: false }));
    }, []);

    const refreshPromptTemplate = useCallback(() => {
        setPromptTemplateKey(new Date().toISOString());
    }, []);

    return {
        modals,
        openModal,
        closeModal,
        promptTemplateKey,
        setPromptTemplateKey,
        filterPromptTemplateType,
        setFilterPromptTemplateType,
        refreshPromptTemplate,
    };
};
